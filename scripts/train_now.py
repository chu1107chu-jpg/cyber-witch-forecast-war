"""
Standalone training script.
Downloads price data → builds features → trains sklearn ensemble.
Run: python3 scripts/train_now.py
"""
import warnings, os, json, time
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import joblib
import yfinance as yf
from pathlib import Path
from sklearn.linear_model import Ridge, ElasticNet
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, StackingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, roc_auc_score

# ── CONFIG ────────────────────────────────────────────────────────────────────
TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "BRK-B", "XOM", "JPM",
    "BTC-USD", "ETH-USD",
    "GC=F",   # Gold
    "^GSPC",  # S&P 500
    "^IXIC",  # NASDAQ
    # MOEX
    "SBER.ME", "GAZP.ME", "LKOH.ME", "NVTK.ME", "ROSN.ME",
    "GMKN.ME", "YNDX.ME", "MGNT.ME", "MTSS.ME", "ALRS.ME",
    "TATN.ME", "PIKK.ME", "PLZL.ME", "RTKM.ME", "VTBR.ME",
]
PERIOD  = "7y"
OUTDIR  = Path(__file__).resolve().parent.parent / "data" / "artifacts" / "sklearn"
RAWDIR  = Path(__file__).resolve().parent.parent / "data" / "raw"
OUTDIR.mkdir(parents=True, exist_ok=True)
RAWDIR.mkdir(parents=True, exist_ok=True)

# ── HELPERS ───────────────────────────────────────────────────────────────────
def rsi(series, n=14):
    delta = series.diff()
    gain  = delta.clip(lower=0).rolling(n).mean()
    loss  = (-delta.clip(upper=0)).rolling(n).mean()
    rs    = gain / (loss + 1e-9)
    return 100 - 100 / (1 + rs)

def macd(series, fast=12, slow=26, sig=9):
    ema_f = series.ewm(span=fast, adjust=False).mean()
    ema_s = series.ewm(span=slow, adjust=False).mean()
    m     = ema_f - ema_s
    s     = m.ewm(span=sig, adjust=False).mean()
    return m - s   # histogram

def atr(high, low, close, n=14):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n).mean()

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    c = df["Close"]
    h = df["High"]
    l = df["Low"]
    v = df["Volume"]

    out = pd.DataFrame(index=df.index)
    # returns
    out["ret1"]   = c.pct_change(1)
    out["ret3"]   = c.pct_change(3)
    out["ret5"]   = c.pct_change(5)
    out["ret10"]  = c.pct_change(10)
    out["ret20"]  = c.pct_change(20)
    out["log_ret1"]= np.log1p(out["ret1"])
    # momentum
    out["rsi14"]  = rsi(c, 14)
    out["macd_h"] = macd(c)
    out["atr14"]  = atr(h, l, c, 14) / (c + 1e-9)
    # volatility
    out["vol10"]  = out["log_ret1"].rolling(10).std()
    out["vol20"]  = out["log_ret1"].rolling(20).std()
    out["vol_ratio"] = out["vol10"] / (out["vol20"] + 1e-9)
    # price position
    out["dist_hi52"] = c / c.rolling(252).max()
    out["dist_lo52"] = c / c.rolling(252).min()
    out["ma50_ratio"]= c / c.rolling(50).mean()
    out["ma200_ratio"]= c / c.rolling(200).mean()
    # volume
    if v.sum() > 0:
        out["vol_rel"] = v / (v.rolling(20).mean() + 1e-9)
    else:
        out["vol_rel"] = 1.0
    # TARGETS
    out["target_r1"]    = c.shift(-1).pct_change(1).shift(1)   # 1-day fwd return
    out["target_R20"]   = c.shift(-20).pct_change(20).shift(20) # 20-day fwd return
    out["target_p1_up"] = (out["target_r1"] > 0).astype(float)
    out["target_p20_up"]= (out["target_R20"] > 0).astype(float)
    return out.dropna()

# ── STEP 1: DOWNLOAD DATA ─────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  STEP 1 — Downloading {len(TICKERS)} tickers × {PERIOD}")
print(f"{'='*60}")

all_frames = []
for ticker in TICKERS:
    print(f"  ↓ {ticker:<12}", end=" ", flush=True)
    try:
        raw = yf.download(ticker, period=PERIOD, interval="1d",
                          auto_adjust=True, progress=False)
        if raw.empty or len(raw) < 300:
            print("⚠ too short, skip")
            continue
        # flatten MultiIndex if present
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        raw["ticker"] = ticker
        raw.to_parquet(RAWDIR / f"{ticker.replace('/', '_')}.parquet")
        all_frames.append(raw)
        print(f"✓  {len(raw)} rows")
    except Exception as e:
        print(f"✗ {e}")

if not all_frames:
    raise RuntimeError("No data downloaded — check internet connection")

