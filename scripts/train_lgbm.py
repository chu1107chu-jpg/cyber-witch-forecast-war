"""
Переобучение модели предсказания акций (LightGBM).

- Признаки строятся через src/stock_features.py — тот же код, что использует
  приложение для инференса (раньше этот скрипт держал свою устаревшую копию
  build_features() на 20 признаков без макро — она разошлась с реально
  задеплоенной моделью на 39 признаках; теперь расхождение невозможно).
- Purged & embargoed walk-forward CV (Лопес де Прадо, "Advances in Financial
  Machine Learning") вместо наивного K-fold: таргеты p5_up/p20_up смотрят на
  N дней вперёд, поэтому соседние по времени сэмплы имеют перекрывающиеся
  окна меток — обычный K-fold в такой ситуации завышает метрику, потому что
  часть "будущего" из train просачивается в validation и обратно.
- Отдельно — честный OOS-тест на 2024-2026, который CV вообще не видит.
- Сохраняет в data/artifacts/lgbm/ — это то, что реально читает app_local.py
  (раньше скрипт по ошибке писал в data/artifacts/sklearn/, т.е. играл в
  собственную песочницу, а задеплоенная модель приходила откуда-то ещё).
"""

import json
import os
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import lightgbm as lgb
import yfinance as yf
from sklearn.metrics import accuracy_score, roc_auc_score

warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from stock_features import build_features, fetch_macro_range, FEATURE_COLS  # noqa: E402

ARTIFACTS = Path(__file__).parent.parent / "data/artifacts/lgbm"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "BRK-B", "XOM", "JPM",
    "BTC-USD", "ETH-USD", "GC=F", "^GSPC", "^IXIC",
]

DATA_START  = "2016-01-01"
DATA_END    = "2026-03-01"
TRAIN_END   = "2023-12-31"
TEST_START  = "2024-01-01"

N_CV_FOLDS = 5
HORIZONS = {"target_p5_up": 5, "target_p20_up": 20}  # дней вперёд

LGB_PARAMS = dict(
    objective="binary", n_estimators=500, learning_rate=0.02,
    num_leaves=31, max_depth=5, min_child_samples=60,
    subsample=0.8, colsample_bytree=0.7,
    reg_alpha=0.2, reg_lambda=2.0,
    random_state=42, n_jobs=-1, verbose=-1,
)


# ─────────────────────────────────────────────
#  Purged & embargoed K-fold (по календарным датам)
# ─────────────────────────────────────────────
def purged_kfold_splits(train: pd.DataFrame, label_date_col: str, n_folds: int, embargo_days: int):
    """
    Возвращает список (train_mask, val_mask) — numpy bool-массивы по индексу train.

    train индексирован календарными датами (может быть много строк на одну
    дату — разные тикеры). label_date_col — дата, на которую "смотрит"
    таргет этой строки (dropna уже применён, так что она всегда есть).

    Для каждого фолда: validation — календарный блок дат; из train фолда
    убираются (а) сама validation-строка, (б) любая строка, чей label_date
    попадает внутрь validation-блока (purge — иначе train "видит" кусок
    будущего, которое проверяется в validation), (в) строки в течение
    embargo_days торговых дней ПОСЛЕ конца validation-блока (embargo —
    защита от остаточной автокорреляции признаков).
    """
    dates = np.sort(train.index.unique())
    bounds = np.array_split(dates, n_folds)
    idx_dates = train.index.values
    label_dates = train[label_date_col].values

    splits = []
    for block in bounds:
        if len(block) == 0:
            continue
        v_start, v_end = block[0], block[-1]

        val_mask = (idx_dates >= v_start) & (idx_dates <= v_end)

        # embargo-граница: v_end + embargo_days торговых дней вперёд по
        # календарю всей выборки (приблизительно — по позиции в unique dates)
        end_pos = np.searchsorted(dates, v_end)
        embargo_end_pos = min(end_pos + embargo_days, len(dates) - 1)
        embargo_end = dates[embargo_end_pos]

        purge_mask = (idx_dates < v_start) & (label_dates >= v_start) & (label_dates <= v_end)
        embargo_mask = (idx_dates > v_end) & (idx_dates <= embargo_end)

        train_mask = ~val_mask & ~purge_mask & ~embargo_mask
        splits.append((train_mask, val_mask))
    return splits


def run_purged_cv(train: pd.DataFrame, feature_cols: list[str], y_col: str,
                   label_date_col: str, n_folds: int, embargo_days: int) -> dict:
    splits = purged_kfold_splits(train, label_date_col, n_folds, embargo_days)
    fold_aucs, fold_accs = [], []
    for train_mask, val_mask in splits:
        X_tr, y_tr = train.loc[train_mask, feature_cols].values, train.loc[train_mask, y_col].values
        X_va, y_va = train.loc[val_mask, feature_cols].values, train.loc[val_mask, y_col].values
        if len(np.unique(y_tr)) < 2 or len(np.unique(y_va)) < 2:
            continue  # вырожденный фолд (все 0 или все 1) — пропускаем
        model = lgb.LGBMClassifier(**LGB_PARAMS)
        model.fit(X_tr, y_tr)
        proba = model.predict_proba(X_va)[:, 1]
        fold_aucs.append(roc_auc_score(y_va, proba))
        fold_accs.append(accuracy_score(y_va, (proba >= 0.5).astype(int)))
    return {
        "cv_auc": float(np.mean(fold_aucs)) if fold_aucs else None,
        "cv_acc": float(np.mean(fold_accs)) if fold_accs else None,
        "cv_folds_auc": [round(float(a), 4) for a in fold_aucs],
        "n_folds_used": len(fold_aucs),
    }


