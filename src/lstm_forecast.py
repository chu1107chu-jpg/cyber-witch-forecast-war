from __future__ import annotations

import math
import os
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

_MODULE_DIR = Path(__file__).parent
_REPO_ROOT  = _MODULE_DIR.parent
MODEL_PATH  = _REPO_ROOT / "data" / "artifacts" / "conflict" / "mlp_ivpn_predictor.pkl"

_model_cache: Optional[dict] = None


def _load_model() -> Optional[dict]:
    global _model_cache
    if _model_cache is not None:
        return _model_cache
    if not MODEL_PATH.exists():
        return None
    try:
        with open(MODEL_PATH, "rb") as f:
            _model_cache = pickle.load(f)
        return _model_cache
    except Exception:
        return None


@dataclass
class LSTMForecast:
    available: bool = False
    next_ivpn: float = 0.0
    delta: float = 0.0
    trajectory: list[float] = None
    direction_icon: str = "→"
    confidence: str = "низкая"
    error: str = ""

    def __post_init__(self):
        if self.trajectory is None:
            self.trajectory = []

    @property
    def direction_color(self) -> str:
        if self.delta > 0.02:
            return "#e74c3c"
        if self.delta < -0.02:
            return "#26c281"
        return "#f39c12"

    def format_delta(self) -> str:
        sign = "▲" if self.delta > 0 else "▼" if self.delta < 0 else "→"
        color = self.direction_color
        return f'<b style="color:{color};">{sign} {abs(self.delta):.3f}</b>'

    def format_next(self) -> str:
        color = self.direction_color
        return f'<b style="color:{color};">{self.next_ivpn:.3f}</b>'


def _age_legacy_feature(age: float, legacy_seeking: float) -> float:
    age_factor = 1.0 / (1.0 + math.exp(-0.08 * (age - 65)))
    return float(np.clip(age_factor * legacy_seeking, 0.0, 1.0))


def extract_leader_features(
    leader_a: dict,
    leader_b: dict,
    atrocity_a: float,
    atrocity_b: float,
    recession_a: float,
    recession_b: float,
    debt_gdp_a: float,
    debt_gdp_b: float,
) -> dict[str, float]:
    election_near_a = 1.0 if leader_a.get("election_months", 999) <= 12 else 0.0
    election_near_b = 1.0 if leader_b.get("election_months", 999) <= 12 else 0.0
    election_near = max(election_near_a, election_near_b)

    return {
        "hawkishness_a":  float(leader_a.get("hawkishness", 0.5)),
        "hawkishness_b":  float(leader_b.get("hawkishness", 0.5)),
        "approval_a":     float(leader_a.get("domestic_approval", 0.5)),
        "approval_b":     float(leader_b.get("domestic_approval", 0.5)),
        "election_near":  election_near,
        "age_legacy_a":   _age_legacy_feature(
                              float(leader_a.get("age", 60)),
                              float(leader_a.get("legacy_seeking", 0.5)),
                          ),
        "age_legacy_b":   _age_legacy_feature(
                              float(leader_b.get("age", 50)),
                              float(leader_b.get("legacy_seeking", 0.5)),
                          ),
        "atrocity_a":     float(atrocity_a),
        "atrocity_b":     float(atrocity_b),
        "recession_a":    float(recession_a),
        "recession_b":    float(recession_b),
        "debt_gdp_a":     float(np.clip(debt_gdp_a, 0.0, 2.5) / 2.5),
        "debt_gdp_b":     float(np.clip(debt_gdp_b, 0.0, 2.5) / 2.5),
    }