# ── STEP 2: BUILD FEATURES ────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  STEP 2 — Building features")
print(f"{'='*60}")

feat_frames = []
for df in all_frames:
    ticker = df["ticker"].iloc[0]
    try:
        df2 = df.drop(columns=["ticker"])
        f   = build_features(df2)
        f["ticker"] = ticker
        feat_frames.append(f)
        print(f"  ✓ {ticker:<12} {len(f)} samples, {f.shape[1]} features")
    except Exception as e:
        print(f"  ✗ {ticker}: {e}")

combined = pd.concat(feat_frames).dropna()
print(f"\n  Total samples: {len(combined):,}")

FEATURE_COLS = [c for c in combined.columns
                if not c.startswith("target_") and c != "ticker"]
TARGET_COLS  = ["target_r1", "target_R20", "target_p1_up", "target_p20_up"]

X = combined[FEATURE_COLS].astype(float)
print(f"  Feature matrix: {X.shape}")

# ── STEP 3: TRAIN MODELS ──────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  STEP 3 — Training models")
print(f"{'='*60}")

tscv     = TimeSeriesSplit(n_splits=5)
metrics  = {}
t0_total = time.time()

def make_stack_reg():
    return StackingRegressor(
        estimators=[
            ("ridge",  Ridge(alpha=1.0)),
            ("en",     ElasticNet(alpha=0.01, l1_ratio=0.5, max_iter=2000)),
            ("rf",     RandomForestRegressor(n_estimators=80, max_depth=8, n_jobs=-1, random_state=42)),
            ("et",     ExtraTreesRegressor(n_estimators=80, max_depth=8, n_jobs=-1, random_state=42)),
        ],
        final_estimator=Ridge(alpha=0.5),
        cv=3, n_jobs=-1,
    )

artifacts = {}

for target in TARGET_COLS:
    y = combined[target].astype(float)
    t0 = time.time()

    is_clf = target.startswith("target_p")
    print(f"\n  ── {target} ({'classification' if is_clf else 'regression'}) ──")

    val_scores = []
    final_model = None

    for fold, (tr_idx, val_idx) in enumerate(tscv.split(X)):
        X_tr, X_val = X.iloc[tr_idx], X.iloc[val_idx]
        y_tr, y_val = y.iloc[tr_idx], y.iloc[val_idx]

        if is_clf:
            model = Pipeline([
                ("scaler", StandardScaler()),
                ("clf",    LogisticRegression(C=1.0, max_iter=500, n_jobs=-1, random_state=42)),
            ])
        else:
            model = Pipeline([
                ("scaler", StandardScaler()),
                ("reg",    make_stack_reg()),
            ])

        model.fit(X_tr, y_tr)
        preds = model.predict(X_val)

        if is_clf:
            try:   score = roc_auc_score(y_val, preds)
            except: score = 0.5
            metric_name = "roc_auc"
        else:
            score = mean_absolute_error(y_val, preds)
            metric_name = "mae"

        val_scores.append(score)
        if fold == 4:   # keep last fold model
            final_model = model

    mean_score = float(np.mean(val_scores))
    metrics[target] = {metric_name: round(mean_score, 5),
                       "folds": [round(s, 5) for s in val_scores]}
    elapsed = time.time() - t0

    icon = "✓" if (is_clf and mean_score > 0.52) or (not is_clf and mean_score < 0.03) else "~"
    print(f"  {icon} {metric_name}={mean_score:.5f}  ({elapsed:.1f}s)")

    artifacts[target] = final_model

# ── STEP 4: SAVE ARTIFACTS ────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  STEP 4 — Saving artifacts")
print(f"{'='*60}")

joblib.dump(artifacts,     OUTDIR / "models.pkl")
joblib.dump(FEATURE_COLS,  OUTDIR / "feature_cols.pkl")

summary = {
    "tickers":       TICKERS,
    "n_samples":     len(combined),
    "n_features":    len(FEATURE_COLS),
    "feature_cols":  FEATURE_COLS,
    "metrics":       metrics,
    "elapsed_total": round(time.time() - t0_total, 1),
}
with open(OUTDIR / "train_summary.json", "w") as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print(f"  ✓ models.pkl         → {OUTDIR}/models.pkl")
print(f"  ✓ feature_cols.pkl   → {OUTDIR}/feature_cols.pkl")
print(f"  ✓ train_summary.json → {OUTDIR}/train_summary.json")

# ── SUMMARY ───────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  ✅ TRAINING COMPLETE  ({summary['elapsed_total']}s)")
print(f"{'='*60}")
print(f"  Tickers   : {len(TICKERS)}")
print(f"  Samples   : {summary['n_samples']:,}")
print(f"  Features  : {summary['n_features']}")
print()
for tgt, m in metrics.items():
    k = list(m.keys())[0]
    print(f"  {tgt:<22} {k}={m[k]:.5f}")
print()
