"""/api/v1/forecast — train / predict / metrics"""
from fastapi import APIRouter, BackgroundTasks, Query
from pydantic import BaseModel
from datetime import date
from typing import List, Optional

router = APIRouter()


class TrainResp(BaseModel):
    status: str
    started_at: str
    job_id: str


class PredictReq(BaseModel):
    date: date
    tickers: List[str]


class TickerPred(BaseModel):
    ticker: str
    date: date
    r1: float
    R20: float
    p1: float
    p20: float


class PredictResp(BaseModel):
    preds: List[TickerPred]


class MetricsResp(BaseModel):
    mae: float
    brier: float
    da: float
    score: float


@router.post("/train", response_model=TrainResp)
async def train(background_tasks: BackgroundTasks):
    """Запуск обучения всех моделей (async background job)."""
    from datetime import datetime
    job_id = f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    # TODO: background_tasks.add_task(run_training, job_id)
    return TrainResp(
        status="started",
        started_at=datetime.now().isoformat(),
        job_id=job_id,
    )


@router.post("/predict", response_model=PredictResp)
async def predict(req: PredictReq):
    """Прогнозы r1 / R20 / p1 / p20 для списка тикеров."""
    from src.pipeline.predict import run_predict
    preds = run_predict(req.date.isoformat(), req.tickers)
    return PredictResp(preds=preds)


@router.get("/metrics", response_model=MetricsResp)
async def metrics(split: str = Query("val", pattern="^(val|test)$")):
    """Метрики последней обученной модели."""
    from src.pipeline.evaluate import load_metrics
    m = load_metrics(split)
    return MetricsResp(**m)