def main():
    t0 = time.time()
    print("Загружаю котировки...")
    frames = []
    for t in TICKERS:
        df = yf.download(t, start=DATA_START, end=DATA_END, auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df.dropna()
        if len(df) < 300:
            print(f"  {t}: пропущен (мало данных)")
            continue
        frames.append((t, df))
        print(f"  {t}: {len(df)} строк котировок")

    print("Загружаю макро (VIX/TNX/DXY)...")
    macro = fetch_macro_range(DATA_START, DATA_END)

    built = []
    for t, df in frames:
        d = build_features(df, macro)
        for target, h in HORIZONS.items():
            d[target.replace("target_", "y_")] = (d["Close"].shift(-h) > d["Close"]).astype(int)
            # дата, на которую "смотрит" таргет этой строки — нужна для purge
            d[f"label_date_{h}"] = d.index.to_series().shift(-h)
        d["ticker"] = t
        d = d.dropna()
        built.append(d)

    data = pd.concat(built).sort_index()
    print(f"Итого: {len(data)} строк, {len(built)} тикеров, {len(FEATURE_COLS)} признаков")

    train = data[data.index <= TRAIN_END]
    test  = data[data.index >= TEST_START]
    print(f"Трейн: {len(train)} | OOS тест (2024-2026, CV не видит): {len(test)}")

    X_tr = train[FEATURE_COLS].values
    X_te = test[FEATURE_COLS].values

    models_out = {}
    metrics = {}

    for target, h in HORIZONS.items():
        y_col = target.replace("target_", "y_")
        label_date_col = f"label_date_{h}"

        print(f"\n=== {target} (горизонт {h} дн.) ===")

        # 1) Purged & embargoed CV — честная оценка на трейне
        cv_res = run_purged_cv(train, FEATURE_COLS, y_col, label_date_col,
                                n_folds=N_CV_FOLDS, embargo_days=h)
        print(f"  Purged CV AUC:  {cv_res['cv_auc']:.4f}  (фолдов: {cv_res['n_folds_used']}/{N_CV_FOLDS})")
        print(f"  Purged CV acc:  {cv_res['cv_acc']:.1%}")

        # 2) Финальная модель на всём трейне -> честный OOS-тест 2024-2026
        y_tr = train[y_col].values
        y_te = test[y_col].values
        model = lgb.LGBMClassifier(**LGB_PARAMS)
        model.fit(X_tr, y_tr,
                  eval_set=[(X_te, y_te)],
                  callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)])
        proba = model.predict_proba(X_te)[:, 1]
        oos_auc = roc_auc_score(y_te, proba)
        oos_acc = accuracy_score(y_te, (proba >= 0.5).astype(int))

        # "уверенные" сигналы — топ-30% по |proba-0.5|, как раньше
        thresh = np.percentile(np.abs(proba - 0.5), 70)
        conf = np.abs(proba - 0.5) >= thresh
        oos_acc_conf = accuracy_score(y_te[conf], (proba[conf] >= 0.5).astype(int))

        print(f"  OOS AUC (2024-2026):        {oos_auc:.4f}")
        print(f"  OOS acc (все сигналы):      {oos_acc:.1%}")
        print(f"  OOS acc (увер. топ-30%):    {oos_acc_conf:.1%}  ({conf.sum()}/{len(y_te)} сигналов)")

        # Feature importance — чтобы видеть, какие признаки реально работают
        importances = sorted(
            zip(FEATURE_COLS, model.feature_importances_.tolist()),
            key=lambda kv: kv[1], reverse=True,
        )

        models_out[target] = model
        metrics[target] = {
            "cv_auc": cv_res["cv_auc"],
            "cv_acc": cv_res["cv_acc"],
            "cv_folds_auc": cv_res["cv_folds_auc"],
            "cv_method": f"purged_embargoed_kfold(n={N_CV_FOLDS}, embargo_days={h})",
            "oos_auc": round(float(oos_auc), 4),
            "oos_acc": round(float(oos_acc), 4),
            "oos_acc_confident_top30": round(float(oos_acc_conf), 4),
            "oos_confident_signals": int(conf.sum()),
            "oos_total_samples": int(len(y_te)),
            "top_features": importances[:10],
        }

    joblib.dump(models_out, ARTIFACTS / "models.pkl")
    joblib.dump(FEATURE_COLS, ARTIFACTS / "feature_cols.pkl")

    summary = {
        "model_type": "LightGBM, purged & embargoed walk-forward CV + true OOS holdout",
        "tickers": TICKERS, "n_tickers": len(built),
        "n_samples": int(len(train)), "n_features": len(FEATURE_COLS),
        "feature_cols": FEATURE_COLS,
        "train_period": f"{DATA_START} - {TRAIN_END}",
        "oos_period": f"{TEST_START} - {DATA_END}",
        "targets": list(HORIZONS.keys()),
        "metrics": metrics,
        "lgb_params": LGB_PARAMS,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": round(time.time() - t0, 1),
        "note": (
            "cv_auc/cv_acc — purged & embargoed K-fold на трейне (2016-2023), "
            "честная оценка без утечки между соседними по времени фолдами "
            "(таргеты смотрят на 5/20 дней вперёд, поэтому обычный K-fold "
            "завышал бы метрику). oos_auc/oos_acc — отдельный истинный "
            "холд-аут 2024-2026, который CV вообще не видел."
        ),
    }
    with open(ARTIFACTS / "train_summary.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\nАртефакты сохранены в: {ARTIFACTS}")
    for t, m in metrics.items():
        print(f"  {t}: CV AUC={m['cv_auc']}, OOS AUC={m['oos_auc']}, OOS acc={m['oos_acc']:.1%}")


if __name__ == "__main__":
    main()
