"""
coin_flip.py
============
Подбрасыватель монеты для страницы "Монетка": орёл / решка / очень редко — ребро.

Счётчики (просмотры страницы, число подбросов, распределение исходов)
сохраняются в data/coin_stats.json — простой способ прикинуть трафик
раздела без внешней аналитики. На Streamlit Community Cloud файл живёт,
пока не будет передеплоя/перезапуска контейнера (та же оговорка, что и
у data/ivpn_history.json в этом проекте).

Файл: data/coin_stats.json
"""
from __future__ import annotations

import json
import random
from pathlib import Path

STATS_FILE = Path(__file__).parent.parent / "data" / "coin_stats.json"
STATS_FILE.parent.mkdir(parents=True, exist_ok=True)

# Вероятность "ребра". Реальная физика для монеты вроде рубля/цента даёт
# что-то в районе 1/6000 (Murray & Teare, 1993). Здесь — компромисс между
# "очень-очень редко" и тем, чтобы фичу вообще можно было увидеть за
# разумное число подбросов: 1 к 2000.
EDGE_PROBABILITY = 0.0005

DEFAULT_STATS = {
    "page_views":  0,
    "total_flips": 0,
    "heads":       0,
    "tails":       0,
    "edge":        0,
}


def _load() -> dict:
    if not STATS_FILE.exists():
        return dict(DEFAULT_STATS)
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**DEFAULT_STATS, **data}
    except Exception:
        return dict(DEFAULT_STATS)


def _save(stats: dict) -> None:
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception:
        pass  # трафик — не критичная функция, страница не должна падать из-за диска


def record_page_view() -> dict:
    """Вызывать один раз за сессию (см. флаг в session_state на странице)."""
    stats = _load()
    stats["page_views"] += 1
    _save(stats)
    return stats


def flip_coin() -> tuple[str, dict]:
    """Подбрасывает монету. Возвращает (результат, обновлённая статистика).

    результат ∈ {"heads", "tails", "edge"}
    """
    r = random.random()
    if r < EDGE_PROBABILITY:
        result = "edge"
    elif r < EDGE_PROBABILITY + (1 - EDGE_PROBABILITY) / 2:
        result = "heads"
    else:
        result = "tails"

    stats = _load()
    stats["total_flips"] += 1
    stats[result] += 1
    _save(stats)
    return result, stats


def get_stats() -> dict:
    return _load()
