"""/api/v1/data — tickers / quotes / news"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import date

router = APIRouter()


class OHLCVRow(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class NewsItem(BaseModel):
    publish_date: str
    title: str
    sentiment: float
    weight: float
    source: str
    url: Optional[str] = None


@router.get("/tickers")
async def get_tickers():
    from src.utils.config import load_app_config
    cfg = load_app_config()
    return {"tickers": cfg.get("tickers", ["AAPL", "MSFT", "BTC-USD", "ETH-USD"])}


@router.get("/quotes")
async def get_quotes(
    ticker: str = Query(...),
    window: int = Query(120, ge=5, le=1200),
):
    from src.etl.fetch_quotes import load_candles
    rows = load_candles(ticker, window)
    return {"ticker": ticker, "data": rows}


@router.get("/news")
async def get_news(
    ticker: str = Query(...),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=500),
):
    from src.etl.clean_news import load_news
    items = load_news(
        ticker,
        from_date=from_date.isoformat() if from_date else None,
        to_date=to_date.isoformat() if to_date else None,
        limit=limit,
    )
    return {"ticker": ticker, "items": items}


@router.get("/big-news-analysis")
async def big_news_analysis(ticker: str = Query(...)):
    """Аналитическая сводка: реакция рынка на 'крупные' новости за 5 лет."""
    from src.features.big_news import analyze_big_news
    result = analyze_big_news(ticker)
    return {"ticker": ticker, **result}
