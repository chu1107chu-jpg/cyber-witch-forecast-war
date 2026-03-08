"""
market_data.py — Живые рыночные данные для обогащения модели.

Источники:
  • yfinance   — Brent (BZ=F), природный газ (NG=F)
  • Polymarket  — gamma-api.polymarket.com (рынок вероятностей)
  • Metaculus   — api2.metaculus.com (агрегатор экспертов)

Данные кэшируются в памяти на TTL секунд, чтобы не DDOSить апи при каждом ренотри.
"""
from __future__ import annotations

import time
import math
import logging
from dataclasses import dataclass, field
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Конфиг
# ─────────────────────────────────────────────
CACHE_TTL = 1800  # 30 минут

# Brent baseline (ноябрь 2025, до обострения)
BRENT_BASELINE = 75.0
LNG_BASELINE   = 2.8  # $/MMBtu

# Polymarket — контракт "Will there be direct US-Iran military conflict before June 2026?"
POLYMARKET_SLUG = "us-iran-military-conflict-2026"

# Metaculus — вопрос об эскалации США-Иран
METACULUS_QUESTION_ID = 11690  # "Iran nuclear crisis escalation 2026"

# ─────────────────────────────────────────────
#  Простой in-process кэш
# ─────────────────────────────────────────────
_CACHE: dict[str, tuple[float, object]] = {}  # key → (ts, value)


def _cache_get(key: str) -> Optional[object]:
    entry = _CACHE.get(key)
    if entry and (time.time() - entry[0]) < CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, value: object) -> None:
    _CACHE[key] = (time.time(), value)


# ─────────────────────────────────────────────
#  Данные классы
# ─────────────────────────────────────────────
@dataclass
class MarketSnapshot:
    # Цены
    brent_usd: Optional[float] = None          # $/bbl
    lng_usd: Optional[float] = None            # $/MMBtu

    # Polymarket
    polymarket_p_conflict: Optional[float] = None   # 0..1
    polymarket_volume_usd: Optional[float] = None
    polymarket_url: str = ""

    # Metaculus
    metaculus_community_p: Optional[float] = None   # 0..1
    metaculus_url: str = ""

    # Вычисленные δ-факторы (сколько добавить к слайдерам)
    delta_economic_pressure: float = 0.0
    delta_military_imbalance: float = 0.0

    # Мета
    fetched_at: float = field(default_factory=time.time)
    errors: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────
#  yfinance — Brent, LNG
# ─────────────────────────────────────────────
def _fetch_prices() -> dict[str, Optional[float]]:
    cached = _cache_get("prices")
    if cached is not None:
        return cached

    result: dict[str, Optional[float]] = {"brent": None, "lng": None}
    try:
        import yfinance as yf

        # Brent Crude
        try:
            b = yf.Ticker("BZ=F")
            hist = b.history(period="5d")
            if not hist.empty:
                result["brent"] = float(hist["Close"].dropna().iloc[-1])
        except Exception as e:
            logger.warning("yfinance Brent: %s", e)

        # Natural Gas Henry Hub (proxy для LNG)
        try:
            n = yf.Ticker("NG=F")
            hist = n.history(period="5d")
            if not hist.empty:
                result["lng"] = float(hist["Close"].dropna().iloc[-1])
        except Exception as e:
            logger.warning("yfinance LNG: %s", e)

    except ImportError:
        logger.warning("yfinance не установлен")

    _cache_set("prices", result)
    return result


