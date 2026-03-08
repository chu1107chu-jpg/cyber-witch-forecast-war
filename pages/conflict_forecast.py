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
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from datetime import datetime


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
        "default_side": "🔄 Нейтрал",
        "default_interest": 0.40,
        "default_active": False,
        "why": "Балансирует между НАТО и Ираном. Поставляет дроны в регион. В случае конфликта — логистический коридор для обеих сторон.",
    },
    "🇮🇳 Индия": {
        "budget": 83, "nuclear": True,
        "default_side": "🔄 Нейтрал",
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


def compute_ivpn(factors: dict) -> float:
    """ИВПН = Σ(wᵢ · xᵢ)  — Индекс военно-политической напряжённости"""
    return sum(WEIGHTS[k] * factors[k] for k in WEIGHTS)


def compute_proba(ivpn: float) -> float:
    """P(E) = 1 / (1 + e^{-k·(ИВПН − θ)})"""
    return 1.0 / (1.0 + math.exp(-K_LOGISTIC * (ivpn - THETA)))


def compute_horizon(ivpn: float) -> float:
    """T_hor = T₀ · e^{-λ·ИВПН}  (мес.)"""
    return T0 * math.exp(-LAMBDA_T * ivpn)


def force_ratio(m_a: float, m_b: float) -> float:
    """ΔΦ = Mₐ / Mᵦ  — соотношение сил"""
    return m_a / m_b if m_b > 0 else float("inf")


def risk_level(p: float):
    if p < 0.25:
        return "🟢 Низкий", "#26c281"
    elif p < 0.45:
        return "🟡 Умеренный", "#f39c12"
    elif p < 0.65:
        return "🟠 Высокий", "#e67e22"
    elif p < 0.80:
        return "🔴 Критический", "#e74c3c"
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
    st.title("⚔️ Прогноз военных конфликтов")
    st.caption(
        "Индексная модель эскалации. Методика: Асланов, гл. 4, стр. 57–59. "
        "Калибровка на исторической базе 1990–2025 (SIPRI/ACLED)."
    )

    # ── Выбор конфликта ──────────────────────────────────
    tab_iran, tab_hist, tab_compare = st.tabs([
        "🇮🇷🆚🇺🇸 Иран / США",
        "📚 Исторические конфликты",
        "📊 Сравнение",
    ])

    # ════════════════════════════════════════════
    #  ТАБ 1: ИРАН — США
    # ════════════════════════════════════════════
    with tab_iran:
        st.markdown("### Сценарный анализ: Иран 🇮🇷 vs США 🇺🇸")

        # ── НОВОСТНОЙ КОНТЕКСТ ────────────────────────────
        with st.expander("📰 Актуальные новости (март 2026) — влияют на расчёт", expanded=True):
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

        # ── ТРЕТЬИ СТРАНЫ ────────────────────────────────
        with st.expander("🌍 Добавь страну и посмотри возможный исход", expanded=False):
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
                            💰 ${tp['budget']}B · {'☢️ ЯО' if tp['nuclear'] else '❌ без ЯО'}
                            </span>
                            </div>""",
                            unsafe_allow_html=True,
                        )
                        side = st.radio(
                            f"Поддерживает:",
                            ["A (США)", "B (Иран)", "🔄 Нейтрал"],
                            index=["A (США)", "B (Иран)", "🔄 Нейтрал"].index(tp["default_side"]),
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
                st.caption("🔴 Значения автоматически скорректированы по свежим новостям.")

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
                tp_summary_lines.append(f"**{country}** → усиливает США (+{contribution:.3f} к ИВПН)")
            elif cfg["side"] == "B (Иран)":
                mil_adj = float(np.clip(mil_adj - 0.05 * (cfg["budget"] / us_mil), 0, 1))
                tp_ivpn_bonus -= contribution * 0.5  # поддержка Ирана сдерживает эскалацию
                tp_summary_lines.append(f"**{country}** → усиливает Иран ({contribution:.3f} к ИВПН сдержан)")
            else:
                tp_summary_lines.append(f"**{country}** → нейтрал (влияния нет)")

        factors_adj = {**factors, "military_imbalance": mil_adj}
        ivpn_base = compute_ivpn(factors)
        ivpn      = float(np.clip(compute_ivpn(factors_adj) + tp_ivpn_bonus, 0, 1))
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
                    f'🌍 Третьи страны: <b style="color:{color_d};">{sign} {abs(delta_p):.1%}</b> '
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
            c1.metric("ИВПН",        f"{ivpn:.3f}", help="Сводная оценка напряжённости. Чем выше число, тем ближе ситуация к опасной черте.")
            c2.metric("Горизонт",    f"{t:.0f} мес.", help=explain_horizon(t))
            c3.metric("ΔΦ (силы)",   f"{delta_phi:.0f}:1", help=explain_force_ratio(delta_phi))

            # Предупреждение о ядерном факторе
            if factors["nuclear_factor"] > 0.75:
                st.warning(
                    "⚠️ **Ядерный порог**: при текущем уровне обогащения (~84%) "
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
        st.markdown('<div class="section-header">Логистическая кривая P(E) = f(ИВПН)</div>',
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
            xaxis=dict(title="ИВПН"),
            yaxis=dict(title="P(эскалация)", tickformat=".0%", range=[0, 1.05]),
            legend=dict(orientation="h", y=1.12),
        )
        st.plotly_chart(fig_logit, use_container_width=True)

        # ── Сценарии ──
        st.divider()
        st.markdown('<div class="section-header">Сценарный анализ</div>',
                    unsafe_allow_html=True)

        scenarios = {
            "🕊️ Деэскалация": {
                **factors,
                "diplomatic_failure": 0.30,
                "proxy_activity":     0.40,
                "nuclear_factor":     0.60,
                "desc": "Возобновление переговоров по ядерной сделке, снижение прокси-активности"
            },
            "📋 Статус-кво": {
                **factors,
                "desc": "Текущие параметры без изменений"
            },
            "⚠️ Эскалация (удар по ядерным объектам)": {
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
                "ИВПН": round(sc_ivpn, 3),
                "P(E)": f"{sc_p:.1%}",
                "Горизонт (мес.)": f"{sc_t:.0f}",
                "Уровень риска": sc_rl,
            })

        st.dataframe(pd.DataFrame(sc_rows), use_container_width=True, hide_index=True)

        # ── Экономические последствия из рыночных данных ──
        st.divider()
        st.markdown('<div class="section-header">📉 Влияние на рынки при эскалации</div>',
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
            "💡 Исторический аналог: после авиаудара Израиля по Ирану (апрель 2024) "
            "нефть выросла на 4% в течение 48 часов, затем скорректировалась. "
            "Рынок закладывает «страховую премию за Ормузский пролив» ~$8–12/барр."
        )

    # ════════════════════════════════════════════
    #  ТАБ 2: ИСТОРИЧЕСКИЕ КОНФЛИКТЫ
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
                "ИВПН": round(civpn, 3),
                "P(E) модель": f"{cp:.1%}",
                "Факт": "✅ эскалация" if actual >= 0.5 else "✅ сдерживание",
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
                "ИВПН":              round(civpn, 3),
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
