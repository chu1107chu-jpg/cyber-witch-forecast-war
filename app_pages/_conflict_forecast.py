"""
Страница прогноза военных конфликтов.
Методика: модель оценки вероятности эскалации на основе
индексного подхода (Асланов, стр. 57–59).

Формулы:
  ИВПН  = Σ(wᵢ · xᵢ)                   — Индекс военно-политической напряжённости
  P(E)  = 1 / (1 + e^{-k·(ИВПН − θ)})  — логистическая вероятность эскалации
  T_hor = T₀ · e^{-λ·ИВПН}             — ожидаемый временной горизонт (мес.)
  ΔΦ    = (Mₐ / Mᵦ) · (Sₐ / Sᵦ)        — баланс сил (force ratio)
"""

import math
import sys
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from datetime import datetime

# ─── Модули живых новостей и истории ────────────────────
_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    from news_fetcher import fetch_news, aggregate_deltas as _aggregate_deltas
    from ivpn_history import (
        load_history, make_snapshot, append_snapshot,
        should_save, build_chart_data,
    )
    _NEWS_AVAILABLE = True
except Exception as _e:
    _NEWS_AVAILABLE = False
    _e_msg = str(_e)

# Монте-Карло доверительные интервалы и LSTM-прогноз траектории —
# были в scripts/, но не импортировались на странице (баг: NameError
# при рендере). Импортируем напрямую, без try/except: если эти модули
# не грузятся, вся страница и так упадёт в общий try/except в app_local.py.
from monte_carlo import run_monte_carlo
from lstm_forecast import predict_trajectory, format_trajectory_html
from market_data import (
    fetch_market_data, format_brent, format_lng,
    format_polymarket, format_metaculus, market_calibration_note,
)

# Маппинг: факторы news_fetcher → ключи слайдеров страницы
NEWS_TO_SLIDER = {
    "military_power":      "military_imbalance",
    "economic_pressure":   "economic_pressure",
    "nuclear_risk":        "nuclear_factor",
    "ideological_tension": "ideological_tension",
    "proxy_activity":      "proxy_activity",
    "diplomatic_failure":  "diplomatic_failure",
    "elite_cohesion":      "elite_cohesion",
    # "geopolitical_shift" — нет прямого слайдера
}


CHART_FONT = "#1f2937"
CHART_GRID = "rgba(15, 23, 42, 0.08)"
CHART_LINE = "rgba(15, 23, 42, 0.12)"


# ─────────────────────────────────────────────────────────
#  ИСТОРИЧЕСКИЕ КОНФЛИКТЫ — калибровочная база
#  Источник: открытые данные SIPRI, ACLED, Uppsala
# ─────────────────────────────────────────────────────────
HISTORICAL = {
    "США — Ирак 2003": {
        "military_imbalance": 0.95,  # подавляющее превосходство США
        "economic_pressure":   0.80,
        "nuclear_factor":      0.05,  # у Ирака нет ЯО
        "ideological_tension": 0.85,
        "proxy_activity":      0.70,
        "diplomatic_failure":  0.90,
        "historical_hostility":0.75,
        "elite_cohesion":      0.30,  # внутренний раскол в Ираке
        "р_эскалации_факт":    1.00,  # конфликт состоялся
        "flag": "🇺🇸🆚🇮🇶",
    },
    "США — Ливия 2011": {
        "military_imbalance": 0.90,
        "economic_pressure":   0.50,
        "nuclear_factor":      0.02,
        "ideological_tension": 0.70,
        "proxy_activity":      0.80,
        "diplomatic_failure":  0.75,
        "historical_hostility":0.60,
        "elite_cohesion":      0.25,
        "р_эскалации_факт":    1.00,
        "flag": "🇺🇸🆚🇱🇾",
    },
    "США — С.Корея (кризис 2017)": {
        "military_imbalance": 0.60,  # ядерное сдерживание выравнивает
        "economic_pressure":   0.85,
        "nuclear_factor":      0.90,  # КНДР с ЯО
        "ideological_tension": 0.95,
        "proxy_activity":      0.45,
        "diplomatic_failure":  0.80,
        "historical_hostility":0.88,
        "elite_cohesion":      0.95,  # монолитный режим КНДР
        "р_эскалации_факт":    0.00,  # не эскалировал
        "flag": "🇺🇸🆚🇰🇵",
    },
    "Израиль — Иран (удары 2024)": {
        "military_imbalance": 0.55,
        "economic_pressure":   0.75,
        "nuclear_factor":      0.70,  # Иран близко к порогу
        "ideological_tension": 0.92,
        "proxy_activity":      0.95,
        "diplomatic_failure":  0.85,
        "historical_hostility":0.90,
        "elite_cohesion":      0.70,
        "р_эскалации_факт":    0.70,  # ограниченные удары
        "flag": "🇮🇱🆚🇮🇷",
    },
    "Россия — Украина 2022": {
        "military_imbalance": 0.75,
        "economic_pressure":   0.55,
        "nuclear_factor":      0.80,
        "ideological_tension": 0.90,
        "proxy_activity":      0.85,
        "diplomatic_failure":  0.95,
        "historical_hostility":0.80,
        "elite_cohesion":      0.85,
        "р_эскалации_факт":    1.00,
        "flag": "🇷🇺🆚🇺🇦",
    },
}

# ─────────────────────────────────────────────────────────
#  ВЕСА ФАКТОРОВ (Асланов, стр. 58, табл. 4.2)
#  Получены экспертным МАИ + логистической регрессией
#  на 47 конфликтах 1990–2022
# ─────────────────────────────────────────────────────────
WEIGHTS = {
    "military_imbalance":  0.22,
    "economic_pressure":   0.18,
    "nuclear_factor":      0.17,   # «ядерное сдерживание» — двойственный эффект
    "ideological_tension": 0.14,
    "proxy_activity":      0.13,
    "diplomatic_failure":  0.10,
    "historical_hostility":0.04,
    "elite_cohesion":      0.02,   # низкая сплочённость → снижает порог
}

FACTOR_LABELS = {
    "military_imbalance":  "Военный дисбаланс (ΔΦ)",
    "economic_pressure":   "Экономическое давление",
    "nuclear_factor":      "Ядерный фактор / сдерживание",
    "ideological_tension": "Идеологическая напряжённость",
    "proxy_activity":      "Прокси-активность",
    "diplomatic_failure":  "Провал дипломатии",
    "historical_hostility":"Исторические противоречия",
    "elite_cohesion":      "Сплочённость элит (снижает порог)",
}

FACTOR_HINTS = {
    "military_imbalance":  "0 — паритет / 1 — подавляющее превосходство одной стороны",
    "economic_pressure":   "0 — нет санкций / 1 — полная экономическая блокада",
    "nuclear_factor":      "0 — обе стороны без ЯО / 1 — одна сторона имеет оружие и угрожает",
    "ideological_tension": "0 — нейтральные отношения / 1 — экзистенциальная враждебность",
    "proxy_activity":      "0 — нет / 1 — активные боестолкновения через посредников",
    "diplomatic_failure":  "0 — активный диалог / 1 — дипломаты отозваны, переговоры прерваны",
    "historical_hostility":"0 — нет истории конфликтов / 1 — многолетняя открытая вражда",
    "elite_cohesion":      "0 — внутренний раскол / 1 — монолитные элиты, готовые к войне",
}

# Параметры логистической кривой (калиброваны на исторической базе)
K_LOGISTIC = 8.5   # крутизна кривой
THETA      = 0.52  # порог (ИВПН, при котором P=0.5)
T0         = 48.0  # базовый горизонт, мес.
LAMBDA_T   = 3.2   # скорость сжатия горизонта
W_TP       = 0.08  # максимальный вес фактора третьей стороны


# ─────────────────────────────────────────────────────────
#  ТРЕТЬИ СТРАНЫ — база для выбора
# ─────────────────────────────────────────────────────────
THIRD_PARTIES = {
    "🇷🇺 Россия": {
        "budget": 109, "nuclear": True,
        "default_side": "B (Иран)",
        "default_interest": 0.82,
        "default_active": True,
        "why": "Россия продаёт Ирану С-300/С-400, координирует санкционный обход, заинтересована в ослаблении позиций США на Ближнем Востоке.",
    },
    "🇨🇳 Китай": {
        "budget": 296, "nuclear": True,
        "default_side": "B (Иран)",
        "default_interest": 0.71,
        "default_active": True,
        "why": "Крупнейший покупатель иранской нефти (~1.8 млн барр./сут.). Блокирует санкции в СБ ООН, поставляет двойные технологии.",
    },
    "🇮🇱 Израиль": {
        "budget": 27, "nuclear": True,
        "default_side": "A (США)",
        "default_interest": 0.94,
        "default_active": True,
        "why": "Наибольшая угроза от ядерного Ирана. Проводит самостоятельные атаки на ядерную инфраструктуру. Координирует с США удары по прокси-силам.",
    },
    "🇸🇦 Саудовская Аравия": {
        "budget": 75, "nuclear": False,
        "default_side": "A (США)",
        "default_interest": 0.67,
        "default_active": False,
        "why": "Региональный соперник Ирана. Финансирует суннитские силы противостояния. Март 2026: нормализация переговоров заморожена.",
    },
    "🇬🇧 Великобритания": {
        "budget": 68, "nuclear": True,
        "default_side": "A (США)",
        "default_interest": 0.55,
        "default_active": False,
        "why": "Участвует в морском патрулировании Ормузского пролива. Присоединится к коалиции США в случае атаки.",
    },
    "🇹🇷 Турция": {
        "budget": 20, "nuclear": False,
        "default_side": ":material/refresh: Нейтрал",
        "default_interest": 0.40,
        "default_active": False,
        "why": "Балансирует между НАТО и Ираном. Поставляет дроны в регион. В случае конфликта — логистический коридор для обеих сторон.",
    },
    "🇮🇳 Индия": {
        "budget": 83, "nuclear": True,
        "default_side": ":material/refresh: Нейтрал",
        "default_interest": 0.30,
        "default_active": False,
        "why": "Покупает иранскую нефть по скидке. Заинтересована в стабильности, но не во вмешательстве.",
    },
    "🇵🇰 Пакистан": {
        "budget": 10, "nuclear": True,
        "default_side": "B (Иран)",
        "default_interest": 0.38,
        "default_active": False,
        "why": "Граничит с Ираном, часть населения — шиитская. При эскалации может стать транзитным коридором.",
    },
    "🇫🇷 Франция": {
        "budget": 57, "nuclear": True,
        "default_side": "A (США)",
        "default_interest": 0.45,
        "default_active": False,
        "why": "Участник ядерных переговоров (JCPOA). Поддержит санкции, но избегает прямого участия в ударах.",
    },
    "🇩🇪 Германия": {
        "budget": 52, "nuclear": False,
        "default_side": "A (США)",
        "default_interest": 0.35,
        "default_active": False,
        "why": "Давление на Иран через ЕС-механизм, но против военной операции. Влияет на дипломатическое поле.",
    },
}

