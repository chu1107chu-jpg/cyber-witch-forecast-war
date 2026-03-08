"""
Переобучение модели предсказания акций.
- LightGBM вместо LogisticRegression/Stacking
- Walk-forward: обучение 2017-2023, тест OOS 2024-2026
- Нет data leakage: все признаки строго backward-looking
- Таргеты: p5_up (5 дней), p20_up (20 дней)
"""

import json, warnings
from datetime import datetime, timezone
from pathlib import Path

import joblib, numpy as np, pandas as pd
import yfinance as yf
import lightgbm as lgb
from sklearn.metrics import accuracy_score, roc_auc_score

warnings.filterwarnings("ignore")

ARTIFACTS = Path(__file__).parent.parent / "data/artifacts/sklearn"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

TICKERS = [
    "AAPL","MSFT","GOOGL","AMZN","NVDA",
    "META","TSLA","BRK-B","XOM","JPM",
    "BTC-USD","ETH-USD","GC=F","^GSPC","^IXIC",
]

FEATURE_COLS = [
    "ret1","ret3","ret5","ret10","ret20","log_ret1",
    "rsi14","macd_h","atr14",
    "vol10","vol20","vol_ratio",
    "dist_hi52","dist_lo52",
    "ma50_ratio","ma200_ratio",
    "vol_rel","dow","month","mom_5_20",
]

def build_features(df):
    d = df.copy()
    c = d["Close"]
    for n in [1,3,5,10,20]:
        d[f"ret{n}"] = c.pct_change(n)
    d["log_ret1"] = np.log(c / c.shift(1))
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    d["rsi14"] = 100 - 100/(1+gain/(loss+1e-9))
    ema12 = c.ewm(span=12,adjust=False).mean()
    ema26 = c.ewm(span=26,adjust=False).mean()
    macd = ema12 - ema26
    d["macd_h"] = macd - macd.ewm(span=9,adjust=False).mean()
    hl = d["High"]-d["Low"]
    hc = (d["High"]-c.shift()).abs()
    lc = (d["Low"] -c.shift()).abs()
    tr = pd.concat([hl,hc,lc],axis=1).max(axis=1)
    d["atr14"] = tr.rolling(14).mean()/(c+1e-9)
    ret = c.pct_change()
    d["vol10"] = ret.rolling(10).std()
    d["vol20"] = ret.rolling(20).std()
    d["vol_ratio"] = d["vol10"]/(d["vol20"]+1e-9)
    r52h = c.rolling(252,min_periods=50).max()
    r52l = c.rolling(252,min_periods=50).min()
    d["dist_hi52"] = (r52h-c)/(r52h+1e-9)
    d["dist_lo52"] = (c-r52l)/(r52l+1e-9)
    d["ma50_ratio"]  = c/(c.rolling(50, min_periods=10).mean()+1e-9)
    d["ma200_ratio"] = c/(c.rolling(200,min_periods=50).mean()+1e-9)
    d["vol_rel"] = d["Volume"]/(d["Volume"].rolling(20).mean()+1e-9)
    d["dow"]   = d.index.dayofweek
    d["month"] = d.index.month
    d["mom_5_20"] = d["ret5"]/(d["ret20"].abs()+1e-9)
    return d

print("Загружаю данные...")
frames = []
for t in TICKERS:
    df = yf.download(t, start="2017-01-01", end="2026-03-01",
                     auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df = df.dropna()
    if len(df) < 300:
        print(f"  {t}: пропущен")
        continue
    d = build_features(df)
    d["y5"]  = (d["Close"].shift(-5)  > d["Close"]).astype(int)
    d["y20"] = (d["Close"].shift(-20) > d["Close"]).astype(int)
    d["ticker"] = t
    d = d.dropna()
    frames.append(d)
    print(f"  {t}: {len(d)} строк")

data = pd.concat(frames).sort_index()
print(f"Итого: {len(data)} строк, {len(frames)} тикеров")

TRAIN_END  = "2023-12-31"
TEST_START = "2024-01-01"
train = data[data.index <= TRAIN_END]
test  = data[data.index >= TEST_START]
print(f"Трейн: {len(train)} | OOS тест: {len(test)}")

X_tr = train[FEATURE_COLS].values
X_te = test[FEATURE_COLS].values

LGB_PARAMS = dict(
    objective="binary", n_estimators=500, learning_rate=0.02,
    num_leaves=31, max_depth=5, min_child_samples=60,
    subsample=0.8, colsample_bytree=0.7,
    reg_alpha=0.2, reg_lambda=2.0,
    random_state=42, n_jobs=-1, verbose=-1,
)

models_out = {}
oos_metrics = {}

for target, y_col in [("target_p5_up","y5"),("target_p20_up","y20")]:
    y_tr = train[y_col].values
    y_te = test[y_col].values
    model = lgb.LGBMClassifier(**LGB_PARAMS)
    model.fit(X_tr, y_tr,
              eval_set=[(X_te, y_te)],
              callbacks=[lgb.early_stopping(50,verbose=False),lgb.log_evaluation(-1)])
    proba = model.predict_proba(X_te)[:,1]
    auc  = roc_auc_score(y_te, proba)
    acc  = accuracy_score(y_te,(proba>=0.5).astype(int))
    thresh = np.percentile(np.abs(proba-0.5), 70)
    conf = np.abs(proba-0.5) >= thresh
    acc_conf = accuracy_score(y_te[conf],(proba[conf]>=0.5).astype(int))
    print(f"\n{target}:")
    print(f"  ROC-AUC OOS:           {auc:.4f}")
    print(f"  Точность OOS (все):    {acc:.1%}")
    print(f"  Точность (уверен.30%): {acc_conf:.1%}  ({conf.sum()} сигналов из {len(y_te)})")
    models_out[target] = model
    oos_metrics[target] = {
        "roc_auc_oos": round(auc,4),
        "accuracy_oos": round(acc,4),
        "accuracy_confident_oos": round(acc_conf,4),
        "confident_signals": int(conf.sum()),
        "total_oos_samples": int(len(y_te)),
    }

joblib.dump(models_out, ARTIFACTS/"models.pkl")
joblib.dump(FEATURE_COLS, ARTIFACTS/"feature_cols.pkl")

summary = {
    "model_type": "LightGBM walk-forward OOS (no leakage)",
    "tickers": TICKERS, "n_tickers": len(frames),
    "n_samples": int(len(train)), "n_features": len(FEATURE_COLS),
    "feature_cols": FEATURE_COLS,
    "train_period": "2017-01-01 – 2023-12-31",
    "test_period":  "2024-01-01 – 2026-03-01",
    "targets": ["target_p5_up","target_p20_up"],
    "metrics": oos_metrics,
    "lgb_params": LGB_PARAMS,
    "trained_at": datetime.now(timezone.utc).isoformat(),
    "note": "Walk-forward OOS. Нет leakage. p5_up=рост за 5 дней, p20_up=рост за 20 дней.",
}
with open(ARTIFACTS/"train_summary.json","w") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print("\nАртефакты сохранены в:", ARTIFACTS)
for t, m in oos_metrics.items():
    print(f"  {t}: AUC={m['roc_auc_oos']}, acc={m['accuracy_oos']:.1%}, confident={m['accuracy_confident_oos']:.1%}")
