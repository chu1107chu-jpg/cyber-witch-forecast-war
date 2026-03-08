"""Очистка, дедупликация и нормализация новостного датасета."""
import logging
from pathlib import Path

import pandas as pd
from langdetect import detect, LangDetectException

logger = logging.getLogger(__name__)

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def _parse_date(s: str) -> pd.Timestamp | None:
    try:
        return pd.to_datetime(s, utc=True)
    except Exception:
        return None


def _detect_lang(text: str) -> str:
    try:
        return detect(text[:200])
    except LangDetectException:
        return "unknown"


def clean(df: pd.DataFrame, allowed_langs: list[str] = ("en", "ru")) -> pd.DataFrame:
    # normalize timestamps
    df["published_at"] = df["published_at"].apply(_parse_date)
    df = df.dropna(subset=["published_at"])
    df = df.sort_values("published_at")

    # fill missing lang
    df["lang"] = df.apply(
        lambda r: r["lang"] if isinstance(r.get("lang"), str) and r["lang"] in allowed_langs
        else _detect_lang(str(r["title"])),
        axis=1,
    )

    # keep only allowed langs
    df = df[df["lang"].isin(allowed_langs)]

    # dedup by url
    df = df.drop_duplicates(subset=["url"])

    # dedup by title similarity (simple hash)
    df["title_norm"] = df["title"].str.lower().str.strip()
    df = df.drop_duplicates(subset=["title_norm"])
    df = df.drop(columns=["title_norm"])

    # text columns
    df["text"] = (df["title"].fillna("") + " " + df["description"].fillna("")).str.strip()

    return df.reset_index(drop=True)


def load_news(
    ticker: str,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Загрузить очищенные новости для API."""
    path = PROCESSED_DIR / "task_1_news.csv"
    if not path.exists():
        logger.warning("Processed news not found, returning []")
        return []
    df = pd.read_csv(path, parse_dates=["published_at"])
    if ticker:
        df = df[df["ticker"].astype(str).str.contains(ticker, case=False, na=False)]
    if from_date:
        df = df[df["published_at"] >= from_date]
    if to_date:
        df = df[df["published_at"] <= to_date]
    df = df.sort_values("published_at", ascending=False).head(limit)
    return df.to_dict("records")


def run():
    raw = RAW_DIR / "task_1_news_raw.csv"
    if not raw.exists():
        logger.error("Raw news not found. Run fetch_news first.")
        return
    df = pd.read_csv(raw)
    df = clean(df)
    out = PROCESSED_DIR / "task_1_news.csv"
    df.to_csv(out, index=False)
    logger.info(f"Cleaned news saved → {out} ({len(df)} rows)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
