"""
monte_carlo.py — Доверительные интервалы для ИВПН и P(E) через Монте-Карло.

Запускаем N симуляций, добавляя гауссов шум к каждому фактору,
вычисляем квантили результирующих ИВПН и вероятностей.

Результат: ConfidenceResult с квантилями [5%, 25%, 50%, 75%, 95%].
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

# ─────────────────────────────────────────────
#  Параметры симуляции
# ─────────────────────────────────────────────
N_SIMULATIONS = 500   # достаточно для p5-p95 при σ ~ 0.05

# Неопределённость по умолчанию для каждого фактора
# Если фактор ближе к 0.5 — ошибка выше, на краях — ниже (expert-calibrated)
FACTOR_SIGMA_DEFAULT = 0.05

# Специальные σ для факторов с принципиально большей неопределённостью
FACTOR_SIGMA: dict[str, float] = {
    "nuclear_factor":      0.07,  # ядерная программа сложно верифицируема
    "elite_cohesion":      0.08,  # внутренняя политика Ирана — «чёрный ящик»
    "proxy_activity":      0.06,
    "diplomatic_failure":  0.06,
    "military_imbalance":  0.04,  # военный дисбаланс относительно измеряем
    "economic_pressure":   0.04,  # рыночные данные — более объективны
    "historical_hostility":0.03,  # исторические факты — стабильны
    "ideological_tension": 0.06,
}


# ─────────────────────────────────────────────
#  Результат
# ─────────────────────────────────────────────
@dataclass
class ConfidenceResult:
    # ИВПН квантили
    ivpn_p5:  float = 0.0
    ivpn_p25: float = 0.0
    ivpn_p50: float = 0.0   # медиана
    ivpn_p75: float = 0.0
    ivpn_p95: float = 0.0

    # P(E) квантили
    pe_p5:    float = 0.0
    pe_p25:   float = 0.0
    pe_p50:   float = 0.0
    pe_p75:   float = 0.0
    pe_p95:   float = 0.0

    # Полный массив (500 значений) для гистограммы
    ivpn_samples: list[float] = field(default_factory=list)
    pe_samples:   list[float] = field(default_factory=list)

    # Вспомогательные метрики
    ivpn_std: float = 0.0   # стандартное отклонение
    pe_std:   float = 0.0

    @property
    def ivpn_ci90(self) -> tuple[float, float]:
        """90% доверительный интервал для ИВПН."""
        return (self.ivpn_p5, self.ivpn_p95)

    @property
    def pe_ci90(self) -> tuple[float, float]:
        """90% доверительный интервал для P(E)."""
        return (self.pe_p5, self.pe_p95)

    def format_ivpn(self) -> str:
        """Форматированная строка: 0.91 [0.84–0.97]"""
        return f"{self.ivpn_p50:.3f} [{self.ivpn_p5:.2f}–{self.ivpn_p95:.2f}]"

    def format_pe(self) -> str:
        """Форматированная строка: 87% [76%–95%]"""
        return f"{self.pe_p50:.0%} [{self.pe_p5:.0%}–{self.pe_p95:.0%}]"

    def uncertainty_band_html(self, value: float, lo: float, hi: float, color: str = "#e74c3c") -> str:
        """HTML для отображения значения с интервалом."""
        width = hi - lo
        return (
            f'<span style="font-size:1.1em;font-weight:700;color:{color};">{value:.3f}</span> '
            f'<span style="font-size:.8em;color:#64748b;"> [{lo:.2f} – {hi:.2f}]  '
            f'±{width/2:.2f}</span>'
        )


# ─────────────────────────────────────────────
#  Главная функция
# ─────────────────────────────────────────────
def run_monte_carlo(
    factors: dict[str, float],
    compute_ivpn_fn: Callable[[dict], float],
    compute_proba_fn: Callable[[float], float],
    leader_adj: float = 0.0,
    bonus: float = 0.0,
    n: int = N_SIMULATIONS,
    seed: int | None = 42,
) -> ConfidenceResult:
    """
    Запускает n Монте-Карло симуляций.

    Args:
        factors:        базовые значения факторов (центры распределений)
        compute_ivpn_fn: функция ИВПН = Σ(wᵢ·xᵢ)
        compute_proba_fn: функция P(E) = 1/(1+e^{-k*(ivpn-θ)})
        leader_adj:     поправка от профилей лидеров
        bonus:          поправка от третьих стран
        n:              количество симуляций
        seed:           seed для воспроизводимости
    """
    rng = np.random.default_rng(seed)

    factor_keys = list(factors.keys())
    sigmas = np.array([FACTOR_SIGMA.get(k, FACTOR_SIGMA_DEFAULT) for k in factor_keys])
    means  = np.array([factors[k] for k in factor_keys])

    # Векторизованная генерация: (n, n_factors)
    samples_matrix = rng.normal(loc=means, scale=sigmas, size=(n, len(factor_keys)))
    # Clip к [0, 1]
    samples_matrix = np.clip(samples_matrix, 0.0, 1.0)

    # Вычисляем ИВПН для каждой симуляции
    ivpn_samples = np.zeros(n)
    for i in range(n):
        f_sim = {k: float(samples_matrix[i, j]) for j, k in enumerate(factor_keys)}
        ivpn_samples[i] = float(np.clip(compute_ivpn_fn(f_sim) + leader_adj + bonus, 0.0, 1.0))

    # P(E) для каждой симуляции
    pe_samples = np.array([compute_proba_fn(x) for x in ivpn_samples])

    result = ConfidenceResult(
        ivpn_p5  = float(np.percentile(ivpn_samples, 5)),
        ivpn_p25 = float(np.percentile(ivpn_samples, 25)),
        ivpn_p50 = float(np.percentile(ivpn_samples, 50)),
        ivpn_p75 = float(np.percentile(ivpn_samples, 75)),
        ivpn_p95 = float(np.percentile(ivpn_samples, 95)),
        pe_p5    = float(np.percentile(pe_samples, 5)),
        pe_p25   = float(np.percentile(pe_samples, 25)),
        pe_p50   = float(np.percentile(pe_samples, 50)),
        pe_p75   = float(np.percentile(pe_samples, 75)),
        pe_p95   = float(np.percentile(pe_samples, 95)),
        ivpn_samples = ivpn_samples.tolist(),
        pe_samples   = pe_samples.tolist(),
        ivpn_std = float(np.std(ivpn_samples)),
        pe_std   = float(np.std(pe_samples)),
    )
    return result


def make_ci_band_trace(
    x_range: list[float],
    ci: ConfidenceResult,
    compute_ivpn_fn: Callable,
    compute_proba_fn: Callable,
) -> list[dict]:
    """
    Возвращает два Plotly-трейса (band P25-P75 и P5-P95)
    для наложения на логистическую кривую.
    """
    # Вертикальная полоса в текущей точке ИВПН
    ivpn_lo5  = ci.ivpn_p5
    ivpn_hi95 = ci.ivpn_p95
    ivpn_lo25 = ci.ivpn_p25
    ivpn_hi75 = ci.ivpn_p75

    traces = []

    # Полоса 90%
    traces.append({
        "type": "rect",
        "x0": ivpn_lo5, "x1": ivpn_hi95,
        "y0": 0, "y1": 1,
        "fillcolor": "rgba(231,76,60,0.07)",
        "line": {"width": 0},
        "layer": "below",
        "label": "90% CI",
    })
    # Полоса 50%
    traces.append({
        "type": "rect",
        "x0": ivpn_lo25, "x1": ivpn_hi75,
        "y0": 0, "y1": 1,
        "fillcolor": "rgba(231,76,60,0.15)",
        "line": {"width": 0},
        "layer": "below",
        "label": "50% CI",
    })

    return traces


def uncertainty_description(ci: ConfidenceResult) -> str:
    """Текстовое описание неопределённости для пользователя."""
    width = ci.ivpn_p95 - ci.ivpn_p5
    if width < 0.05:
        level = "низкая"
    elif width < 0.12:
        level = "умеренная"
    elif width < 0.20:
        level = "высокая"
    else:
        level = "очень высокая"
    return (
        f"Неопределённость модели: **{level}** "
        f"(90% CI по уровню напряжённости: {ci.ivpn_p5:.2f}–{ci.ivpn_p95:.2f}, "
        f"ширина ±{width/2:.2f})"
    )
