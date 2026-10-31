from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import feedparser
import requests

RSS_FEEDS = {
    "ТАСС":          "https://tass.ru/rss/v2.xml",
    "RT":            "https://www.rt.com/rss/news/",
    "BBC":           "https://feeds.bbci.co.uk/news/world/rss.xml",
    "Reuters":       "https://feeds.reuters.com/reuters/worldnews",
    "AlJazeera":     "https://www.aljazeera.com/xml/rss/all.xml",
    "IRNA":          "https://en.irna.ir/rss",
    "TimesOfIsrael": "https://www.timesofisrael.com/feed/",
}

SOURCE_SIGMA: dict[str, float] = {
    "Reuters":       0.12,
    "BBC":           0.16,
    "AlJazeera":     0.18,
    "TimesOfIsrael": 0.20,
    "ТАСС":          0.24,
    "IRNA":          0.24,
    "RT":            0.26,
    "default":       0.22,
}

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

FACTOR_RULES: list[tuple[re.Pattern, str, float]] = [
    (re.compile(r"удар|strike|bombing|бомб|ракет|missile|авиац|airstrike|атаку", re.I),
     "military_power", +0.06),
    (re.compile(r"авианос|carrier|b-1|b-2|бомбардировщ|bomber|troops|войск", re.I),
     "military_power", +0.05),
    (re.compile(r"ормуз|hormuz|strait|блокад|blockade|закрыт|санкц|sanction", re.I),
     "economic_pressure", +0.07),
    (re.compile(r"нефть.{0,20}рост|нефть.{0,20}скач|oil.{0,20}surged|brent.{0,20}jump|brent.{0,20}top", re.I),
     "economic_pressure", +0.04),
    (re.compile(r"ядерн|nuclear|uranium|обогащ|enrichment|centrifuge|центрифуг", re.I),
     "nuclear_risk", +0.07),
    (re.compile(r"ядерн.{0,30}переговор|nuclear.{0,30}deal|jcpoa|nuclear.{0,30}talk", re.I),
     "nuclear_risk", -0.05),
    (re.compile(r"переговор|ceasefire|прекращ огн|перемирие|truce|diplomacy|дипломат", re.I),
     "diplomatic_failure", -0.06),
    (re.compile(r"ультиматум|ultimatum|surrender|капитул|безоговорочн|unconditional|провал.{0,15}перегов", re.I),
     "diplomatic_failure", +0.07),
    (re.compile(r"хезболл|hezbolla|хоути|houthi|хамас|hamas|прокси|proxy|ливан|lebanon|йемен|yemen", re.I),
     "proxy_activity", +0.05),
    (re.compile(r"протест|protest|митинг|демонстрац|riot", re.I),
     "elite_cohesion", -0.04),
    (re.compile(r"консолидац|ral(ly|lied)|народ.{0,20}(support|поддержи|объединил)", re.I),
     "elite_cohesion", +0.04),
    (re.compile(r"китай.{0,20}(поддерж|against|oppose)|china.{0,20}(support|against|oppose)|россия.{0,20}(поддерж|iran)|russia.{0,20}iran", re.I),
     "geopolitical_shift", +0.05),
    (re.compile(r"жертв|погиб|killed|civilian|casualties|168.{0,15}дет|school.{0,15}(strike|bomb)", re.I),
     "military_power", +0.04),
    (re.compile(r"хаменеи.{0,20}(погиб|убит|killed|dead|death)|khamenei.{0,20}(killed|dead|death)", re.I),
     "elite_cohesion", +0.09),
    (re.compile(r"джихад|jihad|объявл.{0,15}войни|шиит|shia|исламск.{0,15}(война|republic)", re.I),
     "ideological_tension", +0.05),
]

@dataclass
class NewsEvent:
    title:         str
    url:           str            = ""
    source:        str            = ""
    published:     str            = ""
    summary:       str            = ""
    factor:        str            = ""
    delta:         float          = 0.0
    matched_rule:  str            = ""


def _parse_published(entry) -> str:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        except Exception:
            pass
    return datetime.now(tz=timezone.utc).isoformat()


def _score_entry(text: str) -> list[tuple[str, float, str]]:
    hits: dict[str, tuple[float, str]] = {}
    for pattern, factor, delta in FACTOR_RULES:
        m = pattern.search(text)
        if m:
            prev_delta, _ = hits.get(factor, (0.0, ""))
            if abs(delta) > abs(prev_delta):
                hits[factor] = (delta, m.group(0))
    return [(factor, delta, matched) for factor, (delta, matched) in hits.items()]


def _fetch_one_feed(source_name: str, url: str, timeout: int) -> tuple[str, list]:
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (IvpnBot/1.0; conflict-forecast)"},
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        return source_name, list(feed.entries or [])
    except Exception:
        return source_name, []


def fetch_news(max_per_feed: int = 30, timeout: int = 6) -> list[NewsEvent]:
    events: list[NewsEvent] = []
    seen_titles: set[str] = set()

    fetched: dict[str, list] = {}
    with ThreadPoolExecutor(max_workers=len(RSS_FEEDS)) as pool:
        futures = {
            pool.submit(_fetch_one_feed, source_name, url, timeout): source_name
            for source_name, url in RSS_FEEDS.items()
        }
        try:
            for fut in as_completed(futures, timeout=timeout + 5):
                try:
                    source_name, entries = fut.result()
                    fetched[source_name] = entries
                except Exception:
                    continue
        except Exception:
            # as_completed сам может кинуть TimeoutError, если что-то не
            # уложилось даже в timeout+5 (напр. завис DNS-резолв) —
            # работаем с тем, что успело прийти, не подвешивая страницу.
            pass

    for source_name in RSS_FEEDS:
        entries = fetched.get(source_name, [])[:max_per_feed]

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

    events.sort(key=lambda e: e.published, reverse=True)
    return events


def aggregate_deltas(events: list[NewsEvent]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for ev in events:
        if ev.factor:
            totals[ev.factor] = totals.get(ev.factor, 0.0) + ev.delta
    return {f: max(-0.30, min(0.30, d)) for f, d in totals.items()}


def bayesian_update(
    prior_factors: dict[str, float],
    events: list[NewsEvent],
    prior_sigma: float = 0.12,
) -> dict[str, float]:
    observations: dict[str, list[tuple[float, float]]] = {}
    for ev in events:
        if not ev.factor or ev.delta == 0.0:
            continue
        sigma_src = SOURCE_SIGMA.get(ev.source, SOURCE_SIGMA["default"])
        x_obs = prior_factors.get(ev.factor, 0.5) + ev.delta
        x_obs = max(0.0, min(1.0, x_obs))
        observations.setdefault(ev.factor, []).append((x_obs, sigma_src))

    updated = dict(prior_factors)
    prior_precision = 1.0 / (prior_sigma ** 2)

    for factor, obs_list in observations.items():
        prior_mean = prior_factors.get(factor, 0.5)
        sum_prec = prior_precision
        sum_prec_x = prior_mean * prior_precision
        for x_obs, sigma_src in obs_list:
            prec = 1.0 / (sigma_src ** 2)
            sum_prec   += prec
            sum_prec_x += x_obs * prec
        posterior_mean = sum_prec_x / sum_prec
        updated[factor] = float(max(0.0, min(1.0, posterior_mean)))

    return updated
