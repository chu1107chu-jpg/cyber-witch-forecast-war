from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

N_SIMULATIONS = 500

FACTOR_SIGMA_DEFAULT = 0.05

FACTOR_SIGMA: dict[str, float] = {
    "nuclear_factor":      0.07,
    "elite_cohesion":      0.08,
    "proxy_activity":      0.06,
    "diplomatic_failure":  0.06,
    "military_imbalance":  0.04,
    "economic_pressure":   0.04,
    "historical_hostility":0.03,
    "ideological_tension": 0.06,
}


@dataclass
class ConfidenceResult:
    ivpn_p5:  float = 0.0
    ivpn_p25: float = 0.0
    ivpn_p50: float = 0.0
    ivpn_p75: float = 0.0
    ivpn_p95: float = 0.0

    pe_p5:    float = 0.0
    pe_p25:   float = 0.0
    pe_p50:   float = 0.0
    pe_p75:   float = 0.0
    pe_p95:   float = 0.0

    ivpn_samples: list[float] = field(default_factory=list)
    pe_samples:   list[float] = field(default_factory=list)

    ivpn_std: float = 0.0
    pe_std:   float = 0.0

    @property
    def ivpn_ci90(self) -> tuple[float, float]:
        return (self.ivpn_p5, self.ivpn_p95)

    @property
    def pe_ci90(self) -> tuple[float, float]:
        return (self.pe_p5, self.pe_p95)

    def format_ivpn(self) -> str:
        return f"{self.ivpn_p50:.3f} [{self.ivpn_p5:.2f}–{self.ivpn_p95:.2f}]"

    def format_pe(self) -> str:
        return f"{self.pe_p50:.0%} [{self.pe_p5:.0%}–{self.pe_p95:.0%}]"

    def uncertainty_band_html(self, value: float, lo: float, hi: float, color: str = "#e74c3c") -> str:
        width = hi - lo
        return (
            f'<span style="font-size:1.1em;font-weight:700;color:{color};">{value:.3f}</span> '
            f'<span style="font-size:.8em;color:#64748b;"> [{lo:.2f} – {hi:.2f}]  '
            f'±{width/2:.2f}</span>'
        )


def run_monte_carlo(
    factors: dict[str, float],
    compute_ivpn_fn: Callable[[dict], float],
    compute_proba_fn: Callable[[float], float],
    leader_adj: float = 0.0,
    bonus: float = 0.0,
    n: int = N_SIMULATIONS,
    seed: int | None = 42,
) -> ConfidenceResult:
    rng = np.random.default_rng(seed)

    factor_keys = list(factors.keys())
    sigmas = np.array([FACTOR_SIGMA.get(k, FACTOR_SIGMA_DEFAULT) for k in factor_keys])
    means  = np.array([factors[k] for k in factor_keys])

    samples_matrix = rng.normal(loc=means, scale=sigmas, size=(n, len(factor_keys)))
    samples_matrix = np.clip(samples_matrix, 0.0, 1.0)

    ivpn_samples = np.zeros(n)
    for i in range(n):
        f_sim = {k: float(samples_matrix[i, j]) for j, k in enumerate(factor_keys)}
        ivpn_samples[i] = float(np.clip(compute_ivpn_fn(f_sim) + leader_adj + bonus, 0.0, 1.0))

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
    ivpn_lo5  = ci.ivpn_p5
    ivpn_hi95 = ci.ivpn_p95
    ivpn_lo25 = ci.ivpn_p25
    ivpn_hi75 = ci.ivpn_p75

    traces = []

    traces.append({
        "type": "rect",
        "x0": ivpn_lo5, "x1": ivpn_hi95,
        "y0": 0, "y1": 1,
        "fillcolor": "rgba(231,76,60,0.07)",
        "line": {"width": 0},
        "layer": "below",
        "label": "90% CI",
    })
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
