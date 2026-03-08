"""
news_fetcher.py
===============
Получает свежие новости из 7 RSS-источников: ТАСС, RT, BBC, Al Jazeera, IRNA, Reuters, Times of Israel.
Фильтрует по иранской тематике, вычисляет δ-факторы с учётом достоверности источника (байесовское обновление).

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
    # Российский угол зрения
    "ТАСС":          "https://tass.ru/rss/v2.xml",
    "RT":            "https://www.rt.com/rss/news/",
    # Западный угол зрения
    "BBC":           "https://feeds.bbci.co.uk/news/world/rss.xml",
    "Reuters":       "https://feeds.reuters.com/reuters/worldnews",
    # Арабский / региональный угол зрения
    "AlJazeera":     "https://www.aljazeera.com/xml/rss/all.xml",
    # Иранское госагентство
    "IRNA":          "https://en.irna.ir/rss",
    # Израильский угол зрения
    "TimesOfIsrael": "https://www.timesofisrael.com/feed/",
}

# Доверие к источнику: меньше σ → больше вес при байесовском обновлении
# Reuters/AP = нейтральные, низкая неопределённость
SOURCE_SIGMA: dict[str, float] = {
    "Reuters":       0.12,   # высокая точность, нейтральный
    "BBC":           0.16,   # надёжный, западный угол
    "AlJazeera":     0.18,   # региональный, независимый
    "TimesOfIsrael": 0.20,   # израильский национальный угол
    "ТАСС":          0.24,   # российское госагентство
    "IRNA":          0.24,   # иранское госагентство
    "RT":            0.26,   # госСМИ с редакционной позицией
    "default":       0.22,
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


def bayesian_update(
    prior_factors: dict[str, float],
    events: list[NewsEvent],
    prior_sigma: float = 0.12,
) -> dict[str, float]:
    """
    Байесовское обновление факторов на основе новостных событий.

    Модель: каждый фактор x имеет Гауссов prior (x_0, σ_prior).
    Каждое событие — наблюдение (x_0 + δ, σ_source).
    Posterior: MAP оценка с взвешиванием по точности источника.

    Формула (Гауссов байес): 
      posterior_mean = (μ0/σ²₀ + Сум(данные_i/σ²_i)) / (1/σ²₀ + Сум(1/σ²_i))

    Args:
        prior_factors: текущие значения слайдеров (prior_mean)
        events:        список NewsEvent
        prior_sigma:   неопределённость приора (по умолчанию 0.12)

    Returns:
        обновлённые значения факторов {factor: posterior_value}
    """
    # Собираем наблюдения по факторам
    observations: dict[str, list[tuple[float, float]]] = {}  # factor -> [(x_obs, sigma)]
    for ev in events:
        if not ev.factor or ev.delta == 0.0:
            continue
        sigma_src = SOURCE_SIGMA.get(ev.source, SOURCE_SIGMA["default"])
        x_obs = prior_factors.get(ev.factor, 0.5) + ev.delta  # x_0 + δ
        x_obs = max(0.0, min(1.0, x_obs))
        observations.setdefault(ev.factor, []).append((x_obs, sigma_src))

    updated = dict(prior_factors)  # начинаем с приором
    prior_precision = 1.0 / (prior_sigma ** 2)

    for factor, obs_list in observations.items():
        prior_mean = prior_factors.get(factor, 0.5)
        # Суммарная статистика по всем наблюдениям
        sum_prec = prior_precision
        sum_prec_x = prior_mean * prior_precision
        for x_obs, sigma_src in obs_list:
            prec = 1.0 / (sigma_src ** 2)
            sum_prec   += prec
            sum_prec_x += x_obs * prec
        posterior_mean = sum_prec_x / sum_prec
        updated[factor] = float(max(0.0, min(1.0, posterior_mean)))

    return updated
