"""Основной пайплайн обучения: sklearn + TF + Torch → artifacts."""
import argparse
import json
import logging
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)
PROCESSED_DIR = Path("data/processed")
ARTIFACT_DIR = Path("data/artifacts")


def run_training(
    models: list[str] | None = None,
    max_time_min: int = 60,
) -> dict:
    if models is None:
        models = ["sk_baseline", "tf_lstm", "torch_mlp"]

    start = time.time()
    results = {}

    logger.info("Loading feature matrix…")
    feat_path = PROCESSED_DIR / "features.parquet"
    if not feat_path.exists():
        from src.features.build_features import build_features
        df = build_features()
    else:
        df = pd.read_parquet(feat_path)

    exclude = {"Date", "ticker", "Open", "High", "Low", "Close", "Volume",
               "target_r1", "target_R20", "target_p1_up", "target_p20_up"}
    feature_cols = [c for c in df.columns if c not in exclude]
    logger.info(f"  {len(df)} rows × {len(feature_cols)} features")

    if "sk_baseline" in models:
        if time.time() - start < max_time_min * 60:
            from src.models.sk_baseline import train as sk_train
            sk_train(df)
            results["sk_baseline"] = "done"

    if "tf_lstm" in models:
        if time.time() - start < max_time_min * 60:
            try:
                from src.models.tf_lstm import train as tf_train
                tf_train(df, feature_cols)
                results["tf_lstm"] = "done"
            except Exception as e:
                logger.error(f"TF LSTM failed: {e}")
                results["tf_lstm"] = f"error: {e}"

    if "torch_mlp" in models:
        if time.time() - start < max_time_min * 60:
            try:
                from src.models.torch_mlp import train as torch_train
                torch_train(df, feature_cols)
                results["torch_mlp"] = "done"
            except Exception as e:
                logger.error(f"Torch MLP failed: {e}")
                results["torch_mlp"] = f"error: {e}"

    elapsed = round(time.time() - start, 1)
    summary = {"elapsed_sec": elapsed, "models": results}
    (ARTIFACT_DIR / "train_summary.json").write_text(json.dumps(summary, indent=2))
    logger.info(f"Training complete in {elapsed}s: {results}")
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="sk_baseline,tf_lstm,torch_mlp")
    parser.add_argument("--max-time", type=int, default=60)
    args = parser.parse_args()
    run_training(args.models.split(","), args.max_time)
