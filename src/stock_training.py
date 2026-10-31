"""
stock_training.py
=================
Обучение LightGBM-модели направления акций. Один код для двух мест:

  * scripts/train_lgbm.py       — запуск вручную / из GitHub Actions
  * src/auto_retrain.py         — фоновое переобучение прямо внутри Streamlit-приложения
                                  (не требует ни GitHub Actions, ни платных серверов:
                                  Streamlit Cloud и так ходит за котировками в Yahoo)

Методология (честная, без утечек):
  1. Скользящий холд-аут: последние HOLDOUT_YEARS лет до сегодняшнего дня.
     Раньше граница была зашита константой (2023-12-31), из-за чего «переобучение»
     никогда не видело свежих данных — теперь окна считаются от сегодняшней даты.
  2. Таргеты p5/p20 смотрят на 5/20 дней вперёд, поэтому из train выкидываются строки,
     чьё окно метки заходит в холд-аут (purge), а в CV — ещё и embargo после
     validation-блока (Лопес де Прадо, "Advances in Financial ML").
  3. OOS-метрики считаются моделью, обученной ТОЛЬКО на train, с фиксированным числом
     деревьев — без early-stopping по холд-ауту (иначе холд-аут участвует в подборе модели
     и метрика получается завышенной).
  4. Боевая модель дообучается на ВСЕХ данных (train + холд-аут), чтобы знать самый
     свежий рынок. Метрики в summary относятся к честной модели из п.3.
  5. Артефакты пишутся атомарно (временная папка -> os.replace), поэтому приложение
     никогда не прочитает наполовину записанную модель.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import joblib
import numpy as np
import pandas as pd

from stock_features import FEATURE_COLS, build_features, fetch_macro_range

warnings.filterwarnings("ignore")

TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "BRK-B", "XOM", "JPM",
    "BTC-USD", "ETH-USD", "GC=F", "^GSPC", "^IXIC",
]
HISTORY_YEARS = 10
HOLDOUT_YEARS = 2
N_CV_FOLDS = 5
MIN_TICKERS = 8                                   # меньше — данные явно битые, не сохраняем
HORIZONS = {"target_p5_up": 5, "target_p20_up": 20}   # дней вперёд

LGB_PARAMS = dict(
    objective="binary", n_estimators=500, learning_rate=0.02,
    num_leaves=31, max_depth=5, min_child_samples=60,
    subsample=0.8, subsample_freq=1, colsample_bytree=0.7,
    reg_alpha=0.2, reg_lambda=2.0,
    random_state=42, verbose=-1,
)


# ─────────────────────────────────────────────
#  Purged & embargoed K-fold
# ─────────────────────────────────────────────
def purged_kfold_splits(train: pd.DataFrame, label_date_col: str, n_folds: int, embargo_days: int):
    """
    Список (train_mask, val_mask) — numpy bool-массивы по строкам train.
    train индексирован датами (на одну дату — много тикеров). label_date_col — дата,
    на которую «смотрит» таргет строки.

    Для каждого фолда validation — календарный блок дат; из train фолда убираются
    (а) строки validation, (б) строки, чьё окно метки попадает в validation (purge),
    (в) embargo_days торговых дней после validation-блока (embargo).
    """
    dates = np.sort(train.index.unique())
    idx_dates = train.index.values
    label_dates = train[label_date_col].values

    splits = []
    for block in np.array_split(dates, n_folds):
        if len(block) == 0:
            continue
        v_start, v_end = block[0], block[-1]
        val_mask = (idx_dates >= v_start) & (idx_dates <= v_end)

        end_pos = np.searchsorted(dates, v_end)
        embargo_end = dates[min(end_pos + embargo_days, len(dates) - 1)]

        purge_mask = (idx_dates < v_start) & (label_dates >= v_start) & (label_dates <= v_end)
        embargo_mask = (idx_dates > v_end) & (idx_dates <= embargo_end)
        splits.append((~val_mask & ~purge_mask & ~embargo_mask, val_mask))
    return splits


def run_purged_cv(train: pd.DataFrame, y_col: str, label_date_col: str,
                  embargo_days: int, params: dict) -> dict:
    import lightgbm as lgb
    from sklearn.metrics import accuracy_score, roc_auc_score

    aucs, accs = [], []
    for tr_mask, va_mask in purged_kfold_splits(train, label_date_col, N_CV_FOLDS, embargo_days):
        y_tr, y_va = train.loc[tr_mask, y_col].values, train.loc[va_mask, y_col].values
        if len(np.unique(y_tr)) < 2 or len(np.unique(y_va)) < 2:
            continue
        m = lgb.LGBMClassifier(**params).fit(train.loc[tr_mask, FEATURE_COLS].values, y_tr)
        p = m.predict_proba(train.loc[va_mask, FEATURE_COLS].values)[:, 1]
        aucs.append(roc_auc_score(y_va, p))
        accs.append(accuracy_score(y_va, (p >= 0.5).astype(int)))
    return {
        "cv_auc": round(float(np.mean(aucs)), 4) if aucs else None,
        "cv_acc": round(float(np.mean(accs)), 4) if accs else None,
        "cv_folds_auc": [round(float(a), 4) for a in aucs],
        "n_folds_used": len(aucs),
    }


# ─────────────────────────────────────────────
#  Проверка «стало ли лучше»: доверительные интервалы и сравнение с прежней моделью
# ─────────────────────────────────────────────
def block_bootstrap_auc(y: np.ndarray, probas: list, months: np.ndarray,
                        n_boot: int = 300, seed: int = 0) -> dict:
    """
    AUC каждой модели + 95%-интервалы (и интервал разницы AUC, если моделей две).
    Ресемплируем целыми МЕСЯЦАМИ: соседние дни и тикеры сильно коррелированы, поэтому
    ресемплинг отдельных строк давал бы слишком узкие (самообманные) интервалы.
    """
    from sklearn.metrics import roc_auc_score
    groups = np.unique(months)
    idx_by = {m: np.where(months == m)[0] for m in groups}
    rng = np.random.default_rng(seed)
    point = [float(roc_auc_score(y, p)) for p in probas]
    draws = []
    for _ in range(n_boot):
        pick = rng.choice(groups, len(groups), replace=True)
        ii = np.concatenate([idx_by[m] for m in pick])
        if len(np.unique(y[ii])) < 2:
            continue
        draws.append([roc_auc_score(y[ii], p[ii]) for p in probas])
    d = np.array(draws) if draws else np.zeros((0, len(probas)))
    out = {"auc": [round(v, 4) for v in point],
           "ci95": [[round(float(np.percentile(d[:, k], 2.5)), 4), round(float(np.percentile(d[:, k], 97.5)), 4)]
                    for k in range(len(probas))] if len(d) else None}
    if len(probas) == 2 and len(d):
        diff = d[:, 0] - d[:, 1]
        out["diff"] = round(point[0] - point[1], 4)
        out["diff_ci95"] = [round(float(np.percentile(diff, 2.5)), 4), round(float(np.percentile(diff, 97.5)), 4)]
    return out


def _parse_date(text: str):
    try:
        return pd.Timestamp(str(text).strip()[:10])
    except Exception:
        return None


def _champion_end(summary: dict):
    """Дата, по которую «чемпион» видел данные при обучении."""
    if summary.get("trained_through"):
        return _parse_date(summary["trained_through"])
    tp = summary.get("train_period", "")          # старый формат: '2016-01-01 → 2023-12-31'
    return _parse_date(tp.split("→")[-1]) if "→" in tp else None


def _load_champion(champion_dir):
    if not champion_dir:
        return None
    d = Path(champion_dir)
    try:
        models = joblib.load(d / "models.pkl")
        feats = joblib.load(d / "feature_cols.pkl")
        with open(d / "train_summary.json", encoding="utf-8") as f:
            summ = json.load(f)
    except Exception:
        return None
    return {"models": models, "feats": list(feats), "summary": summ, "end": _champion_end(summ)}


# ─────────────────────────────────────────────
#  Данные
# ─────────────────────────────────────────────
def _download_prices(start: str, end: str, log: Callable[[str], None]):
    import yfinance as yf

    frames = []
    for t in TICKERS:
        try:
            df = yf.download(t, start=start, end=end, auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df = df.dropna()
        except Exception as e:                      # сеть / лимиты Yahoo — пропускаем тикер
            log(f"  {t}: ошибка загрузки ({type(e).__name__})")
            continue
        if len(df) < 300:
            log(f"  {t}: пропущен (мало данных: {len(df)})")
            continue
        frames.append((t, df))
        log(f"  {t}: {len(df)} строк")
    return frames


def _build_dataset(frames, macro: pd.DataFrame) -> pd.DataFrame:
    built = []
    for t, df in frames:
        d = build_features(df, macro)
        close = df["Close"].reindex(d.index)
        for target, h in HORIZONS.items():
            y = target.replace("target_", "y_")
            # метка = рост цены через h торговых дней; считаем по полному ряду df, чтобы не
            # терять хвост из-за dropna в build_features
            fwd = df["Close"].shift(-h).reindex(d.index)
            d[y] = np.where(fwd.isna(), np.nan, (fwd > close).astype(float))
            d[f"label_date_{h}"] = df.index.to_series().shift(-h).reindex(d.index)
        d["ticker"] = t
        built.append(d.dropna())      # последние h строк без метки отбрасываются
    return pd.concat(built).sort_index()


# ─────────────────────────────────────────────
#  Основная функция
# ─────────────────────────────────────────────
def train_all(artifacts_dir: str | Path, *, run_cv: bool = True, n_jobs: int = -1,
              log: Callable[[str], None] = print, today: datetime | None = None,
              champion_dir: str | Path | None = None, guard: bool = True) -> dict:
    """
    Обучает обе модели и атомарно сохраняет артефакты в artifacts_dir. Возвращает summary.

    champion_dir — папка действующей модели: новая («претендент») сравнивается с ней на одних и тех же
    данных, которых не видела НИ ОДНА из двух. Если претендент значимо хуже (весь 95%-интервал разницы
    AUC ниже нуля) и guard=True — артефакты не перезаписываются (summary['promoted'] = False).
    """
    import lightgbm as lgb
    from sklearn.metrics import accuracy_score, roc_auc_score

    t0 = time.time()
    artifacts_dir = Path(artifacts_dir)
    now = today or datetime.now(timezone.utc)
    end_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=365 * HISTORY_YEARS)).strftime("%Y-%m-%d")
    split_date = pd.Timestamp((now - timedelta(days=365 * HOLDOUT_YEARS)).strftime("%Y-%m-%d"))
    params = {**LGB_PARAMS, "n_jobs": n_jobs}

    log(f"Загружаю котировки {start_date} … {end_date}")
    frames = _download_prices(start_date, end_date, log)
    if len(frames) < MIN_TICKERS:
        raise RuntimeError(f"Загрузилось только {len(frames)} тикеров из {len(TICKERS)} — "
                           f"обучение отменено, старая модель остаётся.")
    log("Загружаю макро (VIX/TNX/DXY)…")
    macro = fetch_macro_range(start_date, end_date)
    if macro is None or macro.empty or macro.shape[1] < 3:
        raise RuntimeError("Макро-данные (VIX/TNX/DXY) не загрузились — обучение отменено.")

    data = _build_dataset(frames, macro)
    if data.empty or data["ticker"].nunique() < MIN_TICKERS:
        raise RuntimeError("После построения признаков осталось слишком мало тикеров.")
    log(f"Итого {len(data)} строк, {data['ticker'].nunique()} тикеров, {len(FEATURE_COLS)} признаков")

    test = data[data.index >= split_date]
    if len(test) < 500:
        raise RuntimeError(f"Холд-аут слишком мал ({len(test)} строк).")

    champ = _load_champion(champion_dir)
    final_models, metrics, champ_cmp = {}, {}, {}
    for target, h in HORIZONS.items():
        y_col, ld_col = target.replace("target_", "y_"), f"label_date_{h}"
        # purge: в train — только строки, чьё окно метки закончилось ДО начала холд-аута
        train = data[(data.index < split_date) & (data[ld_col] < split_date)]
        log(f"\n=== {target} (горизонт {h} дн.): train={len(train)}, holdout={len(test)} ===")

        cv = run_purged_cv(train, y_col, ld_col, h, params) if run_cv else {}
        if cv:
            log(f"  Purged CV AUC {cv['cv_auc']}  acc {cv['cv_acc']}  (фолдов {cv['n_folds_used']})")

        # честная модель: только train, фиксированное число деревьев, без early-stopping
        honest = lgb.LGBMClassifier(**params).fit(train[FEATURE_COLS].values, train[y_col].astype(int).values)
        proba = honest.predict_proba(test[FEATURE_COLS].values)[:, 1]
        y_te = test[y_col].astype(int).values
        oos_auc = float(roc_auc_score(y_te, proba))
        oos_acc = float(accuracy_score(y_te, (proba >= 0.5).astype(int)))
        thr = np.percentile(np.abs(proba - 0.5), 70)
        conf = np.abs(proba - 0.5) >= thr
        oos_conf = float(accuracy_score(y_te[conf], (proba[conf] >= 0.5).astype(int)))
        ci = block_bootstrap_auc(y_te, [proba], test.index.to_period("M").astype(str).values)
        base_up = float(y_te.mean())
        log(f"  OOS AUC {oos_auc:.4f} [95% ДИ {ci['ci95'][0][0]:.3f}–{ci['ci95'][0][1]:.3f}] | acc {oos_acc:.1%} "
            f"(тривиальная «всегда вверх/вниз»: {max(base_up, 1 - base_up):.1%}) | уверенные топ-30%: {oos_conf:.1%}")

        # честное сравнение с действующей моделью: только на датах, которых не видела НИ ОДНА из двух
        if champ and champ["end"] is not None and champ["feats"] == FEATURE_COLS and target in champ["models"]:
            start = max(split_date, champ["end"] + pd.Timedelta(days=30))
            win = test[test.index >= start]
            yw = win[y_col].astype(int).values if len(win) else np.array([])
            if len(win) >= 500 and len(np.unique(yw)) == 2:
                p_new = honest.predict_proba(win[FEATURE_COLS].values)[:, 1]
                p_old = champ["models"][target].predict_proba(win[champ["feats"]].values)[:, 1]
                cmp = block_bootstrap_auc(yw, [p_new, p_old], win.index.to_period("M").astype(str).values)
                champ_cmp[target] = {
                    "window": f"{start.date()} → {win.index.max().date()}", "n": int(len(win)),
                    "new_auc": cmp["auc"][0], "old_auc": cmp["auc"][1],
                    "diff": cmp["diff"], "diff_ci95": cmp["diff_ci95"],
                    "old_trained_at": champ["summary"].get("trained_at"),
                }
                log(f"  Новая vs прежняя на {champ_cmp[target]['window']}: {cmp['auc'][0]:.4f} vs {cmp['auc'][1]:.4f}, "
                    f"разница {cmp['diff']:+.4f} [95% ДИ {cmp['diff_ci95'][0]:+.3f}…{cmp['diff_ci95'][1]:+.3f}]")

        # боевая модель: все данные, у которых уже есть метка
        full = lgb.LGBMClassifier(**params).fit(data[FEATURE_COLS].values, data[y_col].astype(int).values)
        final_models[target] = full

        metrics[target] = {
            **cv,
            "oos_auc": round(oos_auc, 4),
            "oos_auc_ci95": ci["ci95"][0],
            "oos_acc": round(oos_acc, 4),
            "oos_acc_baseline": round(max(base_up, 1 - base_up), 4),
            "oos_base_rate_up": round(base_up, 4),
            "oos_acc_confident_top30": round(oos_conf, 4),
            "oos_total_samples": int(len(y_te)),
            "top_features": sorted(zip(FEATURE_COLS, honest.feature_importances_.tolist()),
                                   key=lambda kv: kv[1], reverse=True)[:10],
        }

    # охрана от регресса: не заменяем действующую модель, если новая ЗНАЧИМО хуже
    # (весь 95%-интервал разницы AUC ниже нуля хотя бы по одному таргету)
    clearly_worse = [t for t, c in champ_cmp.items() if c["diff_ci95"][1] < 0]
    promoted = not (guard and clearly_worse)

    summary = {
        "model_type": "LightGBM, скользящий холд-аут + purged/embargoed CV, финальный рефит на всех данных",
        "trained_at": now.isoformat(),
        "trained_through": str(data.index.max().date()),
        "promoted": promoted,
        "tickers": [t for t, _ in frames],
        "n_tickers": len(frames),
        "n_samples": int(len(data)),
        "n_features": len(FEATURE_COLS),
        "feature_cols": FEATURE_COLS,
        "data_period": f"{start_date} → {end_date}",
        "holdout_from": str(split_date.date()),
        "targets": list(HORIZONS.keys()),
        "metrics": metrics,
        "vs_champion": champ_cmp,
        "lgb_params": params,
        "elapsed_sec": round(time.time() - t0, 1),
        "note": ("Метрики oos_* посчитаны моделью, обученной только на данных до holdout_from, "
                 "без подбора по холд-ауту. Боевая модель (models.pkl) дообучена на всех данных."),
    }

    _append_history(artifacts_dir, summary)
    if promoted:
        _save_atomic(artifacts_dir, final_models, summary)
        log(f"\nГотово за {summary['elapsed_sec']} с → {artifacts_dir}")
    else:
        log(f"\nНовая модель ЗНАЧИМО хуже действующей по {clearly_worse} — не заменяю. Запись добавлена в историю.")
    return summary


def _history_entry(summary: dict) -> dict:
    return {
        "trained_at": summary["trained_at"], "trained_through": summary.get("trained_through"),
        "status": "promoted" if summary.get("promoted", True) else "rejected",
        "n_samples": summary.get("n_samples"),
        "targets": {t: {k: m.get(k) for k in ("oos_auc", "oos_auc_ci95", "oos_acc", "oos_acc_baseline", "cv_auc")}
                    for t, m in summary["metrics"].items()},
        "vs_champion": {t: {k: c.get(k) for k in ("window", "n", "new_auc", "old_auc", "diff", "diff_ci95")}
                        for t, c in (summary.get("vs_champion") or {}).items()},
    }


def _append_history(artifacts_dir: Path, summary: dict, keep: int = 50) -> None:
    """Журнал всех переобучений (train_history.json рядом с артефактами)."""
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = artifacts_dir / "train_history.json"
    try:
        hist = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        hist = []
    hist.append(_history_entry(summary))
    path.write_text(json.dumps(hist[-keep:], indent=2, ensure_ascii=False), encoding="utf-8")


def _save_atomic(artifacts_dir: Path, models: dict, summary: dict) -> None:
    artifacts_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".lgbm_new_", dir=artifacts_dir.parent))
    try:
        joblib.dump(models, tmp / "models.pkl")
        joblib.dump(FEATURE_COLS, tmp / "feature_cols.pkl")
        with open(tmp / "train_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        # summary последним — по нему приложение понимает, что набор целый
        for name in ("models.pkl", "feature_cols.pkl", "train_summary.json"):
            os.replace(tmp / name, artifacts_dir / name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
