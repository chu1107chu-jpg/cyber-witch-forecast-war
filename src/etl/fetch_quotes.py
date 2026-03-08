"""Загрузка котировок: yfinance (акции/ETF) и CoinGecko (крипта)."""
import argparse
import logging
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)
RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


def fetch_yfinance(tickers: list[str], period: str = "10y") -> pd.DataFrame:
    """Скачать OHLCV через yfinance."""
    frames = []
    for ticker in tickers:
        logger.info(f"[yfinance] {ticker}...")
        df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
        df.reset_index(inplace=True)
        df["ticker"] = ticker
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_candles(ticker: str, window: int = 120) -> list[dict]:
    """Загрузить кэшированные свечи для API (или скачать на лету)."""
    path = RAW_DIR / f"candles_{ticker.replace('-','_')}.parquet"
    if path.exists():
        df = pd.read_parquet(path)
    else:
        df = fetch_yfinance([ticker])
    df = df[df["ticker"] == ticker].tail(window)
    return df[["Date", "Open", "High", "Low", "Close", "Volume"]].rename(
        columns={"Date": "date", "Open": "open", "High": "high",
                 "Low": "low", "Close": "close", "Volume": "volume"}
    ).to_dict("records")


def run(tickers: list[str]):
    df = fetch_yfinance(tickers)
    for ticker in tickers:
        sub = df[df["ticker"] == ticker].copy()
        out = RAW_DIR / f"candles_{ticker.replace('-','_')}.parquet"
        sub.to_parquet(out, index=False)
        logger.info(f"  saved {out} ({len(sub)} rows)")
    # unified CSV for pipeline
    out_csv = RAW_DIR / "task_1_candles.csv"
    df.to_csv(out_csv, index=False)
    logger.info(f"Combined CSV saved → {out_csv}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", default="AAPL,MSFT,BTC-USD")
    args = parser.parse_args()
    run(args.tickers.split(","))
