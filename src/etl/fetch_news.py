"""Загрузка новостей: NewsAPI, Alpha Vantage, RSS-ленты."""
import argparse
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import feedparser
import requests
import pandas as pd
from src.utils.config import load_news_config

logger = logging.getLogger(__name__)
RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


def rate_limited(delay: float = 1.5):
    """Декоратор-задержка."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            result = fn(*args, **kwargs)
            time.sleep(delay)
            return result
        return wrapper
    return decorator


def fetch_newsapi(ticker: str, api_key: str) -> list[dict]:
    url = "https://newsapi.org/v2/everything"
    params = {"q": ticker, "sortBy": "publishedAt", "pageSize": 100, "language": "en"}
    resp = requests.get(url, params=params, headers={"X-Api-Key": api_key}, timeout=15)
    resp.raise_for_status()
    articles = resp.json().get("articles", [])
    return [
        {
            "ticker": ticker,
            "title": a.get("title", ""),
            "description": a.get("description", ""),
            "url": a.get("url", ""),
            "published_at": a.get("publishedAt", ""),
            "source": a.get("source", {}).get("name", ""),
            "lang": "en",
        }
        for a in articles
    ]


def fetch_alpha_vantage(ticker: str, api_key: str) -> list[dict]:
    url = "https://www.alphavantage.co/query"
    params = {"function": "NEWS_SENTIMENT", "tickers": ticker, "limit": 200, "apikey": api_key}
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    feed = resp.json().get("feed", [])
    return [
        {
            "ticker": ticker,
            "title": a.get("title", ""),
            "description": a.get("summary", ""),
            "url": a.get("url", ""),
            "published_at": a.get("time_published", ""),
            "source": a.get("source", ""),
            "lang": "en",
            "sentiment_label": a.get("overall_sentiment_label", ""),
            "sentiment_score": a.get("overall_sentiment_score", None),
        }
        for a in feed
    ]


def fetch_rss_feeds(feeds: list[dict]) -> list[dict]:
    rows = []
    for feed in feeds:
        try:
            parsed = feedparser.parse(feed["url"])
            for e in parsed.entries:
                rows.append({
                    "ticker": "",
                    "title": e.get("title", ""),
                    "description": e.get("summary", ""),
                    "url": e.get("link", ""),
                    "published_at": e.get("published", ""),
                    "source": feed["name"],
                    "lang": feed.get("lang", "en"),
                })
            time.sleep(0.5)
        except Exception as exc:
            logger.warning(f"RSS error {feed['name']}: {exc}")
    return rows


def run(tickers: list[str], crypto: list[str] | None = None):
    import os
    cfg = load_news_config()
    rows: list[dict] = []

    newsapi_key = os.getenv("NEWS_API_KEY", "")
    av_key = os.getenv("ALPHA_VANTAGE_KEY", "")

    for ticker in (tickers + (crypto or [])):
        if newsapi_key and cfg["apis"]["newsapi"]["enabled"]:
            try:
                rows += fetch_newsapi(ticker, newsapi_key)
                time.sleep(cfg["apis"]["newsapi"]["delay_sec"])
            except Exception as e:
                logger.error(f"NewsAPI error: {e}")

        if av_key and cfg["apis"]["alpha_vantage"]["enabled"]:
            try:
                rows += fetch_alpha_vantage(ticker, av_key)
                time.sleep(cfg["apis"]["alpha_vantage"]["delay_sec"])
            except Exception as e:
                logger.error(f"AlphaVantage error: {e}")

    # RSS
    rows += fetch_rss_feeds(cfg["rss"]["feeds"])

    df = pd.DataFrame(rows)
    out = RAW_DIR / "task_1_news_raw.csv"
    df.to_csv(out, index=False)
    logger.info(f"News raw saved → {out} ({len(df)} rows)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", default="AAPL,MSFT")
    parser.add_argument("--crypto", default="BTC,ETH")
    args = parser.parse_args()
    run(args.tickers.split(","), args.crypto.split(","))
