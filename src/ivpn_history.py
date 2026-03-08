"""
ivpn_history.py
===============
Хранилище снапшотов ИВПН во времени.

Каждый снапшот:
  {
    "ts":            "2026-03-08T10:00:00+00:00",   # ISO-8601 UTC
    "source":        "news_update | manual | seed",
    "ivpn":          0.82,
    "p_escalation":  0.71,
    "markov_state":  "🔴 Война",
    "markov_idx":    3,
    "factors":       { ... текущие значения всех факторов ... },
    "factor_deltas": { "economic_pressure": +0.07, ... },
    "events": [
      {
        "title":   "КСИР закрыл Ормузский пролив",
        "url":     "https://...",
        "source":  "ТАСС",
        "published":"...",
        "factor":  "economic_pressure",
        "delta":   0.07
      },
      ...
    ]
  }

Файл: data/ivpn_history.json
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HISTORY_FILE = Path(__file__).parent.parent / "data" / "ivpn_history.json"
HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────
#  I/O
# ──────────────────────────────────────────────
def load_history() -> list[dict]:
    """Загружает всю историю, новейшие записи первые."""
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_history(records: list[dict]) -> None:
    with HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────
#  Формирование снапшота
# ──────────────────────────────────────────────
def make_snapshot(
    ivpn: float,
    p_escalation: float,
    markov_state: str,
    markov_idx: int,
    factors: dict[str, float],
    factor_deltas: dict[str, float],
    events: list[dict],
    source: str = "news_update",
    note: str = "",
) -> dict:
    return {
        "ts":            datetime.now(tz=timezone.utc).isoformat(),
        "source":        source,
        "ivpn":          round(ivpn, 4),
        "p_escalation":  round(p_escalation, 4),
        "markov_state":  markov_state,
        "markov_idx":    markov_idx,
        "factors":       {k: round(float(v), 4) for k, v in factors.items()},
        "factor_deltas": {k: round(float(v), 4) for k, v in factor_deltas.items()},
        "events":        events,
        "note":          note,
    }


def append_snapshot(snap: dict) -> None:
    """Добавляет снапшот в начало истории (новейшие — первые)."""
    records = load_history()
    records.insert(0, snap)
    # Ограничиваем размер: 500 снапшотов
    _save_history(records[:500])


# ──────────────────────────────────────────────
#  Дедупликация: не сохраняем если ИВПН не изменился
# ──────────────────────────────────────────────
def should_save(new_ivpn: float, min_delta: float = 0.005) -> bool:
    """Возвращает True если ИВПН изменился достаточно от последней записи."""
    records = load_history()
    if not records:
        return True
    return abs(new_ivpn - records[0]["ivpn"]) >= min_delta


# ──────────────────────────────────────────────
#  Вспомогательные функции для графика
# ──────────────────────────────────────────────
def build_chart_data(records: list[dict]) -> dict:
    """
    Преобразует список снапшотов в структуры для Plotly.
    Возвращает dict с полями ts, ivpn, p_escalation, hover_text, marker_color.
    """
    ts_list, ivpn_list, p_list, hover_list, colors = [], [], [], [], []
    markov_colors = {
        "🟢 Мир":           "#26c281",
        "🟡 Напряжённость": "#f39c12",
        "🟠 Кризис":        "#e67e22",
        "🔴 Война":         "#e74c3c",
        "🔵 Заморозка":     "#6c63ff",
    }

    for rec in reversed(records):  # хронологический порядок для графика
        ts_list.append(rec["ts"])
        ivpn_list.append(rec["ivpn"])
        p_list.append(rec["p_escalation"])

        # ─── hover-текст ───────────────────────────────────
        lines = [
            f"<b>{rec['ts'][:16].replace('T',' ')} UTC</b>",
            f"Уровень напряжённости = <b>{rec['ivpn']:.3f}</b>  |  P(эскалации) = <b>{rec['p_escalation']:.1%}</b>",
            f"Состояние: {rec['markov_state']}",
        ]
        if rec.get("factor_deltas"):
            parts = []
            for fac, d in sorted(rec["factor_deltas"].items(),
                                  key=lambda x: abs(x[1]), reverse=True)[:3]:
                sign = "▲" if d > 0 else "▼"
                parts.append(f"{sign}{abs(d):.2f} {fac}")
            lines.append("Изменения: " + " | ".join(parts))
        events = rec.get("events", [])
        if events:
            lines.append("─────────────────")
            # Уникальные заголовки
            seen = set()
            for ev in events[:5]:
                t = ev.get("title", "")
                if t and t not in seen:
                    seen.add(t)
                    src = ev.get("source", "")
                    lines.append(f"• [{src}] {t[:80]}")
        if rec.get("note"):
            lines.append(f"<i>{rec['note']}</i>")

        hover_list.append("<br>".join(lines))
        colors.append(markov_colors.get(rec.get("markov_state", ""), "#95a5a6"))

    return {
        "ts":           ts_list,
        "ivpn":         ivpn_list,
        "p_escalation": p_list,
        "hover":        hover_list,
        "colors":       colors,
    }
