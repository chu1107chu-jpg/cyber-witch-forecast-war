"""Аналитическая сводка: реакция рынка на 'крупные' новости за 5 лет."""
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
PROCESSED_DIR = Path("data/processed")


def analyze_big_news(ticker: str, lookback_years: int = 5, impact_threshold_std: float = 2.0) -> dict:
    """
    Находит торговые дни, когда return > N sigma (крупное событие),
    сопоставляет с новостями, строит сводку.
    """
    candles_path = Path("data/raw") / f"candles_{ticker.replace('-','_')}.parquet"
    news_path = PROCESSED_DIR / "task_1_news.csv"

    if not candles_path.exists():
        return {"error": "candles not found", "ticker": ticker}

    df = pd.read_parquet(candles_path)
    df = df.sort_values("Date")
    cutoff = df["Date"].max() - pd.DateOffset(years=lookback_years)
    df = df[df["Date"] >= cutoff].copy()
    df["log_return"] = np.log(df["Close"] / df["Close"].shift(1))
    df = df.dropna(subset=["log_return"])

    mu = df["log_return"].mean()
    sigma = df["log_return"].std()
    threshold = impact_threshold_std * sigma

    big_days = df[df["log_return"].abs() > threshold].copy()
    big_days["direction"] = big_days["log_return"].apply(lambda x: "up" if x > 0 else "down")

    # mean reaction windows
    windows = [1, 3, 5]
    reaction = {}
    for w in windows:
        df[f"fwd_{w}"] = df["log_return"].rolling(w).sum().shift(-w)
        reaction[f"mean_fwd_{w}"] = big_days.merge(
            df[["Date", f"fwd_{w}"]], on="Date", how="left"
        )[f"fwd_{w}"].mean()

    # match news
    news_around = []
    if news_path.exists():
        news_df = pd.read_csv(news_path, parse_dates=["published_at"])
        news_df["news_date"] = pd.to_datetime(news_df["published_at"]).dt.normalize()
        for _, row in big_days.iterrows():
            day = pd.Timestamp(row["Date"]).normalize()
            nearby = news_df[
                (news_df["news_date"] >= day - pd.Timedelta(days=1)) &
                (news_df["news_date"] <= day + pd.Timedelta(days=1))
            ]
            if not nearby.empty:
                top = nearby.nlargest(3, "sentiment_score") if "sentiment_score" in nearby.columns else nearby.head(3)
                news_around.append({
                    "date": str(day.date()),
                    "return": round(float(row["log_return"]), 4),
                    "direction": row["direction"],
                    "top_news": top["title"].tolist(),
                })

    return {
        "ticker": ticker,
        "lookback_years": lookback_years,
        "threshold_sigma": impact_threshold_std,
        "big_event_count": len(big_days),
        "up_count": int((big_days["direction"] == "up").sum()),
        "down_count": int((big_days["direction"] == "down").sum()),
        "mean_abs_return": round(float(big_days["log_return"].abs().mean()), 4),
        "reaction_windows": {k: round(v, 4) if not np.isnan(v) else None for k, v in reaction.items()},
        "events_with_news": news_around[:20],
    }