# ─────────────────────────────────────────────
#  Polymarket — gamma API
# ─────────────────────────────────────────────
def _fetch_polymarket() -> dict:
    cached = _cache_get("polymarket")
    if cached is not None:
        return cached

    result = {"p": None, "volume": None, "url": ""}
    try:
        # Ищем рынок по ключевым словам
        resp = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"q": "iran us military conflict 2026", "limit": 5, "active": "true"},
            timeout=6,
        )
        if resp.status_code == 200:
            markets = resp.json()
            if markets:
                best = markets[0]
                # outcomes: [{"price": 0.72, "name": "Yes"}, ...]
                outcomes = best.get("outcomes", best.get("outcomePrices", []))
                if isinstance(outcomes, list) and outcomes:
                    # цена  "Yes" = вероятность
                    if isinstance(outcomes[0], dict):
                        yes = next((o for o in outcomes if str(o.get("name","")).lower() in ("yes","да")), outcomes[0])
                        result["p"] = float(yes.get("price", 0))
                    else:
                        # строки-числа
                        result["p"] = float(outcomes[0])
                result["volume"] = float(best.get("volumeNum", best.get("volume", 0)) or 0)
                result["url"] = f"https://polymarket.com/market/{best.get('slug','')}"

        # Если прямой поиск не дал p — пробуем конкретный slug
        if result["p"] is None:
            resp2 = requests.get(
                f"https://gamma-api.polymarket.com/markets",
                params={"slug": POLYMARKET_SLUG},
                timeout=5,
            )
            if resp2.status_code == 200:
                markets2 = resp2.json()
                if markets2:
                    m = markets2[0]
                    probs_str = m.get("outcomePrices") or m.get("outcomes") or []
                    if isinstance(probs_str, str):
                        import json
                        probs_str = json.loads(probs_str)
                    if probs_str:
                        result["p"] = float(probs_str[0])
                    result["url"] = f"https://polymarket.com/market/{m.get('slug','')}"

    except Exception as e:
        logger.warning("Polymarket fetch: %s", e)

    _cache_set("polymarket", result)
    return result


