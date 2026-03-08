"""Прогнозирование для заданных тикеров и даты (ансамбль)."""
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
PROCESSED_DIR = Path("data/processed")
ARTIFACT_DIR  = Path("data/artifacts")


class TickerPred:
    def __init__(self, ticker, date_, r1, R20, p1, p20):
        self.ticker = ticker
        self.date   = date_
        self.r1     = r1
        self.R20    = R20
        self.p1     = p1
        self.p20    = p20

    def model_dump(self):
        return dict(ticker=self.ticker, date=str(self.date),
                    r1=self.r1, R20=self.R20, p1=self.p1, p20=self.p20)


def run_predict(predict_date: str, tickers: list[str]) -> list[TickerPred]:
    feat_path = PROCESSED_DIR / "features.parquet"
    if not feat_path.exists():
        logger.warning("Features not found, returning mock predictions")
        return _mock_preds(predict_date, tickers)

    df = pd.read_parquet(feat_path)
    exclude = {"Date", "ticker", "Open", "High", "Low", "Close", "Volume",
               "target_r1", "target_R20", "target_p1_up", "target_p20_up"}
    feature_cols = [c for c in df.columns if c not in exclude]

    results = []
    for ticker in tickers:
        sub = df[df["ticker"] == ticker]
        if sub.empty:
            results.append(_mock_pred(predict_date, ticker))
            continue
        last = sub.tail(1)

        preds = {}

        # SK baseline
        try:
            from src.models.sk_baseline import predict as sk_pred
            out = sk_pred(last)
            preds["sk_r1"]  = float(out["pred_r1"].iloc[0])
            preds["sk_R20"] = float(out["pred_R20"].iloc[0])
            preds["sk_p1"]  = float(out["pred_p1"].iloc[0])
        except Exception as e:
            logger.debug(f"SK: {e}")

        # Torch MLP
        try:
            from src.models.torch_mlp import predict as torch_pred
            tout = torch_pred(last)
            if "target_r1" in tout:
                preds["torch_r1"] = float(tout["target_r1"][0])
            if "target_p1_up" in tout:
                preds["torch_p1"] = float(tout["target_p1_up"][0])
        except Exception as e:
            logger.debug(f"Torch: {e}")

        # Ensemble: mean of available
        r1_vals  = [v for k, v in preds.items() if k.endswith("_r1")]
        R20_vals = [v for k, v in preds.items() if k.endswith("_R20")]
        p1_vals  = [v for k, v in preds.items() if k.endswith("_p1")]

        r1  = float(np.mean(r1_vals))  if r1_vals  else 0.0
        R20 = float(np.mean(R20_vals)) if R20_vals else r1 * 5
        p1  = float(np.clip(np.mean(p1_vals), 0, 1)) if p1_vals else 0.5
        p20 = float(np.clip(p1 * 0.9 + 0.05, 0, 1))

        next_date = (pd.Timestamp(predict_date) + pd.Timedelta(days=1)).date()
        results.append(TickerPred(ticker, next_date, round(r1, 6), round(R20, 6),
                                  round(p1, 4), round(p20, 4)))

    return results


def _mock_preds(predict_date: str, tickers: list[str]) -> list[TickerPred]:
    return [_mock_pred(predict_date, t) for t in tickers]


def _mock_pred(predict_date: str, ticker: str) -> TickerPred:
    import random
    random.seed(hash(ticker + predict_date) % (2**32))
    r1 = random.uniform(-0.01, 0.01)
    return TickerPred(
        ticker=ticker,
        date_=(pd.Timestamp(predict_date) + pd.Timedelta(days=1)).date(),
        r1=round(r1, 6),
        R20=round(r1 * 5, 6),
        p1=round(0.5 + r1 * 10, 4),
        p20=round(0.5 + r1 * 5, 4),
    )
