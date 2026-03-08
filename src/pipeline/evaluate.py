"""Оценка моделей: MAE, Brier, DA → итоговый score."""
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, mean_absolute_error

logger = logging.getLogger(__name__)
PROCESSED_DIR = Path("data/processed")
ARTIFACT_DIR  = Path("data/artifacts")


def compute_metrics(y_true_r1, y_pred_r1, y_true_p, y_pred_p,
                    y_true_R20=None, y_pred_R20=None) -> dict:
    mae_r1 = mean_absolute_error(y_true_r1, y_pred_r1)
    mae_R20 = mean_absolute_error(y_true_R20, y_pred_R20) if y_true_R20 is not None else None
    brier = brier_score_loss(y_true_p.astype(int), np.clip(y_pred_p, 0, 1))
    da = float(np.mean(np.sign(y_true_r1) == np.sign(y_pred_r1)))

    # normalised score (higher is better)
    brier_norm = 1 - brier / 0.25          # 0.25 = random baseline Brier
    da_norm    = (da - 0.5) * 2            # [-1, 1]
    score = 0.25 * (1 - mae_r1 / 0.02) + \
            0.25 * (1 - (mae_R20 or mae_r1 * 5) / 0.1) + \
            0.25 * brier_norm + \
            0.25 * da
    score = float(np.clip(score, 0, 1))

    return {
        "mae": round(mae_r1, 6),
        "brier": round(brier, 6),
        "da": round(da, 4),
        "score": round(score, 4),
    }


def load_metrics(split: str = "val") -> dict:
    path = ARTIFACT_DIR / f"metrics_{split}.json"
    if path.exists():
        return json.loads(path.read_text())
    # fallback: compute on the fly
    feat_path = PROCESSED_DIR / "features.parquet"
    if not feat_path.exists():
        return {"mae": 0.0, "brier": 0.25, "da": 0.5, "score": 0.0}

    df = pd.read_parquet(feat_path)
    exclude = {"Date", "ticker", "Open", "High", "Low", "Close", "Volume",
               "target_r1", "target_R20", "target_p1_up", "target_p20_up"}
    feature_cols = [c for c in df.columns if c not in exclude]

    n = len(df)
    cut = int(n * (0.85 if split == "val" else 1.0))
    sub = df[cut:] if split == "test" else df[int(n * 0.7): cut]
    if sub.empty:
        return {"mae": 0.0, "brier": 0.25, "da": 0.5, "score": 0.0}

    try:
        from src.models.sk_baseline import predict as sk_pred
        out = sk_pred(sub)
        m = compute_metrics(
            sub["target_r1"].values, out["pred_r1"].values,
            sub["target_p1_up"].values, out["pred_p1"].values,
            sub["target_R20"].values, out["pred_R20"].values,
        )
    except Exception as e:
        logger.warning(f"Metrics computation failed: {e}")
        m = {"mae": 0.0, "brier": 0.25, "da": 0.5, "score": 0.0}

    path.write_text(json.dumps(m))
    return m
