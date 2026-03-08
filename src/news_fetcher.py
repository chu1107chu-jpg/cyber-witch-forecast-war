"""
news_fetcher.py
===============
Получает свежие новости из RSS-лент ТАСС и RT,
фильтрует по иранской тематике, вычисляет δ-факторы ИВПН.

Результат: список NewsEvent, готовых к записи в историю.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import feedparser

# ──────────────────────────────────────────────
#  RSS-источники
# ──────────────────────────────────────────────
RSS_FEEDS = {
    "ТАСС":   "https://tass.ru/rss/v2.xml",
    "RT":     "https://www.rt.com/rss/news/",
    "BBC":    "https://feeds.bbci.co.uk/news/world/rss.xml",
}

# ──────────────────────────────────────────────
#  Ключевые слова, сигнализирующие об иранской теме
# ──────────────────────────────────────────────
IRAN_KEYWORDS = [
    r"иран", r"iran", r"tehran", r"тегеран",
    r"хаменеи", r"khamenei", r"пезешкиан", r"pezeshkian",
    r"ксир", r"irgc", r"хезболл", r"hezbolla",
    r"хоути", r"хусит", r"houthi",
    r"ормуз", r"hormuz",
    r"ядерн", r"nuclear", r"uranium", r"обогащ",
    r"persian gulf", r"персидск",
]

IRAN_RE = re.compile("|".join(IRAN_KEYWORDS), re.IGNORECASE)

# ──────────────────────────────────────────────
#  Маппинг ключевых слов → (фактор ИВПН, Δ)
#  Факторы совпадают с WEIGHTS в _conflict_forecast.py
# ──────────────────────────────────────────────
FACTOR_RULES: list[tuple[re.Pattern, str, float]] = [
    # Военные удары / эскалация
    (re.compile(r"удар|strike|bombing|бомб|ракет|missile|авиац|airstrike|атаку", re.I),
     "military_power", +0.06),
    # Американо-израильское наращивание
    (re.compile(r"авианос|carrier|b-1|b-2|бомбардировщ|bomber|troops|войск", re.I),
     "military_power", +0.05),
    # Закрытие Ормуза / блокады
    (re.compile(r"ормуз|hormuz|strait|блокад|blockade|закрыт|санкц|sanction", re.I),
     "economic_pressure", +0.07),
    # Нефть цены
    (re.compile(r"нефть.{0,20}рост|нефть.{0,20}скач|oil.{0,20}surged|brent.{0,20}jump|brent.{0,20}top", re.I),
     "economic_pressure", +0.04),
    # Ядерная программа
    (re.compile(r"ядерн|nuclear|uranium|обогащ|enrichment|centrifuge|центрифуг", re.I),
     "nuclear_risk", +0.07),
    # Ядерные переговоры / сделка
    (re.compile(r"ядерн.{0,30}переговор|nuclear.{0,30}deal|jcpoa|nuclear.{0,30}talk", re.I),
     "nuclear_risk", -0.05),
    # Дипломатия / разрядка
    (re.compile(r"переговор|ceasefire|прекращ огн|перемирие|truce|diplomacy|дипломат", re.I),
     "diplomatic_failure", -0.06),
    # Провал переговоров / ультиматум
    (re.compile(r"ультиматум|ultimatum|surrender|капитул|безоговорочн|unconditional|провал.{0,15}перегов", re.I),
     "diplomatic_failure", +0.07),
    # Прокси-активность
    (re.compile(r"хезболл|hezbolla|хоути|houthi|хамас|hamas|прокси|proxy|ливан|lebanon|йемен|yemen", re.I),
     "proxy_activity", +0.05),
    # Протесты / внутренняя дестабилизация Ирана
    (re.compile(r"протест|protest|митинг|демонстрац|riot", re.I),
     "elite_cohesion", -0.04),
    # Народная консолидация в Иране
    (re.compile(r"консолидац|ral(ly|lied)|народ.{0,20}(support|поддержи|объединил)", re.I),
     "elite_cohesion", +0.04),
    # Геополитическая поддержка (Китай/Россия)
    (re.compile(r"китай.{0,20}(поддерж|against|oppose)|china.{0,20}(support|against|oppose)|россия.{0,20}(поддерж|iran)|russia.{0,20}iran", re.I),
     "geopolitical_shift", +0.05),
    # Жертвы среди гражданских / военные потери
    (re.compile(r"жертв|погиб|killed|civilian|casualties|168.{0,15}дет|school.{0,15}(strike|bomb)", re.I),
     "military_power", +0.04),
    # Гибель лидера
    (re.compile(r"хаменеи.{0,20}(погиб|убит|killed|dead|death)|khamenei.{0,20}(killed|dead|death)", re.I),
     "elite_cohesion", +0.09),
    # Идеологическая риторика / религиозная рамка
    (re.compile(r"джихад|jihad|объявл.{0,15}войни|шиит|shia|исламск.{0,15}(война|republic)", re.I),
     "ideological_tension", +0.05),
]

# ──────────────────────────────────────────────
#  Dataclass результата
# ──────────────────────────────────────────────
@dataclass
class NewsEvent:
    title:         str
    url:           str            = ""
    source:        str            = ""
    published:     str            = ""     # ISO timestamp
    summary:       str            = ""
    factor:        str            = ""     # ИВПН-фактор, на который влияет
    delta:         float          = 0.0   # изменение фактора
    matched_rule:  str            = ""


def _parse_published(entry) -> str:
    """Возвращает ISO-8601 строку даты, либо текущее время."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            pass
    return datetime.now(tz=timezone.utc).isoformat()


