"""
lstm_forecast.py — Прогноз траектории уровня напряжённости на основе
MLP-модели (обученной на исторических данных конфликтов).

Файл модели: data/artifacts/conflict/mlp_ivpn_predictor.pkl
Признаки:
  ivpn_t-5..ivpn_t-0   — скользящее окно из 6 значений
  hawkishness_a/b       — агрессивность лидеров
  approval_a/b          — внутреннее одобрение лидеров
  election_near         — выборы в ближайшие 12 мес (0/1)
  age_legacy_a/b        — поправка за возраст/legacy-seeking
  atrocity_a/b          — индекс злодеяний
  recession_a/b         — риск рецессии
  debt_gdp_a/b          — долг/ВВП
"""
from __future__ import annotations

import math
import os
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

# ─────────────────────────────────────────────
#  Путь к модели (относительно корня репо)
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
#  Данные классы
# ─────────────────────────────────────────────
@dataclass
class LSTMForecast:
    available: bool = False         # модель загружена и предсказание успешно
    next_ivpn: float = 0.0          # прогноз ИВПН на t+1 (следующий месяц)
    delta: float = 0.0              # изменение vs текущего ИВПН
    trajectory: list[float] = None  # прогноз на 3 месяца вперёд
    direction_icon: str = "→"       # ▲ ▼ →
    confidence: str = "низкая"      # высокая/средняя/низкая (по |delta|)
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


# ─────────────────────────────────────────────
#  Вспомогательная: age_legacy feature
# ─────────────────────────────────────────────
def _age_legacy_feature(age: float, legacy_seeking: float) -> float:
    """
    Комбинирует возраст и стремление к наследию.
    Лидеры > 70 лет с высоким legacy_seeking → выше значение.
    """
    age_factor = 1.0 / (1.0 + math.exp(-0.08 * (age - 65)))  # sigmoid вокруг 65 лет
    return float(np.clip(age_factor * legacy_seeking, 0.0, 1.0))


# ─────────────────────────────────────────────
#  Извлечение признаков лидеров из профиля
# ─────────────────────────────────────────────
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
    """
    Формирует словарь признаков лидеров для MLP-модели.
    Ключи совпадают с feature_names модели (кроме ivpn_t-n).
    """
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
        "debt_gdp_a":     float(np.clip(debt_gdp_a, 0.0, 2.5) / 2.5),   # нормируем
        "debt_gdp_b":     float(np.clip(debt_gdp_b, 0.0, 2.5) / 2.5),
    }


# ─────────────────────────────────────────────
#  Автарегрессионный прогноз
# ─────────────────────────────────────────────
def _predict_one_step(
    model_dict: dict,
    ivpn_window: list[float],  # 6 значений, старые → новые
    leader_feats: dict[str, float],
) -> float:
    """Делает прогноз на 1 шаг вперёд."""
    model    = model_dict["model"]
    scaler   = model_dict["scaler"]
    feat_names = model_dict["feature_names"]  # 19 признаков
    window   = model_dict["window"]           # 6

    # Формируем вектор признаков в порядке feature_names
    feat_vec = []
    for name in feat_names:
        if name.startswith("ivpn_t-"):
            # ivpn_t-5 → индекс 0 (самый старый), ivpn_t-0 → индекс 5 (текущий)
            lag = int(name.split("t-")[1])  # 5,4,3,2,1,0
            idx = (window - 1) - lag        # 0,1,2,3,4,5
            feat_vec.append(float(np.clip(ivpn_window[idx], 0.0, 1.0)))
        else:
            feat_vec.append(leader_feats.get(name, 0.5))

    X = np.array(feat_vec).reshape(1, -1)
    X_scaled = scaler.transform(X)
    pred = float(model.predict(X_scaled)[0])
    return float(np.clip(pred, 0.0, 1.0))


# ─────────────────────────────────────────────
#  Публичный API
# ─────────────────────────────────────────────
def predict_trajectory(
    current_ivpn: float,
    history_ivpn: list[float],  # список значений из истории, newest первый
    leader_a: dict,
    leader_b: dict,
    atrocity_a: float = 0.5,
    atrocity_b: float = 0.5,
    recession_a: float = 0.3,
    recession_b: float = 0.7,
    debt_gdp_a: float = 1.2,
    debt_gdp_b: float = 0.4,
    n_steps: int = 3,           # горизонт прогноза в месяцах
) -> LSTMForecast:
    """
    Прогнозирует траекторию уровня напряжённости на n_steps месяцев вперёд.

    Args:
        current_ivpn:   текущее значение ИВПН (из UI)
        history_ivpn:   предыдущие значения (newest first) из ivpn_history
        leader_a/b:     профили лидеров (из LEADER_PROFILES)
        n_steps:        горизонт прогноза (мес.)

    Returns:
        LSTMForecast с next_ivpn, delta, trajectory[n_steps]
    """
    model_dict = _load_model()
    if model_dict is None:
        return LSTMForecast(
            available=False,
            error=f"Файл модели не найден: {MODEL_PATH}",
        )

    try:
        window = model_dict["window"]  # 6

        # Собираем окно из 6 значений: история (oldest→newest) + current
        all_vals = list(reversed(history_ivpn)) + [current_ivpn]  # oldest first
        if len(all_vals) < window:
            # Дополняем текущим значением
            all_vals = [current_ivpn] * (window - len(all_vals)) + all_vals
        ivpn_window = list(all_vals[-window:])  # последние 6, oldest first

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

        # Авторегрессионный прогноз на n_steps шагов
        trajectory = []
        window_buf = list(ivpn_window)
        for _ in range(n_steps):
            pred = _predict_one_step(model_dict, window_buf, leader_feats)
            trajectory.append(pred)
            window_buf = window_buf[1:] + [pred]  # сдвигаем окно

        next_ivpn = trajectory[0]
        delta = next_ivpn - current_ivpn

        # Иконка направления
        if delta > 0.015:
            icon = "▲"
        elif delta < -0.015:
            icon = "▼"
        else:
            icon = "→"

        # Уровень уверенности по magnitude delta
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
    """Строит HTML-строку с мини-графиком из emoji и цифр."""
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
