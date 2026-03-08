"""sklearn baseline models: Ridge, ElasticNet, Logistic, RF, ExtraTrees."""
import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, StackingRegressor, StackingClassifier
from sklearn.linear_model import Ridge, ElasticNet, LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)
ARTIFACT_DIR = Path("data/artifacts/sklearn")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS: list[str] = []  # будет заполнено в train()


def _get_feature_cols(df: pd.DataFrame) -> list[str]:
    exclude = {"Date", "ticker", "Open", "High", "Low", "Close", "Volume",
               "target_r1", "target_R20", "target_p1_up", "target_p20_up"}
    return [c for c in df.columns if c not in exclude]


def train(df: pd.DataFrame) -> dict:
    global FEATURE_COLS
    FEATURE_COLS = _get_feature_cols(df)
    X = df[FEATURE_COLS].fillna(0).values
    y_r1 = df["target_r1"].values
    y_R20 = df["target_R20"].values
    y_p1 = df["target_p1_up"].values
    y_p20 = df["target_p20_up"].values

    # regression
    reg_models = [
        ("ridge", Ridge(alpha=1.0)),
        ("enet", ElasticNet(alpha=0.01, l1_ratio=0.5, max_iter=2000)),
        ("rf", RandomForestRegressor(n_estimators=100, max_depth=6, n_jobs=-1, random_state=42)),
        ("et", ExtraTreesRegressor(n_estimators=100, max_depth=6, n_jobs=-1, random_state=42)),
    ]
    reg_r1 = StackingRegressor(
        estimators=reg_models[:2], final_estimator=Ridge(), passthrough=True, cv=3
    )
    reg_R20 = StackingRegressor(
        estimators=reg_models[:2], final_estimator=Ridge(), passthrough=True, cv=3
    )
    # classification
    clf_models = [
        ("lr", LogisticRegression(C=1.0, max_iter=500, random_state=42)),
        ("rf_c", RandomForestRegressor(n_estimators=100, max_depth=6, n_jobs=-1, random_state=42)),
    ]

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    logger.info("Training stacked regressor for r1…")
    reg_r1.fit(X_scaled, y_r1)
    logger.info("Training stacked regressor for R20…")
    reg_R20.fit(X_scaled, y_R20)

    lr_p1 = LogisticRegression(C=1.0, max_iter=500, random_state=42)
    lr_p1.fit(X_scaled, y_p1.astype(int))
    lr_p20 = LogisticRegression(C=1.0, max_iter=500, random_state=42)
    lr_p20.fit(X_scaled, y_p20.astype(int))

    artifacts = {
        "scaler": scaler,
        "reg_r1": reg_r1,
        "reg_R20": reg_R20,
        "clf_p1": lr_p1,
        "clf_p20": lr_p20,
        "feature_cols": FEATURE_COLS,
    }
    with open(ARTIFACT_DIR / "artifacts.pkl", "wb") as f:
        pickle.dump(artifacts, f)
    logger.info(f"SK artifacts saved → {ARTIFACT_DIR}/artifacts.pkl")
    return artifacts


def predict(df: pd.DataFrame, artifacts: dict | None = None) -> pd.DataFrame:
    if artifacts is None:
        with open(ARTIFACT_DIR / "artifacts.pkl", "rb") as f:
            artifacts = pickle.load(f)
    feat_cols = artifacts["feature_cols"]
    X = df[feat_cols].fillna(0).values
    X_scaled = artifacts["scaler"].transform(X)
    df = df.copy()
    df["pred_r1"]  = artifacts["reg_r1"].predict(X_scaled)
    df["pred_R20"] = artifacts["reg_R20"].predict(X_scaled)
    df["pred_p1"]  = artifacts["clf_p1"].predict_proba(X_scaled)[:, 1]
    df["pred_p20"] = artifacts["clf_p20"].predict_proba(X_scaled)[:, 1]
    return df