def _score_entry(text: str) -> list[tuple[str, float, str]]:
    """
    Применяет FACTOR_RULES к тексту заголовка+аннотации.
    Возвращает список (factor, delta, matched_rule) для всех совпавших правил.
    Каждый фактор засчитывается максимум один раз (strongest match).
    """
    hits: dict[str, tuple[float, str]] = {}
    for pattern, factor, delta in FACTOR_RULES:
        m = pattern.search(text)
        if m:
            prev_delta, _ = hits.get(factor, (0.0, ""))
            if abs(delta) > abs(prev_delta):
                hits[factor] = (delta, m.group(0))
    return [(factor, delta, matched) for factor, (delta, matched) in hits.items()]


def fetch_news(max_per_feed: int = 30, timeout: int = 8) -> list[NewsEvent]:
    """
    Скачивает новости из RSS_FEEDS.
    Возвращает список NewsEvent для Иран-релевантных статей с рассчитанным δ.
    Более новые статьи — первые в списке.
    """
    events: list[NewsEvent] = []
    seen_titles: set[str] = set()

    for source_name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url, request_headers={
                "User-Agent": "Mozilla/5.0 (IvpnBot/1.0; conflict-forecast)"
            })
            entries = (feed.entries or [])[:max_per_feed]
        except Exception:
            continue

        for entry in entries:
            title   = getattr(entry, "title",   "")
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
            link    = getattr(entry, "link",    "")
            text    = f"{title} {summary}"

            if not IRAN_RE.search(text):
                continue

            norm_title = re.sub(r"\s+", " ", title.strip().lower())
            if norm_title in seen_titles:
                continue
            seen_titles.add(norm_title)

            hits = _score_entry(text)
            pub  = _parse_published(entry)

            if hits:
                # Создаём по одному NewsEvent на каждое сработавшее правило
                for factor, delta, matched in hits:
                    events.append(NewsEvent(
                        title=title.strip(),
                        url=link,
                        source=source_name,
                        published=pub,
                        summary=summary[:300],
                        factor=factor,
                        delta=delta,
                        matched_rule=matched,
                    ))
            else:
                # Иран-тема, но без явного сигнала → небольшой нейтральный маркер
                events.append(NewsEvent(
                    title=title.strip(),
                    url=link,
                    source=source_name,
                    published=pub,
                    summary=summary[:300],
                    factor="ideological_tension",
                    delta=0.01,
                    matched_rule="(иран-тема)",
                ))

    # Сортируем по дате убывания
    events.sort(key=lambda e: e.published, reverse=True)
    return events


def aggregate_deltas(events: list[NewsEvent]) -> dict[str, float]:
    """
    Агрегирует все δ по факторам из списка событий.
    Возвращает {factor: total_delta}, ограничиваем [-0.30, +0.30].
    """
    totals: dict[str, float] = {}
    for ev in events:
        if ev.factor:
            totals[ev.factor] = totals.get(ev.factor, 0.0) + ev.delta
    # Ограничиваем сильные сигналы
    return {f: max(-0.30, min(0.30, d)) for f, d in totals.items()}