# ─────────────────────────────────────────────
#  Metaculus — REST API v2
# ─────────────────────────────────────────────
def _fetch_metaculus() -> dict:
    cached = _cache_get("metaculus")
    if cached is not None:
        return cached

    result = {"p": None, "url": ""}
    try:
        # Поиск по Iran escalation
        resp = requests.get(
            "https://www.metaculus.com/api2/questions/",
            params={"search": "iran us war 2026", "order_by": "-publish_time", "limit": 3,
                    "status": "open", "forecast_type": "binary"},
            timeout=6,
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 200:
            data = resp.json()
            questions = data.get("results", [])
            if questions:
                q = questions[0]
                p_raw = q.get("community_prediction", {})
                if isinstance(p_raw, dict):
                    result["p"] = p_raw.get("full", {}).get("q2")
                elif isinstance(p_raw, (int, float)):
                    result["p"] = float(p_raw)
                result["url"] = f"https://www.metaculus.com{q.get('page_url','')}"
        else:
            # fallback: конкретный вопрос по ID
            resp2 = requests.get(
                f"https://www.metaculus.com/api2/questions/{METACULUS_QUESTION_ID}/",
                timeout=5,
                headers={"Accept": "application/json"},
            )
            if resp2.status_code == 200:
                q = resp2.json()
                p_raw = q.get("community_prediction", {})
                if isinstance(p_raw, dict):
                    result["p"] = p_raw.get("full", {}).get("q2")
                result["url"] = f"https://www.metaculus.com/questions/{METACULUS_QUESTION_ID}/"

    except Exception as e:
        logger.warning("Metaculus fetch: %s", e)

    _cache_set("metaculus", result)
    return result


# ─────────────────────────────────────────────
#  Расчёт δ-факторов из цен
# ─────────────────────────────────────────────
def _price_to_deltas(brent: Optional[float], lng: Optional[float]) -> dict[str, float]:
    """
    Переводит отклонение цен от базовых значений
    в поправки к факторам модели.
    
    Логика:
      Brent > baseline → рынок закладывает риск → economic_pressure ↑
      Brent рост > 30% → признак сильного шока → military_imbalance чуть ↑
    """
    d = {"economic_pressure": 0.0, "military_imbalance": 0.0}
    if brent is not None:
        pct = (brent - BRENT_BASELINE) / BRENT_BASELINE
        # Линейная связь: +10% нефти ↔ +0.03 к economic_pressure, cap ±0.20
        d["economic_pressure"] = float(max(-0.20, min(0.20, pct * 0.30)))
        # Резкий скачок нефти → косвенный сигнал военного риска
        if pct > 0.25:
            d["military_imbalance"] = min(0.05, (pct - 0.25) * 0.10)

    if lng is not None:
        pct_lng = (lng - LNG_BASELINE) / LNG_BASELINE
        # LNG шок усиливает economic_pressure, но слабее нефти
        ep_extra = max(-0.10, min(0.10, pct_lng * 0.12))
        d["economic_pressure"] = max(-0.20, min(0.20, d["economic_pressure"] + ep_extra))

    return d


# ─────────────────────────────────────────────
#  Главная функция
# ─────────────────────────────────────────────
def fetch_market_data(timeout: float = 8.0) -> MarketSnapshot:
    """
    Параллельно получает цены, Polymarket и Metaculus.
    Возвращает MarketSnapshot с готовыми данными.
    """
    snap = MarketSnapshot()
    errors: list[str] = []

    # 1. Цены
    try:
        prices = _fetch_prices()
        snap.brent_usd = prices.get("brent")
        snap.lng_usd   = prices.get("lng")
        deltas = _price_to_deltas(snap.brent_usd, snap.lng_usd)
        snap.delta_economic_pressure  = deltas["economic_pressure"]
        snap.delta_military_imbalance = deltas["military_imbalance"]
    except Exception as e:
        errors.append(f"Цены: {e}")

    # 2. Polymarket
    try:
        pm = _fetch_polymarket()
        snap.polymarket_p_conflict = pm.get("p")
        snap.polymarket_volume_usd = pm.get("volume")
        snap.polymarket_url = pm.get("url", "")
    except Exception as e:
        errors.append(f"Polymarket: {e}")

    # 3. Metaculus
    try:
        mc = _fetch_metaculus()
        snap.metaculus_community_p = mc.get("p")
        snap.metaculus_url = mc.get("url", "")
    except Exception as e:
        errors.append(f"Metaculus: {e}")

    snap.errors = errors
    return snap


# ─────────────────────────────────────────────
#  Вспомогательные форматтеры для UI
# ─────────────────────────────────────────────
def format_brent(snap: MarketSnapshot) -> str:
    if snap.brent_usd is None:
        return "—"
    delta_pct = (snap.brent_usd - BRENT_BASELINE) / BRENT_BASELINE * 100
    sign = "▲" if delta_pct > 0 else "▼"
    color = "#e74c3c" if delta_pct > 10 else "#f39c12" if delta_pct > 0 else "#26c281"
    return f'<b style="color:{color};">{snap.brent_usd:.1f} $/bbl {sign}{abs(delta_pct):.0f}%</b>'


def format_lng(snap: MarketSnapshot) -> str:
    if snap.lng_usd is None:
        return "—"
    delta_pct = (snap.lng_usd - LNG_BASELINE) / LNG_BASELINE * 100
    sign = "▲" if delta_pct > 0 else "▼"
    color = "#e74c3c" if delta_pct > 20 else "#f39c12" if delta_pct > 0 else "#26c281"
    return f'<b style="color:{color};">{snap.lng_usd:.2f} $/MMBtu {sign}{abs(delta_pct):.0f}%</b>'


def format_polymarket(snap: MarketSnapshot) -> str:
    if snap.polymarket_p_conflict is None:
        return "—"
    p = snap.polymarket_p_conflict
    color = "#e74c3c" if p > 0.7 else "#e67e22" if p > 0.4 else "#26c281"
    return f'<b style="color:{color};">{p:.0%}</b>'


def format_metaculus(snap: MarketSnapshot) -> str:
    if snap.metaculus_community_p is None:
        return "—"
    p = snap.metaculus_community_p
    color = "#e74c3c" if p > 0.7 else "#e67e22" if p > 0.4 else "#26c281"
    return f'<b style="color:{color};">{p:.0%}</b>'


def market_calibration_note(snap: MarketSnapshot, model_p: float) -> Optional[str]:
    """
    Если Polymarket/Metaculus значительно расходятся с моделью — выдаём предупреждение.
    """
    signals = []
    if snap.polymarket_p_conflict is not None:
        signals.append(snap.polymarket_p_conflict)
    if snap.metaculus_community_p is not None:
        signals.append(snap.metaculus_community_p)
    if not signals:
        return None

    market_avg = sum(signals) / len(signals)
    diff = abs(market_avg - model_p)
    if diff > 0.15:
        direction = "занижает" if model_p < market_avg else "завышает"
        return (
            f"⚠️ Рынки ({market_avg:.0%}) и модель ({model_p:.0%}) расходятся на "
            f"{diff:.0%}. Модель может {direction} риск — проверьте слайдеры."
        )
    return None