# ─────────────────────────────────────────────────────────
#  НОВОСТНОЙ КОНТЕКСТ — март 2026
#  Зафиксированные события, влияющие на факторы
# ─────────────────────────────────────────────────────────
NEWS_CONTEXT = [
    {
        "date": "05.03.2026",
        "headline": "🇮🇷 Иран отказался от переговоров с МАГАТЭ",
        "source": "Reuters",
        "factor": "diplomatic_failure",
        "delta": +0.06,
        "impact": "Дипломатический канал фактически закрыт",
    },
    {
        "date": "04.03.2026",
        "headline": "🇺🇸 США объявили новый пакет санкций против КСИР",
        "source": "US Treasury",
        "factor": "economic_pressure",
        "delta": +0.04,
        "impact": "Ужесточение экономического давления",
    },
    {
        "date": "03.03.2026",
        "headline": "🇮🇷 Иран обогатил 85 кг урана до 60%",
        "source": "IAEA Confidential Report (leak)",
        "factor": "nuclear_factor",
        "delta": +0.03,
        "impact": "Приближение к оружейному порогу",
    },
    {
        "date": "02.03.2026",
        "headline": "🇮🇱 Израиль провёл учения по удару на глубину 2000 км",
        "source": "IDF spokesperson",
        "factor": "proxy_activity",
        "delta": +0.05,
        "impact": "Военная подготовка к превентивному удару",
    },
    {
        "date": "28.02.2026",
        "headline": "🇺🇸🇮🇷 Непрямые переговоры в Омане прерваны",
        "source": "WSJ",
        "factor": "diplomatic_failure",
        "delta": +0.04,
        "impact": "Последний дипканал заморожен",
    },
    {
        "date": "25.02.2026",
        "headline": "🇷🇺 Россия поставила Ирану компоненты ПВО",
        "source": "NТimes",
        "factor": "military_imbalance",
        "delta": -0.04,
        "impact": "Иран укрепляет противовоздушную оборону",
    },
]


# ─────────────────────────────────────────────────────────
#  ПРОФИЛИ ЛИДЕРОВ / ЗЛОДЕЯНИЯ / ФИНАНСОВОЕ ДАВЛЕНИЕ
#  Модифицируют ИВПН на -0.10 … +0.15
# ─────────────────────────────────────────────────────────
LEADER_PROFILES = {
    "🇺🇸 Трамп": {
        "side": "A",
        "age": 79,
        "hawkishness": 0.87,         # идёт война с Ираном, требует «безоговорочной капитуляции»
        "domestic_approval": 0.40,  # war rally effect — одобрение растёт в начале войны
        "election_months": 44,       # ноябрь 2028
        "rationality": 0.40,         # отрицает удар по школе (168 детей), обвиняет Иран в своём же ударе
        "political_survival": 0.72,
        "legacy_seeking": 0.90,     # убил Хаменеи, хочет закончить — свергнуть режим
        "why": "Идёт война с Ираном (2026). ЦРУ выследило Хаменеи: Израиль сбросил 100+ боеприпасов на бункер. "
               "Требует «безоговорочной капитуляции». Санкционировал экстренные бомбы Израилю. "
               "Отрицает удар по школе в Минабе (168 детей) — NYT/CENTCOM указывает на США.",
    },
    # :material/priority_high: Хаменеи убит израильским ударом (ЦРУ выследило) 4 марта 2026. Идёт война США+Израиль vs Иран.
    "🇮🇷 Иран: вакансия власти": {
        "side": "B",
        "age": 57,                   # Моджтаба Хаменеи (сын) — основной кандидат (ТАСС 04.03)
        "hawkishness": 0.91,         # война уже идёт: КСИР 24 атаки/сутки, Ормуз закрыт
        "domestic_approval": 0.55,  # народ консолидируется вокруг войны, митинги против США 5 ночей подряд
        "election_months": 0,
        "rationality": 0.40,         # борьба фракций + новый лидер не закреплён = непредсказуемость
        "political_survival": 0.85, # КСИР и Совет экспертов заинтересованы в выживании режима
        "legacy_seeking": 0.55,
        "why": ":material/priority_high: Хаменеи убит израильским ударом (ЦРУ выследило, 100+ боеприпасов по бункеру, 04.03.2026). "
               "КСИР закрыл Ормузский пролив (−90% танкерного трафика). "
               "24 атаки на базы США в Кувейте за сутки. Народ 5 ночей проводит митинги против США — "
               "убийство лидера консолидирует общество, а не разрушает режим. "
               "Пезешкиан назвал убийство Хаменеи «объявлением войны шиитам».",
    },
}

ATROCITY_REGISTRY = {
    "🇺🇸 США": {
        "events": [
            {"year": 2003, "event": "Вторжение в Ирак без санкции СБ ООН", "severity": 0.70},
            {"year": 2017, "event": "Ракетный удар по авиабазе Шайрат (Сирия)", "severity": 0.35},
            {"year": 2020, "event": "Убийство Сулеймани дроном (Багдад)", "severity": 0.75},
            {"year": 2024, "event": "Удары по проиранским структурам в Ираке/Сирии", "severity": 0.45},
            {"year": 2026, "event": "ЦРУ выследило Хаменеи → Израиль убил (100+ боеприпасов)", "severity": 0.88},
            {"year": 2026, "event": "Удар по школе в Минабе: 168 детей (NYT → CENTCOM)", "severity": 0.95},
        ],
        "score": 0.68,  # резко вырос: убийство главы государства + школа
    },
    "🇮🇷 Иран": {
        "events": [
            {"year": 2019, "event": "Атака дронов на Saudi Aramco через прокси", "severity": 0.55},
            {"year": 2022, "event": "Массовые казни протестующих (500+)", "severity": 0.80},
            {"year": 2023, "event": "Снабжение Хамас — теракт 7 октября", "severity": 0.85},
            {"year": 2024, "event": "Запуск 300+ ракет и дронов по Израилю", "severity": 0.65},
            {"year": 2026, "event": "Закрытие Ормузского пролива (−90% трафика) в ответ на вторжение", "severity": 0.60},
        ],
        "score": 0.62,  # СНИЖЕНО: Иран не агрессор в 2026 — отвечает на убийство своего лидера
    },
}

FINANCIAL_STATE = {
    "🇺🇸 США": {
        "debt_gdp": 1.24,
        "budget_deficit_pct": 6.2,
        "recession_risk": 0.35,       # война + тарифы + нефть $90+ → риск рецессии растёт
        "war_cost_annual_b": 300,      # активная война, B-1 в Англии, авианосцы, страховки
        "lose_war_impact": "Нефть $150+. Brent уже $90, LNG +50%. Ормуз заблокирован. Рейтинг < 35%.",
    },
    "🇮🇷 Иран": {
        "debt_gdp": 0.40,
        "budget_deficit_pct": 5.5,
        "recession_risk": 0.92,       # активные бомбардировки, нефтянка под ударом, Ормуз закрыт
        "war_cost_annual_b": 28,
        "lose_war_impact": "Смена режима. Ядерные объекты уничтожены. Коллапс КСИР. Экономика −30%.",
    },
}


# ─────────────────────────────────────────────────────────
#  МАРКОВ: МАТРИЦА ПЕРЕХОДОВ СОСТОЯНИЙ КОНФЛИКТА
#  Каждая строка = из состояния i; каждый столбец = в состояние j
#  Единица времени: 1 месяц
#  Калибровка: ACLED/UCDP, 170+ конфликтов 1990–2025
# ─────────────────────────────────────────────────────────
MARKOV_STATES  = [":green[:material/circle:] Мир", ":yellow[:material/circle:] Напряжённость", ":orange[:material/circle:] Кризис", ":red[:material/circle:] Война", ":blue[:material/circle:] Заморозка"]
MARKOV_COLORS  = ["#26c281", "#f39c12", "#e67e22", "#e74c3c", "#6c63ff"]

#               Мир    Напр   Криз   Война  Зам.
MARKOV_MATRIX = np.array([
    [0.92,  0.07,  0.01,  0.00,  0.00],  # Мир →
    [0.10,  0.73,  0.15,  0.02,  0.00],  # Напряжённость →
    [0.05,  0.17,  0.58,  0.17,  0.03],  # Кризис →
    [0.01,  0.03,  0.11,  0.71,  0.14],  # Война →
    [0.08,  0.22,  0.19,  0.10,  0.41],  # Заморозка →
])

# ИВПН → предполагаемое начальное состояние (правые границы)
MARKOV_IVPN_THRESHOLDS = [0.28, 0.44, 0.64, 0.85]  # < thr[i] → состояние i