def _predict_one_step(
    model_dict: dict,
    ivpn_window: list[float],
    leader_feats: dict[str, float],
) -> float:
    model    = model_dict["model"]
    scaler   = model_dict["scaler"]
    feat_names = model_dict["feature_names"]
    window   = model_dict["window"]

    feat_vec = []
    for name in feat_names:
        if name.startswith("ivpn_t-"):
            # ivpn_t-5 → индекс 0 (самый старый), ivpn_t-0 → индекс 5 (текущий)
            lag = int(name.split("t-")[1])
            idx = (window - 1) - lag
            feat_vec.append(float(np.clip(ivpn_window[idx], 0.0, 1.0)))
        else:
            feat_vec.append(leader_feats.get(name, 0.5))

    X = np.array(feat_vec).reshape(1, -1)
    X_scaled = scaler.transform(X)
    pred = float(model.predict(X_scaled)[0])
    return float(np.clip(pred, 0.0, 1.0))


def predict_trajectory(
    current_ivpn: float,
    history_ivpn: list[float],
    leader_a: dict,
    leader_b: dict,
    atrocity_a: float = 0.5,
    atrocity_b: float = 0.5,
    recession_a: float = 0.3,
    recession_b: float = 0.7,
    debt_gdp_a: float = 1.2,
    debt_gdp_b: float = 0.4,
    n_steps: int = 3,
) -> LSTMForecast:
    model_dict = _load_model()
    if model_dict is None:
        return LSTMForecast(
            available=False,
            error=f"Файл модели не найден: {MODEL_PATH}",
        )

    try:
        window = model_dict["window"]

        all_vals = list(reversed(history_ivpn)) + [current_ivpn]
        if len(all_vals) < window:
            all_vals = [current_ivpn] * (window - len(all_vals)) + all_vals
        ivpn_window = list(all_vals[-window:])

        leader_feats = extract_leader_features(
            leader_a=leader_a,
            leader_b=leader_b,
            atrocity_a=atrocity_a,
            atrocity_b=atrocity_b,
            recession_a=recession_a,
            recession_b=recession_b,
            debt_gdp_a=debt_gdp_a,
            debt_gdp_b=debt_gdp_b,
        )

        trajectory = []
        window_buf = list(ivpn_window)
        for _ in range(n_steps):
            pred = _predict_one_step(model_dict, window_buf, leader_feats)
            trajectory.append(pred)
            window_buf = window_buf[1:] + [pred]

        next_ivpn = trajectory[0]
        delta = next_ivpn - current_ivpn

        if delta > 0.015:
            icon = "▲"
        elif delta < -0.015:
            icon = "▼"
        else:
            icon = "→"

        confidence = (
            "высокая" if abs(delta) > 0.04
            else "средняя" if abs(delta) > 0.015
            else "низкая"
        )

        return LSTMForecast(
            available=True,
            next_ivpn=next_ivpn,
            delta=delta,
            trajectory=trajectory,
            direction_icon=icon,
            confidence=confidence,
        )

    except Exception as e:
        return LSTMForecast(
            available=False,
            error=str(e),
        )


def format_trajectory_html(forecast: LSTMForecast, current_ivpn: float) -> str:
    if not forecast.available:
        return f'<span style="color:#64748b;font-size:.85em;">⚠️ MLP-модель недоступна: {forecast.error}</span>'

    steps = [current_ivpn] + forecast.trajectory
    parts = []
    for i, v in enumerate(steps):
        if i == 0:
            parts.append(f'<b>{v:.3f}</b>')
        else:
            prev = steps[i - 1]
            if v > prev + 0.01:
                col = "#e74c3c"
                arrow = "↗"
            elif v < prev - 0.01:
                col = "#26c281"
                arrow = "↘"
            else:
                col = "#f39c12"
                arrow = "→"
            parts.append(f'<span style="color:{col};">{arrow} {v:.3f}</span>')

    return (
        f'<div style="font-size:.9rem;">🤖 <b>MLP-прогноз траектории:</b> '
        + " ".join(parts)
        + f' <span style="color:#64748b;font-size:.8em;">(на 1–{len(forecast.trajectory)} мес. вперёд)</span>'
        + "</div>"
    )
