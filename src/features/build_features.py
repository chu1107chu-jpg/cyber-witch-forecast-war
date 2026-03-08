"""Построение фич: market + news → train-ready датафрейм."""
import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ── Price features ────────────────────────────────────────────

def add_price_features(df: pd.DataFrame, windows: list[int] = (1, 3, 5, 10, 20, 60)) -> pd.DataFrame:
    df = df.copy().sort_values(["ticker", "Date"])
    df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
    # targets
    df["target_r1"] = df["log_return"].shift(-1)
    df["target_R20"] = (
        df["Close"].shift(-20) / df["Close"] - 1
    )
    df["target_p1_up"]  = (df["target_r1"]  > 0).astype(float)
    df["target_p20_up"] = (df["target_R20"] > 0).astype(float)

    for w in windows:
        df[f"roll_mean_{w}"] = df["log_return"].rolling(w).mean()
        df[f"roll_std_{w}"]  = df["log_return"].rolling(w).std()
        df[f"vol_{w}"]       = df["Volume"].rolling(w).mean()

    # RSI-14
    delta = df["log_return"]
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi_14"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    # MACD
    ema12 = df["Close"].ewm(span=12).mean()
    ema26 = df["Close"].ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()

    # ATR
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift(1)).abs()
    low_close  = (df["Low"]  - df["Close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()

    # Volume anomaly
    df["vol_anomaly"] = df["Volume"] / df["Volume"].rolling(20).mean()

    return df


# ── News features ─────────────────────────────────────────────

def add_news_features(
    price_df: pd.DataFrame,
    news_df: pd.DataFrame,
    half_life_h: float = 24.0,
) -> pd.DataFrame:
    """Присоединить агрегированные новостные фичи к ценовому датафрейму."""
    if news_df.empty:
        logger.warning("News dataframe is empty, skipping news features")
        return price_df

    price_df = price_df.copy()
    price_df["Date"] = pd.to_datetime(price_df["Date"]).dt.normalize()

    news_df = news_df.copy()
    news_df["published_at"] = pd.to_datetime(news_df["published_at"], utc=True)
    news_df["news_date"] = news_df["published_at"].dt.normalize().dt.tz_localize(None)

    results = []
    for _, row in price_df.iterrows():
        t = row["Date"]
        ticker = row["ticker"]
        # newsd до дня t (без утечки: news t-1)
        sub = news_df[
            (news_df["news_date"] < t) &
            (news_df["news_date"] >= t - pd.Timedelta(days=7))
        ]
        if "ticker" in news_df.columns:
            sub = sub[sub["ticker"].astype(str).str.contains(ticker, case=False, na=False) | (sub["ticker"] == "")]

        if sub.empty:
            results.append({"Date": t, "ticker": ticker,
                            "news_count": 0, "news_sent_mean": 0.0, "news_sent_impulse": 0.0,
                            "news_sent_chain_3": 0.0, "news_unique_sources": 0})
            continue

        # экспоненциальное затухание
        hours_ago = (t - sub["news_date"]).dt.total_seconds() / 3600
        weights = 0.5 ** (hours_ago / half_life_h)
        sent = sub.get("sentiment_score", pd.Series(0.0, index=sub.index)).fillna(0.0)

        results.append({
            "Date": t,
            "ticker": ticker,
            "news_count": len(sub),
            "news_sent_mean": float((sent * weights).sum() / weights.sum() if weights.sum() > 0 else 0),
            "news_sent_impulse": float(sent.abs().max()),
            "news_sent_chain_3": float(sent.rolling(3, min_periods=1).sum().iloc[-1]),
            "news_unique_sources": len(sub["source"].unique()) if "source" in sub.columns else 0,
        })

    news_feat = pd.DataFrame(results)
    price_df = price_df.merge(news_feat, on=["Date", "ticker"], how="left")
    return price_df


# ── Main ──────────────────────────────────────────────────────

def build_features() -> pd.DataFrame:
    candles = PROCESSED_DIR.parent / "raw" / "task_1_candles.csv"
    news_path = PROCESSED_DIR / "task_1_news.csv"

    if not candles.exists():
        raise FileNotFoundError(f"Candles not found: {candles}. Run fetch_quotes first.")

    price_df = pd.read_csv(candles)
    news_df = pd.read_csv(news_path) if news_path.exists() else pd.DataFrame()

    # add NLP sentiment if available
    if not news_df.empty and "sentiment_score" not in news_df.columns:
        try:
            from src.nlp.sentiment import score_df
            news_df = score_df(news_df, text_col="text")
        except Exception as e:
            logger.warning(f"NLP sentiment skipped: {e}")

    # per-ticker features
    parts = []
    for ticker in price_df["ticker"].unique():
        sub = price_df[price_df["ticker"] == ticker].copy()
        sub = add_price_features(sub)
        if not news_df.empty:
            sub = add_news_features(sub, news_df)
        parts.append(sub)

    full = pd.concat(parts, ignore_index=True)
    full = full.dropna(subset=["target_r1", "target_R20"])

    out = PROCESSED_DIR / "features.parquet"
    full.to_parquet(out, index=False)
    logger.info(f"Features saved → {out} ({len(full)} rows, {full.shape[1]} cols)")
    return full


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_features()