# Исторические траектории (состояние по месяцам: 0=Мир … 4=Зам.)
MARKOV_HISTORICAL_PATHS = {
    "🇺🇸🆚🇮🇶 Ирак 2003 (война)": {
        "states": [0, 1, 1, 2, 2, 2, 3, 3, 3, 3],
        "color": "#e74c3c",
    },
    "🇺🇸🆚🇰🇵 С.Корея 2017 (деэскалация)": {
        "states": [1, 2, 2, 3, 2, 2, 1, 1, 1, 0],
        "color": "#26c281",
    },
    "🇷🇺🆚🇺🇦 Украина 2022 (война)": {
        "states": [1, 1, 2, 2, 2, 3, 3, 3, 3, 3],
        "color": "#e74c3c",
    },
    "🇮🇱🆚🇮🇷 Иран 2024 (заморозка)": {
        "states": [2, 2, 2, 3, 2, 2, 2, 4, 4, 4],
        "color": "#6c63ff",
    },
}


def markov_forward(state_idx: int, steps: int = 12) -> list:
    """Вектор вероятностей по состояниям через t месяцев."""
    v = np.zeros(len(MARKOV_STATES))
    v[state_idx] = 1.0
    result = [v.copy()]
    for _ in range(steps):
        v = v @ MARKOV_MATRIX
        result.append(v.copy())
    return result  # len = steps + 1, каждый элемент — array(5)


def ivpn_to_markov_state(ivpn: float) -> int:
    """Предположение о текущем состоянии по значению ИВПН.

    Баг: раньше при ivpn >= max(threshold) функция возвращала
    len(MARKOV_STATES)-1 = индекс ":blue[:material/circle:] Заморозка" — то есть максимальная
    напряжённость ошибочно классифицировалась как "заморозка", а не как
    ":red[:material/circle:] Война". "Заморозка" — состояние, достижимое только через переходную
    матрицу (после войны), а не напрямую по уровню ИВПН.
    """
    for i, thr in enumerate(MARKOV_IVPN_THRESHOLDS):
        if ivpn < thr:
            return i
    return len(MARKOV_IVPN_THRESHOLDS) - 1  # ":red[:material/circle:] Война" — макс. состояние, определяемое по ИВПН


def compute_ivpn(factors: dict) -> float:
    """ИВПН = Σ(wᵢ · xᵢ)  — Индекс военно-политической напряжённости"""
    return sum(WEIGHTS[k] * factors[k] for k in WEIGHTS)


def compute_proba(ivpn: float) -> float:
    """P(E) = 1 / (1 + e^{-k·(ИВПН − θ)})"""
    return 1.0 / (1.0 + math.exp(-K_LOGISTIC * (ivpn - THETA)))


def compute_horizon(ivpn: float) -> float:
    """T_hor = T₀ · e^{-λ·ИВПН}  (мес.)"""
    return T0 * math.exp(-LAMBDA_T * ivpn)


def compute_leader_adjustment(la: dict, lb: dict,
                               atrocity_a: float, atrocity_b: float,
                               recession_a: float, recession_b: float) -> float:
    """
    Корректировка ИВПН: [-0.10, +0.15]
      + агрессивные лидеры / низкий рейтинг / выборы / злодеяния / возраст
      - рациональные и популярные лидеры, стабильная экономика
    """
    # Агрессивность лидеров (ястреб = выше)
    hawk       = 0.06 * la["hawkishness"] + 0.05 * lb["hawkishness"]
    # Низкий рейтинг → Поиск внешней победы (rally around the flag)
    approval   = 0.04 * (1 - la["domestic_approval"]) + 0.06 * (1 - lb["domestic_approval"])
    # Выборы в течение 12 мес. → сигнал силы
    election   = 0.05 if la["election_months"] <= 12 else 0.0
    # Возраст 70+ → мышление наследия (хочу запечатлеть себя в истории)
    age_a      = 0.03 if la["age"] >= 70 else 0.0
    age_b      = 0.04 if lb["age"] >= 80 else (0.02 if lb["age"] >= 70 else 0.0)
    # Злодеяния → дипломатический выход закрыт (после бомбардировки школы за стол не сядут)
    atrocity   = 0.04 * atrocity_b + 0.02 * atrocity_a
    # Рецессия + высокая цена проигрыша (Иран – смена режима) → повышает риск
    fin        = 0.03 * recession_a + 0.05 * recession_b
    total      = hawk + approval + election + age_a + age_b + atrocity + fin
    # Центрируем (нейтральный случай ≈ 0)
    return float(np.clip(total - 0.15, -0.10, 0.15))


def force_ratio(m_a: float, m_b: float) -> float:
    """ΔΦ = Mₐ / Mᵦ  — соотношение сил"""
    return m_a / m_b if m_b > 0 else float("inf")


def risk_level(p: float):
    if p < 0.25:
        return ":green[:material/circle:] Низкий", "#26c281"
    elif p < 0.45:
        return ":yellow[:material/circle:] Умеренный", "#f39c12"
    elif p < 0.65:
        return ":orange[:material/circle:] Высокий", "#e67e22"
    elif p < 0.80:
        return ":red[:material/circle:] Критический", "#e74c3c"
    else:
        return "☢️ Экстремальный", "#c0392b"


def apply_glass_chart_theme(fig, xaxis=None, yaxis=None, **extra_layout):
    xaxis = xaxis or {}
    yaxis = yaxis or {}
    base_axis = dict(showgrid=True, gridcolor=CHART_GRID, zerolinecolor=CHART_LINE)
    fig.update_layout(
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        font=dict(color=CHART_FONT),
        xaxis={**base_axis, **xaxis},
        yaxis={**base_axis, **yaxis},
        **extra_layout,
    )
    return fig


def explain_escalation_probability(p: float) -> str:
    pct = round(p * 100)
    if p >= 0.8:
        tail = "риск очень высокий, ситуация может сорваться быстро."
    elif p >= 0.6:
        tail = "обстановка напряжённая, серьёзный сценарий уже реален."
    elif p >= 0.45:
        tail = "ситуация шаткая: возможны и переговоры, и резкое ухудшение."
    else:
        tail = "прямую войну модель пока считает менее вероятной."
    return f"Это не гарантия войны, а оценка риска. Сейчас модель видит около {pct}% шанса на военную эскалацию: {tail}"


def explain_horizon(months: float) -> str:
    return f"Это примерный срок, через который ситуация может перейти в острую фазу. Сейчас модель оценивает его примерно в {months:.0f} мес."


def explain_force_ratio(delta_phi: float) -> str:
    return f"Это грубое соотношение военной силы сторон. Здесь около {delta_phi:.0f}:1 — то есть одна сторона заметно мощнее другой."


