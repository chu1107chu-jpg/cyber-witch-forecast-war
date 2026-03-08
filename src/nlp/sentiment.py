"""Sentiment scoring — FinBERT (en) / RuBERT-tiny (ru), CPU-friendly."""
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_pipeline_cache: dict = {}


def _get_pipeline(lang: str = "en"):
    if lang in _pipeline_cache:
        return _pipeline_cache[lang]
    from transformers import pipeline as hf_pipeline
    if lang == "ru":
        model_name = "blanchefort/rubert-base-cased-sentiment"
    else:
        model_name = "ProsusAI/finbert"
    logger.info(f"Loading sentiment model {model_name}…")
    pipe = hf_pipeline(
        "text-classification",
        model=model_name,
        device=-1,         # CPU
        truncation=True,
        max_length=128,
    )
    _pipeline_cache[lang] = pipe
    return pipe


def score_texts(texts: list[str], lang: str = "en") -> list[float]:
    """Возвращает список float: +1 positive, -1 negative, 0 neutral."""
    pipe = _get_pipeline(lang)
    results = pipe(texts, batch_size=32)
    scores = []
    for r in results:
        label = r["label"].lower()
        score = r["score"]
        if "positive" in label or "pos" in label:
            scores.append(score)
        elif "negative" in label or "neg" in label:
            scores.append(-score)
        else:
            scores.append(0.0)
    return scores


def score_df(df: pd.DataFrame, text_col: str = "text") -> pd.DataFrame:
    """Добавляет колонку sentiment_score к датафрейму."""
    df = df.copy()
    df["sentiment_score"] = 0.0

    # split by language
    for lang in ("en", "ru"):
        mask = df.get("lang", pd.Series("en", index=df.index)) == lang
        sub = df[mask]
        if sub.empty:
            continue
        texts = sub[text_col].fillna("").tolist()
        try:
            scores = score_texts(texts, lang)
            df.loc[mask, "sentiment_score"] = scores
        except Exception as e:
            logger.error(f"Sentiment scoring failed for lang={lang}: {e}")
    return df