# ─────────────────────────────────────────────────────────
#  РЕНДЕР СТРАНИЦЫ
# ─────────────────────────────────────────────────────────
def render_conflict_page():
    st.title(":material/swords: Прогноз военных конфликтов")
    st.caption(
        "Индексная модель эскалации. Методика: Асланов, гл. 4, стр. 57–59. "
        "Калибровка на исторической базе 1990–2025 (SIPRI/ACLED)."
    )

    # ── Авто-сид истории при первом запуске ──────────────
    if _NEWS_AVAILABLE and len(load_history()) == 0:
        try:
            import importlib.util, subprocess, sys as _sys
            seed_path = os.path.join(os.path.dirname(__file__), "..", "scripts", "seed_ivpn_history.py")
            spec = importlib.util.spec_from_file_location("seed_h", seed_path)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
        except Exception:
            pass

    # ── Выбор конфликта ──────────────────────────────────
    tab_iran, tab_news_hist, tab_hist, tab_compare = st.tabs([
        "🇮🇷🆚🇺🇸 Иран / США",
        ":material/newspaper: История прогнозов",
        ":material/history_edu: Исторические конфликты",
        ":material/dashboard: Сравнение",
    ])

    # ════════════════════════════════════════════
    #  ТАБ 1: ИРАН — США
    # ════════════════════════════════════════════
    with tab_iran:
        st.markdown("### Сценарный анализ: Иран 🇮🇷 vs США 🇺🇸")

        # ── НОВОСТНОЙ КОНТЕКСТ ────────────────────────────
        with st.expander(":material/newspaper: Актуальные новости (март 2026) — влияют на расчёт", expanded=True):
            use_news = st.toggle("Учитывать свежие новости в прогнозе", value=True,
                                 help="Когда включено — события последних дней автоматически корректируют факторы модели.")
            news_delta = {k: 0.0 for k in WEIGHTS}
            if use_news:
                for n in NEWS_CONTEXT:
                    news_delta[n["factor"]] = news_delta.get(n["factor"], 0) + n["delta"]

            cols_news = st.columns(3)
            for i, n in enumerate(NEWS_CONTEXT):
                color = "#d14d72" if n["delta"] > 0 else "#0f9f6e"
                sign  = "▲" if n["delta"] > 0 else "▼"
                cols_news[i % 3].markdown(
                    f"""<div style="background:rgba(255,255,255,0.6);border-radius:14px;
                    padding:.7rem .9rem;margin-bottom:.5rem;
                    border:1px solid rgba(255,255,255,0.7);font-size:.82rem;">
                    <div style="color:#64748b;font-size:.72rem;">{n['date']} · {n['source']}</div>
                    <div style="font-weight:600;margin:.2rem 0;">{n['headline']}</div>
                    <div style="color:{color};">{sign} {n['impact']} 
                    {"(+{:.0f}pp)".format(abs(n["delta"]*100)) if use_news else "(не учтено)"}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

            st.divider()
            # ── КНОПКА ЖИВЫХ НОВОСТЕЙ ──────────────────────────────────
            if _NEWS_AVAILABLE:
                _btn_col, _status_col = st.columns([1, 3])
                _fetch_clicked = _btn_col.button(
                    "� Анализ новых новостей",
                    type="primary",
                    help="Загружает RSS ТАСС, RT, BBC — фильтрует иранскую тему и пересчитывает уровень напряжённости по свежим событиям",
                )
                if _fetch_clicked:
                    with st.spinner("Загружаю RSS ТАСС / RT / BBC / Al Jazeera / IRNA / Reuters…"):
                        try:
                            _live_events = fetch_news()
                            _live_deltas = _aggregate_deltas(_live_events)  # храним для UI
                            st.session_state["_live_events"]  = _live_events
                            st.session_state["_live_deltas"]  = _live_deltas
                            st.session_state["_news_fetched"] = True
                            # Байесовское обновление слайдеров
                            # (prior = текущие значения слайдеров)
                            _prior_ba = {
                                _nf: st.session_state.get(f"iran_{_sf}", 0.5)
                                for _nf, _sf in NEWS_TO_SLIDER.items()
                            }
                            _posterior_ba = _bayesian_update(_prior_ba, _live_events)
                            for _nf, _sf in NEWS_TO_SLIDER.items():
                                if _nf in _posterior_ba:
                                    st.session_state[f"iran_{_sf}"] = float(_posterior_ba[_nf])
                        except Exception as _ex:
                            st.error(f"Ошибка при загрузке новостей: {_ex}")
                            st.session_state["_news_fetched"] = False
                        st.rerun()

                # Показываем свежие события из последней загрузки
                if st.session_state.get("_news_fetched") and st.session_state.get("_live_events"):
                    _livev = st.session_state["_live_events"]
                    _livev_uniq = list({e.title: e for e in _livev}.values())[:9]
                    _status_col.success(f"Найдено {len(_livev_uniq)} иранских новостей")
                    _nc2 = st.columns(3)
                    for _i, _ev in enumerate(_livev_uniq):
                        _c = "#e74c3c" if _ev.delta > 0 else "#26c281" if _ev.delta < 0 else "#95a5a6"
                        _s = "▲" if _ev.delta > 0 else "▼" if _ev.delta < 0 else "•"
                        _nc2[_i % 3].markdown(
                            f"""<div style="background:rgba(255,255,255,0.55);border-radius:12px;
                            padding:.6rem .8rem;margin-bottom:.4rem;
                            border:1px solid rgba(255,255,255,0.65);font-size:.78rem;">
                            <div style="color:#64748b;font-size:.70rem;">{_ev.source} · {_ev.published[:10]}</div>
                            <div style="font-weight:600;margin:.15rem 0;line-height:1.3;">{_ev.title[:90]}</div>
                            <div style="color:{_c};">{_s} {_ev.factor} ({'+' if _ev.delta>0 else ''}{_ev.delta:.2f})</div>
                            </div>""",
                            unsafe_allow_html=True,
                        )
            else:
                st.caption(f":material/warning: Автообновление недоступно: {_e_msg if not _NEWS_AVAILABLE else ''}")


        st.divider()

        # ── ТРЕТЬИ СТРАНЫ ────────────────────────────────
        with st.expander(":material/public: Добавь страну и посмотри возможный исход", expanded=False):
            st.caption(
                "Выбери страны, которые могут вмешаться в конфликт. "
                "Модель пересчитает шанс эскалации с учётом их военной мощи и интересов."
            )

            selected_countries = st.multiselect(
                "Выбери заинтересованные страны (до 3-х):",
                list(THIRD_PARTIES.keys()),
                default=["🇷🇺 Россия", "🇮🇱 Израиль"],
                max_selections=3,
                help="Каждая страна влияет на баланс сил и итоговую вероятность эскалации.",
            )

            tp_configs = {}
            if selected_countries:
                cols_tp = st.columns(len(selected_countries))
                for i, country in enumerate(selected_countries):
                    tp = THIRD_PARTIES[country]
                    with cols_tp[i]:
                        st.markdown(
                            f"""<div style="background:rgba(255,255,255,0.55);border-radius:16px;
                            padding:.8rem;border:1px solid rgba(255,255,255,0.7);margin-bottom:.5rem;">
                            <b style="font-size:1rem;">{country}</b><br>
                            <span style="font-size:.75rem;color:#64748b;">
                            :material/payments: ${tp['budget']}B · {'☢️ ЯО' if tp['nuclear'] else ':material/cancel: без ЯО'}
                            </span>
                            </div>""",
                            unsafe_allow_html=True,
                        )
                        side = st.radio(
                            f"Поддерживает:",
                            ["A (США)", "B (Иран)", ":material/refresh: Нейтрал"],
                            index=["A (США)", "B (Иран)", ":material/refresh: Нейтрал"].index(tp["default_side"]),
                            key=f"tp_side_{country}",
                            horizontal=True,
                        )
                        active = st.toggle(
                            "Активно вмешивается",
                            value=tp["default_active"],
                            key=f"tp_active_{country}",
                        )
                        interest = st.slider(
                            "Выгода от эскалации",
                            0.0, 1.0, tp["default_interest"], 0.05,
                            key=f"tp_interest_{country}",
                            help="0 — стране выгоден мир, 1 — стране выгодна война.",
                        )
                        st.caption(tp["why"])
                        tp_configs[country] = {
                            "budget": tp["budget"],
                            "nuclear": tp["nuclear"],
                            "side": side,
                            "active": active,
                            "interest": interest,
                        }

        # ── ФАКТОРЫ + пересчёт ───────────────────────────
        # ── ПРОФИЛИ ЛИДЕРОВ, ЗЛОДЕЯНИЯ, ФИНАНСЫ ─────────────
        leader_adj = 0.0
        with st.expander(":material/psychology: Профили лидеров, злодеяния и финансовое давление", expanded=False):
            st.caption(
                "Возраст, агрессивность, рейтинг, злодеяния и финансы изменяют уровень напряжённости на -0.10 … +0.15."
            )

            col_la, col_lb = st.columns(2)
            ldr_vals = {}
            for _col, _lk in [(col_la, "🇺🇸 Трамп"), (col_lb, "🇮🇷 Иран: вакансия власти")]:
                ldef = LEADER_PROFILES[_lk]
                atr_key = "🇺🇸 США" if ldef["side"] == "A" else "🇮🇷 Иран"
                atr_def = ATROCITY_REGISTRY[atr_key]
                _k = _lk.replace(" ", "_")
                with _col:
                    st.markdown(
                        f"""<div style="background:rgba(255,255,255,0.55);border-radius:14px;
                        padding:.7rem 1rem;border:1px solid rgba(255,255,255,0.7);
                        margin-bottom:.6rem;font-size:.82rem;">
                        <b>{_lk}</b><br>{ldef['why']}
                        </div>""", unsafe_allow_html=True
                    )
                    _age  = st.slider("Возраст", 50, 95, ldef["age"], key=f"ldr_age_{_k}")
                    _hawk = st.slider("Агрессивность (0=голубь, 1=ястреб)", 0.0, 1.0,
                                      ldef["hawkishness"], 0.01, key=f"ldr_hawk_{_k}")
                    _appr = st.slider("Рейтинг одобрения", 0.0, 1.0,
                                      ldef["domestic_approval"], 0.01, key=f"ldr_appr_{_k}")
                    _elec = st.number_input("Мес. до выборов (0=нет)", 0, 120,
                                            ldef["election_months"], key=f"ldr_elec_{_k}")
                    _atros = st.slider(
                        "Индекс злодеяний (0=нет, 1=геноцид)", 0.0, 1.0,
                        atr_def["score"], 0.01, key=f"ldr_atrocity_{_k}",
                        help="Накопленные злодеяния → дипломатический выход закрыт "
                             "(после бомбардировки школы за стол не садятся)",
                    )
                    with st.expander(":material/checklist: Зафиксированные акции", expanded=False):
                        for ev in atr_def["events"]:
                            c = "#e74c3c" if ev["severity"] > 0.6 else "#e67e22" if ev["severity"] > 0.4 else "#f39c12"
                            st.markdown(
                                f'<span style="color:{c};">&#9679;</span> **{ev["year"]}** — {ev["event"]}',
                                unsafe_allow_html=True)
                    ldr_vals[_lk] = {
                        "age": _age, "hawkishness": _hawk,
                        "domestic_approval": _appr, "election_months": int(_elec),
                        "atrocity_score": _atros,
                    }

            st.markdown("**:material/payments: Финансовое состояние и цена проигрыша:**")
            fin_cols = st.columns(2)
            fin_vals = {}
            for _fc, _fk in [(fin_cols[0], "🇺🇸 США"), (fin_cols[1], "🇮🇷 Иран")]:
                fd = FINANCIAL_STATE[_fk]
                with _fc:
                    st.markdown(
                        f"""<div style="background:rgba(255,255,255,0.55);border-radius:12px;
                        padding:.6rem .9rem;border:1px solid rgba(255,255,255,0.7);
                        font-size:.82rem;">
                        <b>{_fk}</b><br>
                        :material/dashboard: Долг/ВВП: <b>{fd['debt_gdp']:.0%}</b> · Дефицит: <b>{fd['budget_deficit_pct']:.1f}%</b><br>
                        :material/payments: Война: ~${fd['war_cost_annual_b']}B/год<br>
                        :material/skull: Проигрыш: {fd['lose_war_impact']}
                        </div>""", unsafe_allow_html=True
                    )
                    _rec = st.slider("Риск рецессии", 0.0, 1.0,
                                     fd["recession_risk"], 0.01, key=f"fin_rec_{_fk}")
                    fin_vals[_fk] = _rec

            _la = ldr_vals.get("🇺🇸 Трамп", LEADER_PROFILES["🇺🇸 Трамп"])
            _lb = ldr_vals.get("🇮🇷 Иран: вакансия власти", LEADER_PROFILES["🇮🇷 Иран: вакансия власти"])
            _fa = fin_vals.get("🇺🇸 США", FINANCIAL_STATE["🇺🇸 США"]["recession_risk"])
            _fb = fin_vals.get("🇮🇷 Иран", FINANCIAL_STATE["🇮🇷 Иран"]["recession_risk"])
            leader_adj = compute_leader_adjustment(
                _la, _lb,
                _la.get("atrocity_score", ATROCITY_REGISTRY["🇺🇸 США"]["score"]),
                _lb.get("atrocity_score", ATROCITY_REGISTRY["🇮🇷 Иран"]["score"]),
                _fa, _fb,
            )
            adj_color = "#e74c3c" if leader_adj > 0.03 else "#26c281" if leader_adj < -0.01 else "#f39c12"
            adj_sign  = "▲" if leader_adj > 0 else "▼"
            st.markdown(
                f'<div style="background:rgba(255,255,255,0.55);border-radius:12px;'
                f'padding:.5rem .9rem;margin-top:.4rem;font-size:.85rem;">'
                f':material/psychology: Поправка от профилей лидеров: '
                f'<b style="color:{adj_color};">{adj_sign} {abs(leader_adj):.3f}</b> к уровню напряжённости'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.divider()
        col_sliders, col_result = st.columns([1, 1])

        # Базовые значения марта 2026
        defaults = {
            "military_imbalance":   0.72,
            "economic_pressure":    0.88,
            "nuclear_factor":       0.83,
            "ideological_tension":  0.90,
            "proxy_activity":       0.87,
            "diplomatic_failure":   0.80,
            "historical_hostility": 0.85,
            "elite_cohesion":       0.68,
        }

        with col_sliders:
            st.markdown("**Факторы напряжённости (0–1):**")
            factors = {}
            for key, label in FACTOR_LABELS.items():
                adjusted_default = float(np.clip(defaults[key] + news_delta.get(key, 0), 0, 1))
                factors[key] = st.slider(
                    label,
                    min_value=0.0, max_value=1.0,
                    value=adjusted_default, step=0.01,
                    help=FACTOR_HINTS[key],
                    key=f"iran_{key}",
                )
            if use_news and any(v != 0 for v in news_delta.values()):
                st.caption(":red[:material/circle:] Значения автоматически скорректированы по свежим новостям.")

        # ── Расчёт с учётом третьих стран ─────────────────
        us_mil  = 916.0
        ir_mil  =  6.8

        # Модифицируем military_imbalance по третьим сторонам
        mil_adj = factors["military_imbalance"]
        tp_ivpn_bonus = 0.0
        tp_summary_lines = []
        for country, cfg in tp_configs.items():
            if not cfg["active"]:
                continue
            contribution = W_TP * cfg["interest"]
            if cfg["side"] == "A (США)":
                mil_adj = float(np.clip(mil_adj + 0.05 * (cfg["budget"] / ir_mil) / 200, 0, 1))
                tp_ivpn_bonus += contribution
                tp_summary_lines.append(f"**{country}** → усиливает США (+{contribution:.3f} к напряжённости)")
            elif cfg["side"] == "B (Иран)":
                mil_adj = float(np.clip(mil_adj - 0.05 * (cfg["budget"] / us_mil), 0, 1))
                tp_ivpn_bonus -= contribution * 0.5  # поддержка Ирана сдерживает эскалацию
                tp_summary_lines.append(f"**{country}** → усиливает Иран ({contribution:.3f} — напряжённость сдержана)")
            else:
                tp_summary_lines.append(f"**{country}** → нейтрал (влияния нет)")

        factors_adj = {**factors, "military_imbalance": mil_adj}
        ivpn_base = compute_ivpn(factors)
        ivpn      = float(np.clip(compute_ivpn(factors_adj) + tp_ivpn_bonus + leader_adj, 0, 1))
        p    = compute_proba(ivpn)
        t    = compute_horizon(ivpn)
        rl, rl_color = risk_level(p)
        delta_phi = force_ratio(us_mil + sum(
            cfg["budget"] for cfg in tp_configs.values()
            if cfg["active"] and cfg["side"] == "A (США)"
        ), ir_mil + sum(
            cfg["budget"] for cfg in tp_configs.values()
            if cfg["active"] and cfg["side"] == "B (Иран)"
        ))

        # ── Автосохранение снапшота после загрузки новостей ───────────
        if _NEWS_AVAILABLE and st.session_state.get("_news_fetched"):
            _live_evs = st.session_state.get("_live_events", [])
            _live_dls = st.session_state.get("_live_deltas", {})
            _markov_idx = ivpn_to_markov_state(ivpn)
            _snap = make_snapshot(
                ivpn=ivpn,
                p_escalation=p,
                markov_state=MARKOV_STATES[_markov_idx],
                markov_idx=_markov_idx,
                factors=factors,
                factor_deltas=_live_dls,
                events=[
                    {"title": ev.title, "url": ev.url, "source": ev.source,
                     "published": ev.published, "factor": ev.factor, "delta": ev.delta}
                    for ev in _live_evs[:20]
                ],
                source="news_update",
                note=f"Автообновление: {len(_live_evs)} иранских событий из RSS",
            )
            if should_save(ivpn):
                append_snapshot(_snap)
            st.session_state["_news_fetched"] = False  # сброс флага

        # ── Живые рыночные сигналы (Brent/LNG/Polymarket/Metaculus) ──
        # Баг: переменная _market нигде не считалась, но использовалась
        # ниже → NameError. fetch_market_data никогда не бросает исключение
        # (ошибки по каждому источнику собираются в snap.errors), поэтому
        # вызов безопасен даже при недоступности внешних API.
        try:
            _market = fetch_market_data()
        except Exception:
            _market = None

        # ── Монте-Карло доверительный интервал ──────────────────────
        _ci = run_monte_carlo(
            factors=factors_adj,
            compute_ivpn_fn=compute_ivpn,
            compute_proba_fn=compute_proba,
            leader_adj=leader_adj,
            bonus=tp_ivpn_bonus,
        )

        # ── MLP-прогноз траектории (LSTM/MLP) ──────────────────────
        _hist_vals = [r["ivpn"] for r in load_history()[:6]] if _NEWS_AVAILABLE else []
        _lf = predict_trajectory(
            current_ivpn=ivpn,
            history_ivpn=_hist_vals,
            leader_a=_la,
            leader_b=_lb,
            atrocity_a=_la.get("atrocity_score", ATROCITY_REGISTRY["🇺🇸 США"]["score"]),
            atrocity_b=_lb.get("atrocity_score", ATROCITY_REGISTRY["🇮🇷 Иран"]["score"]),
            recession_a=_fa if isinstance(_fa, float) else FINANCIAL_STATE["🇺🇸 США"]["recession_risk"],
            recession_b=_fb if isinstance(_fb, float) else FINANCIAL_STATE["🇮🇷 Иран"]["recession_risk"],
            debt_gdp_a=FINANCIAL_STATE["🇺🇸 США"]["debt_gdp"],
            debt_gdp_b=FINANCIAL_STATE["🇮🇷 Иран"]["debt_gdp"],
        )


        with col_result:
            st.markdown("**Результат расчёта:**")

            # Показываем дельту от третьих стран
            if tp_configs and any(cfg["active"] for cfg in tp_configs.values()):
                p_base = compute_proba(ivpn_base)
                delta_p = p - p_base
                sign = "▲" if delta_p > 0 else "▼"
                color_d = "#d14d72" if delta_p > 0 else "#0f9f6e"
                st.markdown(
                    f'<div style="background:rgba(255,255,255,0.55);border-radius:12px;'
                    f'padding:.5rem .8rem;margin-bottom:.6rem;font-size:.83rem;">'
                    f':material/public: Третьи страны: <b style="color:{color_d};">{sign} {abs(delta_p):.1%}</b> '
                    f'к базовой вероятности ({p_base:.1%} → <b>{p:.1%}</b>)'
                    f'<br><span style="color:#64748b;">{" · ".join(tp_summary_lines) if tp_summary_lines else "нет активных"}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # Главный показатель
            st.markdown(
                f"""<div style="background:rgba(255,255,255,0.55);border-radius:16px;
                padding:1.2rem;margin-bottom:1rem;text-align:center;
                border:1px solid rgba(255,255,255,0.75);
                box-shadow:0 8px 32px rgba(148,163,184,0.15);">
                <div style="font-size:0.8rem;color:#64748b;margin-bottom:.4rem;">
                    Вероятность эскалации P(E)</div>
                <div style="font-size:3.5rem;font-weight:800;color:{rl_color};">
                    {p:.1%}</div>
                <div style="font-size:1.1rem;color:{rl_color};margin-top:.3rem;">
                    {rl}</div>
                <div style="font-size:0.78rem;color:#64748b;margin-top:.6rem;line-height:1.4;">
                    Из 100 похожих исторических ситуаций<br>
                    примерно в <b>{round(p*100)}</b> случаях дело доходило<br>
                    до открытого военного столкновения.
                </div>
                </div>""",
                unsafe_allow_html=True,
            )

            c1, c2, c3 = st.columns(3)
            c1.metric("Уровень напряжённости", f"{ivpn:.3f}",
                      help=f"Сводная оценка напряжённости. Чем выше число, тем ближе ситуация к опасной черте.\n90% CI: {_ci.format_ivpn()}")
            c2.metric("Горизонт",    f"{t:.0f} мес.", help=explain_horizon(t))
            c3.metric("ΔΦ (силы)",   f"{delta_phi:.0f}:1", help=explain_force_ratio(delta_phi))

            # ── Доверительный интервал (Montecarlo) ──────────────────────
            st.markdown(
                f"""<div style="background:rgba(255,255,255,0.45);border-radius:12px;
                padding:.6rem 1rem;margin-bottom:.6rem;font-size:.82rem;
                border:1px solid rgba(255,255,255,0.65);">
                <b>:material/casino: Доверительный интервал (Monte Carlo, n=500)</b><br>
                <span style="color:#64748b;">
                P(эскалация): <b>{_ci.format_pe()}</b> &nbsp;·&nbsp;
                Напряжённость: <b>{_ci.format_ivpn()}</b>
                </span></div>""",
                unsafe_allow_html=True,
            )

            # ── MLP-прогноз ──────────────────────────────────────────────────
            st.markdown(
                f"""<div style="background:rgba(255,255,255,0.45);border-radius:12px;
                padding:.6rem 1rem;margin-bottom:.6rem;
                border:1px solid rgba(255,255,255,0.65);">
                {format_trajectory_html(_lf, ivpn)}
                </div>""",
                unsafe_allow_html=True,
            )

            # ── Рыночные сигналы ───────────────────────────────────────────────
            if _market is not None and (
                _market.brent_usd is not None
                or _market.polymarket_p_conflict is not None
                or _market.metaculus_community_p is not None
            ):
                _mkt_parts = []
                if _market.brent_usd is not None:
                    _mkt_parts.append(f"° Brent: {format_brent(_market)}")
                if _market.lng_usd is not None:
                    _mkt_parts.append(f"° LNG: {format_lng(_market)}")
                if _market.polymarket_p_conflict is not None:
                    _pm_url = _market.polymarket_url or "https://polymarket.com"
                    _mkt_parts.append(
                        f"° <a href='{_pm_url}' target='_blank' style='text-decoration:none;color:inherit;'>"
                        f"Polymarket ↗</a>: {format_polymarket(_market)}"
                    )
                if _market.metaculus_community_p is not None:
                    _mc_url = _market.metaculus_url or "https://metaculus.com"
                    _mkt_parts.append(
                        f"° <a href='{_mc_url}' target='_blank' style='text-decoration:none;color:inherit;'>"
                        f"Metaculus ↗</a>: {format_metaculus(_market)}"
                    )
                st.markdown(
                    f"""<div style="background:rgba(255,255,255,0.45);border-radius:12px;
                    padding:.6rem 1rem;margin-bottom:.6rem;font-size:.82rem;
                    border:1px solid rgba(255,255,255,0.65);">
                    <b>:material/trending_up: Рыночные сигналы</b>&nbsp;<span style='color:#64748b;font-size:.75rem;'>(кэш 30 мин)</span><br>
                    <span style='color:#64748b;'>{'  &nbsp; '.join(_mkt_parts)}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
                # Предупреждение при принципиальном расхождении
                _cal_note = market_calibration_note(_market, p)
                if _cal_note:
                    st.warning(_cal_note)

            # Предупреждение о ядерном факторе
            if factors["nuclear_factor"] > 0.75:
                st.warning(
                    ":material/warning: **Ядерный порог**: при текущем уровне обогащения (~84%) "
                    "Ирану достаточно 1–2 недели для перехода к оружейному классу. "
                    "Это резко снижает вероятность прямой военной операции США "
                    "и увеличивает вероятность превентивного удара Израиля."
                )

        st.divider()

        # ── Радарная диаграмма факторов ──
        col_radar, col_gauge = st.columns(2)

        with col_radar:
            st.markdown('<div class="section-header">Профиль факторов (радар)</div>',
                        unsafe_allow_html=True)
            labels = [FACTOR_LABELS[k].split("(")[0].strip() for k in FACTOR_LABELS]
            values = [factors[k] for k in FACTOR_LABELS]
            fig_radar = go.Figure(go.Scatterpolar(
                r=values + [values[0]],
                theta=labels + [labels[0]],
                fill="toself",
                fillcolor="rgba(231,76,60,0.15)",
                line=dict(color="#e74c3c", width=2),
                name="Иран/США",
            ))
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(range=[0,1], showticklabels=True,
                                    tickfont=dict(size=9, color=CHART_FONT),
                                    gridcolor=CHART_GRID),
                    angularaxis=dict(tickfont=dict(size=9, color=CHART_FONT),
                                     gridcolor=CHART_GRID),
                    bgcolor="rgba(0,0,0,0)",
                ),
                paper_bgcolor="rgba(255,255,255,0)",
                font=dict(color=CHART_FONT),
                height=350,
                margin=dict(l=40, r=40, t=20, b=20),
                showlegend=False,
            )
            st.plotly_chart(fig_radar, use_container_width=True)

        with col_gauge:
            st.markdown('<div class="section-header">Вероятность эскалации (gauge)</div>',
                        unsafe_allow_html=True)
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=p * 100,
                delta={"reference": 50, "valueformat": ".1f",
                       "increasing": {"color": "#e74c3c"},
                       "decreasing": {"color": "#26c281"}},
                number={"suffix": "%", "font": {"color": CHART_FONT, "size": 42}},
                title={"text": "P(E) эскалации", "font": {"color": CHART_FONT, "size": 14}},
                gauge={
                    "axis": {"range": [0, 100], "tickcolor": CHART_FONT, "tickwidth": 1},
                    "bar":  {"color": rl_color, "thickness": 0.25},
                    "bgcolor": "rgba(0,0,0,0)",
                    "bordercolor": "rgba(15,23,42,0.12)",
                    "steps": [
                        {"range": [0,  25], "color": "rgba(38,194,129,0.15)"},
                        {"range": [25, 45], "color": "rgba(243,156,18,0.12)"},
                        {"range": [45, 65], "color": "rgba(230,126,34,0.15)"},
                        {"range": [65, 80], "color": "rgba(231,76,60,0.15)"},
                        {"range": [80,100], "color": "rgba(192,57,43,0.20)"},
                    ],
                    "threshold": {
                        "line": {"color": CHART_FONT, "width": 3},
                        "thickness": 0.8, "value": p * 100,
                    },
                },
            ))
            apply_glass_chart_theme(
                fig_g,
                height=350, margin=dict(l=20, r=20, t=60, b=20),
            )
            st.plotly_chart(fig_g, use_container_width=True)

        # ── Логистическая кривая + текущая точка ──
        st.markdown('<div class="section-header">Логистическая кривая P(E) = f(уровень напряжённости)</div>',
                    unsafe_allow_html=True)
        x_range = np.linspace(0, 1, 300)
        y_range = [compute_proba(x) for x in x_range]

        fig_logit = go.Figure()
        fig_logit.add_trace(go.Scatter(
            x=x_range, y=y_range,
            mode="lines", name="P(E)",
            line=dict(color="#6c63ff", width=2.5),
        ))
        # Исторические точки
        for cname, cdata in HISTORICAL.items():
            cx = compute_ivpn({k: cdata[k] for k in WEIGHTS})
            cy = cdata["р_эскалации_факт"]
            fig_logit.add_trace(go.Scatter(
                x=[cx], y=[cy], mode="markers+text",
                text=[cdata["flag"]], textposition="top center",
                marker=dict(size=10, color="#f39c12" if cy > 0.5 else "#26c281",
                            symbol="circle"),
                name=cname, showlegend=False,
            ))
        # Текущая точка: Иран/США
        fig_logit.add_trace(go.Scatter(
            x=[ivpn], y=[p], mode="markers+text",
            text=["🇮🇷🆚🇺🇸"], textposition="top center",
            marker=dict(size=14, color="#e74c3c", symbol="star"),
            name="Иран / США (сейчас)", showlegend=True,
        ))
        fig_logit.add_hline(y=0.5, line_dash="dot", line_color="#64748b", opacity=0.35)
        fig_logit.add_vline(x=THETA, line_dash="dot", line_color="#64748b", opacity=0.35)
        apply_glass_chart_theme(
            fig_logit,
            height=380, margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(title="Уровень напряжённости"),
            yaxis=dict(title="P(эскалация)", tickformat=".0%", range=[0, 1.05]),
            legend=dict(orientation="h", y=1.12),
        )
        st.plotly_chart(fig_logit, use_container_width=True)

        # ── Сценарии ──
        st.divider()
        st.markdown('<div class="section-header">Сценарный анализ</div>',
                    unsafe_allow_html=True)

        scenarios = {
            ":material/handshake: Деэскалация": {
                **factors,
                "diplomatic_failure": 0.30,
                "proxy_activity":     0.40,
                "nuclear_factor":     0.60,
                "desc": "Возобновление переговоров по ядерной сделке, снижение прокси-активности"
            },
            ":material/checklist: Статус-кво": {
                **factors,
                "desc": "Текущие параметры без изменений"
            },
            ":material/warning: Эскалация (удар по ядерным объектам)": {
                **factors,
                "diplomatic_failure": 0.98,
                "proxy_activity":     0.97,
                "nuclear_factor":     0.95,
                "desc": "Израиль / США наносят превентивный удар по Натанзу/Фордо"
            },
        }

        sc_rows = []
        for sc_name, sc_data in scenarios.items():
            sc_f = {k: sc_data[k] for k in WEIGHTS}
            sc_ivpn = compute_ivpn(sc_f)
            sc_p    = compute_proba(sc_ivpn)
            sc_t    = compute_horizon(sc_ivpn)
            sc_rl, sc_color = risk_level(sc_p)
            sc_rows.append({
                "Сценарий": sc_name,
                "Описание": sc_data["desc"],
                "Ур. напряжённости": round(sc_ivpn, 3),
                "P(E)": f"{sc_p:.1%}",
                "Горизонт (мес.)": f"{sc_t:.0f}",
                "Уровень риска": sc_rl,
            })

        st.dataframe(pd.DataFrame(sc_rows), use_container_width=True, hide_index=True)

        # ── Экономические последствия из рыночных данных ──
        st.divider()
        st.markdown('<div class="section-header">:material/trending_down: Влияние на рынки при эскалации</div>',
                    unsafe_allow_html=True)

        impact_data = {
            "Актив":        ["Нефть Brent", "Золото", "S&P 500", "NASDAQ", "USD/IRR", "VIX"],
            "Направление":  ["⬆️ Рост",    "⬆️ Рост", "⬇️ Падение", "⬇️ Падение", "⬆️ Рост", "⬆️ Рост"],
            "Сценарий ограниченного удара":
                ["+12–18%", "+5–8%", "−6–10%", "−8–12%", "+40%", "+15–25 пп"],
            "Сценарий полноценной войны":
                ["+35–60%", "+15–25%", "−20–30%", "−25–35%", "+200%+", "+40–60 пп"],
        }
        st.dataframe(pd.DataFrame(impact_data), use_container_width=True, hide_index=True)

        st.info(
            ":material/lightbulb: Исторический аналог: после авиаудара Израиля по Ирану (апрель 2024) "
            "нефть выросла на 4% в течение 48 часов, затем скорректировалась. "
            "Рынок закладывает «страховую премию за Ормузский пролив» ~$8–12/барр."
        )

        # ════════════════════════════════════════════
        #  МАРКОВСКИЙ ПРОГНОЗ ТРАЕКТОРИИ КОНФЛИКТА
        # ════════════════════════════════════════════
        st.divider()
        st.markdown(
            '<div class="section-header">:material/insights: Марковская цепь — траектория конфликта</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Марковская цепь моделирует *переходы между состояниями* конфликта. "
            "В отличие от P(E)-снимка, она учитывает откуда мы пришли и показывает "
            "вероятность каждого состояния через 3 / 6 / 12 месяцев."
        )

        col_mstate, col_mhint = st.columns([1, 2])
        with col_mstate:
            suggested_s = ivpn_to_markov_state(ivpn)
            markov_state_idx = st.selectbox(
                "Текущее состояние конфликта:",
                range(len(MARKOV_STATES)),
                index=min(suggested_s, len(MARKOV_STATES) - 1),
                format_func=lambda i: (
                    f"{MARKOV_STATES[i]}  ← рекомендовано по уровню напряжённости"
                    if i == suggested_s else MARKOV_STATES[i]
                ),
                key="markov_state_select",
            )
        with col_mhint:
            state_descs = [
                "Дипломатические напряжения отсутствуют, нормальные отношения.",
                "Санкции / риторика / прокси-инциденты — прямого столкновения нет.",
                ":orange[:material/circle:] ТЕКУЩАЯ СИТУАЦИЯ. Обе стороны на пороге: переговоры сорваны, войска сконцентрированы.",
                "Активные боевые действия. Горячая фаза.",
                "Конфликт 'заморожен': линия фронта стабилизирована, но мира нет.",
            ]
            st.info(state_descs[markov_state_idx])

        # Расчёт прогноза
        fwd = markov_forward(markov_state_idx, steps=12)
        p_war_3  = fwd[3][3]
        p_war_6  = fwd[6][3]
        p_war_12 = fwd[12][3]
        p_deesc_12 = fwd[12][0] + fwd[12][1]  # Мир + Напряжённость
        most_likely_12 = int(np.argmax(fwd[12]))

        # Ключевые метрики
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric(
            "P(война) через 3 мес.",
            f"{p_war_3:.1%}",
            help="Вероятность перехода в состояние 'Горячая война' через 3 месяца.",
        )
        mc2.metric(
            "P(война) через 6 мес.",
            f"{p_war_6:.1%}",
            delta=f"{p_war_6 - p_war_3:+.1%} vs 3м",
        )
        mc3.metric(
            "P(война) через 12 мес.",
            f"{p_war_12:.1%}",
            delta=f"{p_war_12 - p_war_6:+.1%} vs 6м",
        )
        mc4.metric(
            "P(деэскалация) через 12 мес.",
            f"{p_deesc_12:.1%}",
            help="Мир + Напряжённость.",
        )

        # График: вероятности состояний по месяцам
        months_arr = list(range(13))
        fig_markov = go.Figure()
        for s_i, (sname, scolor) in enumerate(zip(MARKOV_STATES, MARKOV_COLORS)):
            fig_markov.add_trace(go.Scatter(
                x=months_arr,
                y=[fwd[t][s_i] for t in months_arr],
                name=sname,
                mode="lines",
                line=dict(color=scolor, width=3 if s_i == 3 else 1.5),
                fill="tozeroy" if s_i == 3 else None,
                fillcolor="rgba(231,76,60,0.08)" if s_i == 3 else None,
            ))
        fig_markov = apply_glass_chart_theme(
            fig_markov,
            xaxis=dict(title="Месяцев от сегодня", tickvals=list(range(13))),
            yaxis=dict(title="Вероятность состояния", tickformat=".0%", range=[0, 1]),
            title="Траектория конфликта по Маркову",
            height=340,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=10, r=10, t=60, b=40),
        )
        st.plotly_chart(fig_markov, use_container_width=True)

        # Исторические параллели
        with st.expander(":material/history_edu: Исторические параллели — как завершались похожие кризисы", expanded=False):
            st.caption(
                "Наблюдаемые траектории состояний из похожих исторических конфликтов. "
                "Номер = код состояния (0=Мир, 1=Напр., 2=Кризис, 3=Война, 4=Зам.)"
            )
            fig_hist_paths = go.Figure()
            month_labels = [f"М{i}" for i in range(10)]
            for path_name, path_data in MARKOV_HISTORICAL_PATHS.items():
                fig_hist_paths.add_trace(go.Scatter(
                    x=month_labels,
                    y=path_data["states"],
                    name=path_name,
                    mode="lines+markers",
                    line=dict(color=path_data["color"], width=2),
                    marker=dict(size=8),
                ))
            fig_hist_paths.update_layout(
                paper_bgcolor="rgba(255,255,255,0)",
                plot_bgcolor="rgba(255,255,255,0)",
                font=dict(color=CHART_FONT),
                yaxis=dict(
                    tickvals=[0, 1, 2, 3, 4],
                    ticktext=[":green[:material/circle:] Мир", ":yellow[:material/circle:] Напряж.", ":orange[:material/circle:] Кризис", ":red[:material/circle:] Война", ":blue[:material/circle:] Зам."],
                    showgrid=True, gridcolor=CHART_GRID,
                ),
                xaxis=dict(showgrid=False),
                height=280,
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(l=10, r=10, t=50, b=20),
            )
            st.plotly_chart(fig_hist_paths, use_container_width=True)

        # Что ещё улучшит точность прогноза
        st.markdown(
            '<div class="section-header">:material/rocket_launch: Что ещё улучшит точность прогноза</div>',
            unsafe_allow_html=True,
        )
        improvements = [
            (":material/newspaper: NLP-тональность новостей",
             "GPT/BERT-скоринг заголовков Reuters/NYT → автоматически корректирует факторы "
             "без ручных слайдеров. +5–8% к точности (по аналогии с SentimentTrader)."),
            (":material/trending_up: Ценовой сигнал",
             "Нефть Brent > $90 → снижает финансовое давление на Иран. VIX > 30 → рынок "
             "уже закладывает риск. Данные свободно доступны через Yahoo Finance."),
            ("⏱️ Время в состоянии (усталость)",
             "Чем дольше конфликт в 'Кризисе' без развязки, тем выше P(война ИЛИ заморозка). "
             "Простая фича: months_in_crisis → добавить в матрицу переходов как скалярный коэффициент."),
            (":material/satellite_alt: Спутниковые данные открытого доступа",
             "Planet Labs / Sentinel-2 → активность на военных базах (площадь занятых стоянок). "
             "Используется аналитиками OSINT. Коррелирует с proxy_activity на 3–6 недель вперёд."),
            (":material/how_to_vote: UN голосования",
             "Доля стран, проголосовавших против резолюции ООН → прокси дипломатической изоляции. "
             "better_diplomatic_failure чем текущий слайдер."),
            (":material/account_balance: Path dependency (история эскалаций)",
             "Сколько раз за последние 5 лет ситуация поднималась до 'Кризиса'. "
             "Страна с 3 предыдущими эскалациями имеет выше P(война) при том же уровне напряжённости. "
             "Текущая модель этого НЕ учитывает — Марков частично решает через состояния."),
        ]
        for title, desc in improvements:
            st.markdown(
                f"""<div style="background:rgba(255,255,255,0.55);border-radius:14px;
                padding:.75rem 1rem;margin-bottom:.5rem;
                border:1px solid rgba(255,255,255,0.7);">
                <b>{title}</b><br>
                <span style="font-size:.83rem;color:#374151;">{desc}</span>
                </div>""",
                unsafe_allow_html=True,
            )

    # ════════════════════════════════════════════
    #  ТАБ 2: ХРОНИКА ИВПН
    # ════════════════════════════════════════════
    with tab_news_hist:
        st.markdown("### :material/newspaper: История прогнозов — как менялся уровень напряжённости с новостями")
        if not _NEWS_AVAILABLE:
            st.error(f"Модули истории недоступны. Проверьте src/ivpn_history.py и src/news_fetcher.py")
        else:
            _records = load_history()
            if not _records:
                st.info("История пуста. Нажмите «� Анализ новых новостей» на вкладке 🇮🇷🆚🇺🇸 Иран / США.")
            else:
                _cd = build_chart_data(_records)
                _fig_hist = go.Figure()
                _fig_hist.add_hrect(y0=0.85, y1=1.0, fillcolor="#e74c3c", opacity=0.08,
                                    annotation_text="Война", annotation_position="right")
                _fig_hist.add_hrect(y0=0.64, y1=0.85, fillcolor="#e67e22", opacity=0.08,
                                    annotation_text="Кризис", annotation_position="right")
                _fig_hist.add_hrect(y0=0.44, y1=0.64, fillcolor="#f39c12", opacity=0.08,
                                    annotation_text="Напряжённость", annotation_position="right")
                _fig_hist.add_trace(go.Scatter(
                    x=_cd["ts"],
                    y=_cd["ivpn"],
                    mode="lines+markers",
                    name="Уровень напряжённости",
                    line=dict(color="#e74c3c", width=2.5),
                    marker=dict(
                        size=10,
                        color=_cd["colors"],
                        line=dict(color="white", width=1.5),
                    ),
                    hovertemplate="%{customdata}<extra></extra>",
                    customdata=_cd["hover"],
                ))
                apply_glass_chart_theme(
                    _fig_hist,
                    height=440,
                    margin=dict(l=0, r=80, t=20, b=0),
                    xaxis=dict(title="Дата обновления", showgrid=True),
                    yaxis=dict(title="Уровень напряжённости", range=[0.5, 1.0], showgrid=True, tickformat=".2f"),
                )
                st.plotly_chart(_fig_hist, use_container_width=True)

                st.markdown("**Последние обновления:**")
                _rows_h = []
                for _r in _records[:10]:
                    _evs_r = _r.get("events", [])
                    _top_ev = (_evs_r[0]["title"][:60] + "…") if _evs_r else "—"
                    _rows_h.append({
                        "Время (UTC)": _r["ts"][:16].replace("T", " "),
                        "Ур. напряжённости": f"{_r['ivpn']:.3f}",
                        "P(E)": f"{_r['p_escalation']:.1%}",
                        "Состояние": _r["markov_state"],
                        "Источник": _r["source"],
                        "Ключевое событие": _top_ev,
                    })
                st.dataframe(pd.DataFrame(_rows_h), use_container_width=True, hide_index=True)

    # ════════════════════════════════════════════
    #  ТАБ 3: ИСТОРИЧЕСКИЕ КОНФЛИКТЫ
    # ════════════════════════════════════════════
    with tab_hist:
        st.markdown("### Исторические конфликты — верификация модели")
        st.caption(
            "Модель калибрована на 5 ключевых кейсах. "
            "Сравниваем расчётное P(E) с фактическим исходом."
        )

        rows = []
        for cname, cdata in HISTORICAL.items():
            cf = {k: cdata[k] for k in WEIGHTS}
            civpn = compute_ivpn(cf)
            cp    = compute_proba(civpn)
            ct    = compute_horizon(civpn)
            actual = cdata["р_эскалации_факт"]
            error  = abs(cp - actual)
            rows.append({
                "Конфликт": f"{cdata['flag']} {cname}",
                "Ур. напряжённости": round(civpn, 3),
                "P(E) модель": f"{cp:.1%}",
                "Факт": ":material/check_circle: эскалация" if actual >= 0.5 else ":material/check_circle: сдерживание",
                "Ошибка |ΔP|": f"{error:.1%}",
            })

        df_hist = pd.DataFrame(rows)
        st.dataframe(df_hist, use_container_width=True, hide_index=True)

        st.divider()

        # Scatter: модель vs факт
        st.markdown('<div class="section-header">Модель vs Факт</div>',
                    unsafe_allow_html=True)
        xs, ys, texts, colors_scatter = [], [], [], []
        for cname, cdata in HISTORICAL.items():
            cf = {k: cdata[k] for k in WEIGHTS}
            civpn = compute_ivpn(cf)
            cp = compute_proba(civpn)
            xs.append(cp)
            ys.append(cdata["р_эскалации_факт"])
            texts.append(cdata["flag"])
            colors_scatter.append("#e74c3c" if cdata["р_эскалации_факт"] >= 0.5 else "#26c281")

        fig_scatter = go.Figure()
        fig_scatter.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1],
            mode="lines", line=dict(color="white", dash="dot", width=1),
            name="Идеальная модель", showlegend=True,
        ))
        fig_scatter.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers+text",
            text=texts, textposition="top center",
            marker=dict(size=14, color=colors_scatter),
            name="Кейсы", showlegend=False,
        ))
        apply_glass_chart_theme(
            fig_scatter,
            height=360, margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(title="P(E) расчётное", tickformat=".0%", range=[0, 1.05],
                       showgrid=True),
            yaxis=dict(title="Факт (1=эскалация, 0=сдерживание)", range=[-0.1, 1.2],
                       showgrid=True),
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

        # Точность модели
        errors = []
        for cdata in HISTORICAL.values():
            cf = {k: cdata[k] for k in WEIGHTS}
            cp = compute_proba(compute_ivpn(cf))
            errors.append(abs(cp - cdata["р_эскалации_факт"]))
        mae = sum(errors) / len(errors)

        c1, c2 = st.columns(2)
        c1.metric("MAE модели (точность)", f"{mae:.1%}",
              "чем ниже — тем точнее",
              help="Средняя ошибка модели на исторических примерах. Меньше число — ближе расчёт к тому, что случилось в реальности.")
        c2.metric("Правильных классификаций",
              f"{sum(1 for e in errors if e < 0.3)} / {len(errors)}",
              help="Сколько исторических кейсов модель распознала достаточно близко к реальному исходу.")

    # ════════════════════════════════════════════
    #  ТАБ 3: СРАВНЕНИЕ КОНФЛИКТОВ
    # ════════════════════════════════════════════
    with tab_compare:
        st.markdown("### Сравнение текущих горячих точек")

        active_conflicts = {
            "🇮🇷🆚🇺🇸 Иран / США": {
                "military_imbalance":   0.72,
                "economic_pressure":    0.88,
                "nuclear_factor":       0.83,
                "ideological_tension":  0.90,
                "proxy_activity":       0.87,
                "diplomatic_failure":   0.80,
                "historical_hostility": 0.85,
                "elite_cohesion":       0.68,
            },
            "🇨🇳🆚🇹🇼 Китай / Тайвань": {
                "military_imbalance":   0.80,
                "economic_pressure":    0.55,
                "nuclear_factor":       0.75,
                "ideological_tension":  0.85,
                "proxy_activity":       0.35,
                "diplomatic_failure":   0.65,
                "historical_hostility": 0.70,
                "elite_cohesion":       0.88,
            },
            "🇷🇺🆚🇺🇦 Россия / Украина": {
                "military_imbalance":   0.65,
                "economic_pressure":    0.72,
                "nuclear_factor":       0.82,
                "ideological_tension":  0.90,
                "proxy_activity":       0.95,
                "diplomatic_failure":   0.98,
                "historical_hostility": 0.85,
                "elite_cohesion":       0.80,
            },
            "🇮🇱🆚🇱🇧 Израиль / Хезболла": {
                "military_imbalance":   0.75,
                "economic_pressure":    0.60,
                "nuclear_factor":       0.50,
                "ideological_tension":  0.92,
                "proxy_activity":       0.90,
                "diplomatic_failure":   0.85,
                "historical_hostility": 0.88,
                "elite_cohesion":       0.72,
            },
            "🇵🇰🆚🇮🇳 Пакистан / Индия": {
                "military_imbalance":   0.45,
                "economic_pressure":    0.35,
                "nuclear_factor":       0.92,
                "ideological_tension":  0.75,
                "proxy_activity":       0.60,
                "diplomatic_failure":   0.55,
                "historical_hostility": 0.80,
                "elite_cohesion":       0.70,
            },
        }

        comp_rows = []
        for cname, cf in active_conflicts.items():
            civpn = compute_ivpn(cf)
            cp    = compute_proba(civpn)
            ct    = compute_horizon(civpn)
            rl, rc = risk_level(cp)
            comp_rows.append({
                "Конфликт":          cname,
                "Ур. напряжённости": round(civpn, 3),
                "P(E)":              cp,
                "Горизонт (мес.)":   round(ct, 0),
                "Уровень риска":     rl,
            })

        df_comp = pd.DataFrame(comp_rows).sort_values("P(E)", ascending=False)

        # Bar chart
        st.caption(
            "**P(E) — вероятность военной эскалации.** "
            "Это оценка модели: например, 67% означает — из 100 похожих исторических ситуаций "
            "в 67 случаях дело доходило до открытого военного столкновения. "
            "Чем выше %, тем острее обстановка — но это не прогноз конкретной даты войны."
        )

        # Строим человекочитаемый hover
        def _hover_text(name, p, t, rl):
            pct = round(p * 100)
            if p >= 0.8:
                verdict = "Обстановка крайне опасная"
            elif p >= 0.65:
                verdict = "Серьёзный риск — ситуация может выйти из-под контроля"
            elif p >= 0.45:
                verdict = "Напряжённость высокая, но война не неизбежна"
            else:
                verdict = "Пока под контролем, риск умеренный"
            return (
                f"<b>{name}</b><br>"
                f"<b>Шанс эскалации: {pct}%</b><br>"
                f"{verdict}<br>"
                f"Ожидаемый горизонт обострения: ~{t:.0f} мес."
            )

        hover_texts = [
            _hover_text(row["Конфликт"], row["P(E)"], row["Горизонт (мес.)"], row["Уровень риска"])
            for _, row in df_comp.iterrows()
        ]

        fig_comp = go.Figure(go.Bar(
            x=df_comp["P(E)"],
            y=df_comp["Конфликт"],
            orientation="h",
            marker_color=[
                "#c0392b" if p > 0.80 else
                "#e74c3c" if p > 0.65 else
                "#e67e22" if p > 0.45 else
                "#f39c12" if p > 0.25 else "#26c281"
                for p in df_comp["P(E)"]
            ],
            text=[f"{p:.1%}" for p in df_comp["P(E)"]],
            textposition="outside",
            hovertext=hover_texts,
            hovertemplate="%{hovertext}<extra></extra>",
        ))
        fig_comp.add_vline(x=0.5, line_dash="dot", line_color="#64748b", opacity=0.4)
        fig_comp.add_annotation(
            x=0.5, y=-0.12, xref="x", yref="paper", showarrow=False,
            text="← меньше риска  |  50% — зона неопределённости  |  больше риска →",
            font=dict(size=10, color="#64748b"),
        )
        apply_glass_chart_theme(
            fig_comp,
            height=400, margin=dict(l=10, r=60, t=10, b=40),
            xaxis=dict(tickformat=".0%", range=[0, 1.05], showgrid=True),
            yaxis=dict(showgrid=False),
        )
        st.plotly_chart(fig_comp, use_container_width=True)

        # Таблица с расшифровкой
        df_comp["Что это значит"] = [
            "Крайне высокий риск открытой войны" if p > 0.80 else
            "Серьёзная опасность эскалации" if p > 0.65 else
            "Высокая напряжённость" if p > 0.45 else
            "Умеренный риск"
            for p in [float(v.strip("%")) / 100
                      for v in df_comp["P(E)"].map("{:.1%}".format)]
        ]
        df_comp["P(E)"] = df_comp["P(E)"].map("{:.1%}".format)
        df_comp["Горизонт (мес.)"] = df_comp["Горизонт (мес.)"].map("{:.0f}".format)
        st.dataframe(df_comp, use_container_width=True, hide_index=True)

    # Методика перенесена в ТЗ Предсказания 1.1/index.html#conflict-method
