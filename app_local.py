"""
Предсказания — локальное демо-приложение.
Запуск: streamlit run app_local.py
Не требует Supabase / внешних API. Использует обученные модели из data/artifacts/sklearn/.
"""
import json
import os
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
#  Константы
# ─────────────────────────────────────────────
ARTIFACTS = Path(__file__).parent / "data/artifacts/sklearn"
TICKERS_US = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "BRK-B", "XOM", "JPM",
    "BTC-USD", "ETH-USD", "GC=F", "^GSPC", "^IXIC",
]
TICKERS_RU = [
    "SBER.ME", "GAZP.ME", "LKOH.ME", "NVTK.ME", "ROSN.ME",
    "GMKN.ME", "YNDX.ME", "MGNT.ME", "MTSS.ME", "ALRS.ME",
    "TATN.ME", "PIKK.ME", "PLZL.ME", "RTKM.ME", "VTBR.ME",
]
TICKERS = TICKERS_US + TICKERS_RU

CHART_FONT = "#1f2937"
CHART_GRID = "rgba(15, 23, 42, 0.08)"
CHART_LINE = "rgba(15, 23, 42, 0.12)"

ARTIFACTS_OLD  = Path(__file__).parent / "data/artifacts/sklearn"
ARTIFACTS_LGBM = Path(__file__).parent / "data/artifacts/lgbm"
# Используем LightGBM если есть, иначе старые sklearn
ARTIFACTS = ARTIFACTS_LGBM if (ARTIFACTS_LGBM / "models.pkl").exists() else ARTIFACTS_OLD
USING_LGBM = ARTIFACTS == ARTIFACTS_LGBM

TICKER_LABELS = {
    # US
    "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Google", "AMZN": "Amazon",
    "NVDA": "NVIDIA", "META": "Meta", "TSLA": "Tesla", "BRK-B": "Berkshire",
    "XOM": "ExxonMobil", "JPM": "JPMorgan", "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum", "GC=F": "Gold", "^GSPC": "S&P 500", "^IXIC": "NASDAQ",
    # RU
    "SBER.ME": "Сбербанк", "GAZP.ME": "Газпром", "LKOH.ME": "ЛУКОЙЛ",
    "NVTK.ME": "НОВАТЭК", "ROSN.ME": "Роснефть", "GMKN.ME": "Норникель",
    "YNDX.ME": "Яндекс", "MGNT.ME": "Магнит", "MTSS.ME": "МТС",
    "ALRS.ME": "АЛРОСА", "TATN.ME": "Татнефть", "PIKK.ME": "ПИК",
    "PLZL.ME": "Полюс", "RTKM.ME": "Ростелеком", "VTBR.ME": "ВТБ",
}

MARKET_FLAGS = {
    **{t: "🇺🇸" for t in TICKERS_US},
    **{t: "🇷🇺" for t in TICKERS_RU},
}

# ─────────────────────────────────────────────
#  Страница
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Предсказания",
    page_icon=":material/insights:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Глобальные стили
st.markdown("""
<style>
.stApp {
    background:
        radial-gradient(circle at 0% 0%, rgba(125, 211, 252, 0.35), transparent 28%),
        radial-gradient(circle at 100% 0%, rgba(196, 181, 253, 0.28), transparent 25%),
        linear-gradient(180deg, #f7fbff 0%, #eef4fb 52%, #e9f0f8 100%);
    color: #18212f;
}
.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
}
[data-testid="stMetricValue"] { font-size: 1.5rem; font-weight: 700; color: #162033; }
[data-testid="stMetricLabel"] { font-size: 0.82rem; opacity: .78; color: #4b5563; }
[data-testid="stMetricDelta"] { color: #5b6472; }
.metric-up   { color: #0f9f6e; }
.metric-down { color: #d14d72; }
.section-header {
    font-size: 1.1rem; font-weight: 600;
    border-left: 3px solid rgba(99, 102, 241, 0.85);
    padding-left: .6rem; margin: 1.2rem 0 .6rem;
    color: #18212f;
}
div[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(255,255,255,0.82), rgba(244,248,255,0.70));
    backdrop-filter: blur(20px);
    border-right: 1px solid rgba(255,255,255,0.55);
}
div[data-testid="stSidebar"] * { color: #1f2937; }
[data-testid="stHeader"] {
    background: rgba(255,255,255,0.35);
    backdrop-filter: blur(14px);
}
[data-testid="stToolbar"] { right: 1rem; }
[data-testid="stAppViewContainer"] {
    background: transparent;
}
div[data-testid="stMetric"],
div[data-testid="stDataFrame"],
div[data-testid="stPlotlyChart"],
div.stAlert,
div[data-baseweb="select"],
div[data-baseweb="input"],
div[data-baseweb="base-input"],
div.stButton > button,
div[data-testid="stExpander"],
div[data-testid="stTabs"] {
    backdrop-filter: blur(18px);
}
div[data-testid="stMetric"],
div[data-testid="stPlotlyChart"],
div[data-testid="stDataFrame"] {
    background: linear-gradient(180deg, rgba(255,255,255,0.72), rgba(255,255,255,0.48));
    border: 1px solid rgba(255,255,255,0.62);
    box-shadow: 0 12px 40px rgba(148, 163, 184, 0.16);
    border-radius: 22px;
    padding: .6rem .8rem;
}
div[data-testid="stAlert"] {
    background: rgba(255,255,255,0.68);
    border: 1px solid rgba(255,255,255,0.7);
    border-radius: 18px;
    color: #1f2937;
}
div[data-testid="stTabs"] button[role="tab"] {
    background: rgba(255,255,255,0.52);
    border: 1px solid rgba(255,255,255,0.7);
    border-radius: 999px;
    margin-right: .4rem;
    color: #334155;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    background: linear-gradient(135deg, rgba(255,255,255,0.95), rgba(224,231,255,0.9));
    color: #312e81;
}
div[data-baseweb="select"] > div,
div[data-baseweb="base-input"] > div,
div[data-baseweb="input"] > div {
    background: rgba(255,255,255,0.70);
    border: 1px solid rgba(255,255,255,0.7);
    border-radius: 16px;
}
div.stButton > button {
    background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(224,231,255,0.88));
    color: #1e1b4b;
    border: 1px solid rgba(255,255,255,0.85);
    border-radius: 14px;
}
</style>
""", unsafe_allow_html=True)


def apply_glass_chart_theme(fig, xaxis=None, yaxis=None, **extra_layout):
    """Единый светлый glass-стиль для Plotly."""
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


def explain_probability(p: float, horizon: str) -> str:
    pct = round(p * 100)
    if p >= 0.7:
        mood = "сильный шанс роста"
    elif p >= 0.55:
        mood = "умеренно позитивный сигнал"
    elif p >= 0.45:
        mood = "неопределённая ситуация"
    elif p >= 0.3:
        mood = "повышенный риск снижения"
    else:
        mood = "высокая вероятность снижения"
    return f"Это оценка модели: примерно {pct}% шанс, что актив будет выше через {horizon}. Простыми словами — сейчас это {mood}."


def explain_return(r: float, horizon: str) -> str:
    pct = r * 100
    direction = "выше" if pct >= 0 else "ниже"
    return (
        f"Это не гарантия, а средняя оценка модели. Она ожидает, что цена через {horizon} будет "
        f"примерно на {abs(pct):.2f}% {direction} текущей."
    )


def explain_signal_count(count: int, total: int, horizon: str) -> str:
    return (
        f"Из {total} инструментов модель считает, что {count} с большей вероятностью покажут рост через {horizon}. "
        f"Это быстрый индикатор общего настроения рынка."
    )


def explain_price(last_close: float, delta_pct: float) -> str:
    return (
        f"Последняя доступная цена закрытия. Сейчас актив стоит около ${last_close:,.2f}. "
        f"За прошлую сессию цена изменилась на {delta_pct:+.2%}."
    )


# ─────────────────────────────────────────────
#  Загрузка моделей и макро (кэш)
# ─────────────────────────────────────────────
@st.cache_resource(show_spinner="Загружаю модели…")
def load_models():
    models   = joblib.load(ARTIFACTS / "models.pkl")
    features = joblib.load(ARTIFACTS / "feature_cols.pkl")
    with open(ARTIFACTS / "train_summary.json") as f:
        summary = json.load(f)
    return models, features, summary


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_macro() -> pd.DataFrame:
    """Загружаем VIX, TNX, DXY — нужны для LightGBM признаков."""
    if not USING_LGBM:
        return pd.DataFrame()
    macro_tickers = {"vix": "^VIX", "tnx": "^TNX", "dxy": "DX-Y.NYB"}
    frames = {}
    for name, sym in macro_tickers.items():
        try:
            df = yf.download(sym, period="3y", auto_adjust=True, progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            frames[name] = df["Close"].rename(name)
        except Exception:
            pass
    return pd.concat(frames.values(), axis=1).ffill() if frames else pd.DataFrame()


@st.cache_data(ttl=300, show_spinner="Загружаю котировки…")
def fetch_data(ticker: str, period: str = "2y") -> pd.DataFrame:
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df = df.dropna()
    return df


def build_features(df: pd.DataFrame, macro: pd.DataFrame = None) -> pd.DataFrame:
    """Строим 39 признаков для LightGBM (без leakage). Совместимо со старой моделью."""
    d = df.copy()
    c = d["Close"]
    macro = macro if macro is not None and not macro.empty else pd.DataFrame()

    # Доходности
    for n in [1, 2, 3, 5, 10, 20]:
        d[f"ret{n}"] = c.pct_change(n)
    d["log_ret1"] = np.log(c / c.shift(1))

    # RSI-14
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    d["rsi14"] = 100 - 100 / (1 + gain / (loss + 1e-9))

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    d["macd_h"]    = macd - macd.ewm(span=9, adjust=False).mean()
    d["macd_sign"] = (macd > 0).astype(float)

    # ATR
    hl = d["High"] - d["Low"]
    hc = (d["High"] - c.shift()).abs()
    lc = (d["Low"]  - c.shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    d["atr14"] = tr.rolling(14).mean() / (c + 1e-9)

    # Bollinger Bands
    ma20  = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    d["bb_pos"]   = (c - ma20) / (2 * std20 + 1e-9)
    d["bb_width"] = (4 * std20) / (ma20 + 1e-9)

    # Волатильность
    d["vol5"]      = c.pct_change().rolling(5).std()
    d["vol10"]     = c.pct_change().rolling(10).std()
    d["vol20"]     = c.pct_change().rolling(20).std()
    d["vol_ratio"] = d["vol5"] / (d["vol20"] + 1e-9)

    # Скользящие средние
    for m in [10, 20, 50, 200]:
        d[f"ma{m}_ratio"] = c / (c.rolling(m, min_periods=m//2).mean() + 1e-9)

    # 52-week hi/lo
    r52h = c.rolling(252, min_periods=60).max()
    r52l = c.rolling(252, min_periods=60).min()
    d["dist_hi52"]  = (r52h - c) / (r52h + 1e-9)
    d["dist_lo52"]  = (c - r52l) / (r52l + 1e-9)
    d["hl52_range"] = (r52h - r52l) / (r52l + 1e-9)

    # Объём
    v_ma = d["Volume"].rolling(20).mean() if "Volume" in d.columns else pd.Series(1, index=d.index)
    d["vol_rel"]   = (d["Volume"] if "Volume" in d.columns else 1) / (v_ma + 1e-9)
    d["vol_spike"] = (d["vol_rel"] > 2.0).astype(float)
    # vol_ratio = vol10/vol20 (как в обучающем скрипте)
    d["vol_ratio"] = d["vol10"] / (d["vol20"] + 1e-9)

    # Momentum
    d["mom10"]      = c / (c.shift(10) + 1e-9) - 1
    d["mom20"]      = c / (c.shift(20) + 1e-9) - 1
    d["mom_cross"]  = (d["mom10"] > d["mom20"]).astype(float)
    d["ma_cross_20_50"] = (c.rolling(20).mean() > c.rolling(50).mean()).astype(float)
    # mom_5_20 = ret5 / |ret20| (как в обучающем скрипте)
    d["mom_5_20"]   = d["ret5"] / (d["ret20"].abs() + 1e-9)

    # Сезонность
    d["dow"]          = d.index.dayofweek.astype(float)   # как в train_lgbm.py
    d["day_of_week"]  = d["dow"]
    d["month"]        = d.index.month.astype(float)
    d["week_of_year"] = d.index.isocalendar().week.astype(float)

    # Макро
    if not macro.empty:
        d = d.join(macro.reindex(d.index).ffill(), how="left")
        for col in macro.columns:
            if col in d.columns:
                roll_mean = d[col].rolling(60, min_periods=20).mean()
                roll_std  = d[col].rolling(60, min_periods=20).std()
                d[f"{col}_z"]   = (d[col] - roll_mean) / (roll_std + 1e-9)
                d[f"{col}_ret"] = d[col].pct_change(5)
                d.drop(columns=[col], inplace=True)

    return d.dropna()


def predict_ticker(ticker: str, models, feature_cols, macro=None):
    df_raw = fetch_data(ticker, "2y")
    if df_raw.empty or len(df_raw) < 250:
        return None, df_raw
    df = build_features(df_raw, macro)
    if df.empty:
        return None, df_raw

    # Проверяем наличие всех нужных признаков
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        return None, df_raw

    X_last = df[feature_cols].iloc[[-1]].values
    result = {}
    for target, model in models.items():
        try:
            val = float(model.predict_proba(X_last)[0][1])
        except Exception:
            val = 0.5
        result[target] = val

    return result, df_raw


# ─────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## :material/insights: Предсказания")
    st.caption("Рыночные прогнозы на базе ML")
    st.divider()

    page = st.radio(
        "Раздел",
        [":material/dashboard: Дашборд", ":material/search: Тикер", ":material/swords: Конфликты", ":material/toll: Монетка", ":material/volunteer_activism: Донат"],
        label_visibility="collapsed",
    )
    st.divider()

    st.markdown(
        '<a href="/arena/" target="_blank" style="'
        "display:block;text-align:center;padding:12px;margin:8px 0;"
        "background:linear-gradient(135deg,#ff2d7b,#b84dff);"
        "color:#fff;border-radius:20px;text-decoration:none;"
        "font-weight:700;font-size:14px;"
        'letter-spacing:1px;">:material/sports_esports: ПОЛИТИЧЕСКАЯ АРЕНА</a>',
        unsafe_allow_html=True,
    )
    st.divider()

    if page == ":material/search: Тикер":
        market_filter = st.radio("Рынок", ["🇺🇸 США", "🇷🇺 Россия"], horizontal=True)
        pool = TICKERS_US if market_filter == "🇺🇸 США" else TICKERS_RU
        sel_ticker = st.selectbox(
            "Тикер",
            pool,
            format_func=lambda t: f"{t} — {TICKER_LABELS.get(t, '')}",
        )
        period = st.select_slider(
            "История", ["3mo", "6mo", "1y", "2y", "5y"], value="1y"
        )

    st.caption(f"Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")


# ─────────────────────────────────────────────
#  Загружаем модели
# ─────────────────────────────────────────────
try:
    models, feature_cols, train_summary = load_models()
    models_loaded = True
except Exception as e:
    models_loaded = False
    st.error(f"Не удалось загрузить модели: {e}")
    st.info("Запусти `python scripts/train_now.py` для обучения.")


# ═══════════════════════════════════════════════
#  СТРАНИЦА: ДАШБОРД
# ═══════════════════════════════════════════════
if page == ":material/dashboard: Дашборд":
    st.title(":material/dashboard: Рыночный дашборд")
    st.caption("Прогнозы на основе обученных моделей. Обновляется каждые 5 минут.")

    if not models_loaded:
        st.stop()

    # Табы по рынкам
    tab_us, tab_ru = st.tabs(["🇺🇸 США / Крипто / Индексы", "🇷🇺 Россия (MOEX)"])

    # Метка горизонтов в зависимости от модели
    H1_KEY  = "target_p5_up"  if USING_LGBM else "target_p1_up"
    H2_KEY  = "target_p20_up"
    H1_LABEL = "p↑(5д)"  if USING_LGBM else "p↑(1д)"
    H2_LABEL = "p↑(20д)"
    H1_DESC  = "5 дней" if USING_LGBM else "1 день"

    def run_forecasts(ticker_list, label):
        rows = []
        prog = st.progress(0, text=f"Загружаю {label}…")
        for i, ticker in enumerate(ticker_list):
            prog.progress((i + 1) / len(ticker_list), text=f"↓ {ticker}")
            try:
                pred, _ = predict_ticker(ticker, models, feature_cols, macro_data)
                if pred:
                    rows.append({
                        "Тикер":    ticker,
                        "Название": TICKER_LABELS.get(ticker, ticker),
                        H1_LABEL:   pred.get(H1_KEY,  0.5),
                        H2_LABEL:   pred.get(H2_KEY,  0.5),
                    })
            except Exception:
                pass
        prog.empty()
        return rows

    def render_market_tab(ticker_list, label):
        with st.spinner(f"Считаю прогнозы — {label}…"):
            rows = run_forecasts(ticker_list, label)
        if not rows:
            st.warning("Нет данных. Проверьте интернет.")
            return
        df_table = pd.DataFrame(rows)

        # Сводные метрики
        up1  = (df_table[H1_LABEL] > 0.5).sum()
        up20 = (df_table[H2_LABEL] > 0.5).sum()
        best   = df_table.loc[df_table[H1_LABEL].idxmax(), "Тикер"]
        best_p = df_table[H1_LABEL].max()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f":material/trending_up: Растут за {H1_DESC}", f"{up1} / {len(rows)}",
              help=explain_signal_count(up1, len(rows), H1_DESC))
        c2.metric(":material/trending_up: Растут за 20д", f"{up20} / {len(rows)}",
              help=explain_signal_count(up20, len(rows), "20 дней"))
        c3.metric(":material/emoji_events: Лучший сигнал", f"{best}", f"{best_p:.1%} вверх",
              help=f"Наибольшая вероятность роста среди всех инструментов. У {best} — {best_p:.0%}.")
        c4.metric(":material/calendar_month: Дата прогноза", datetime.now().strftime("%d.%m.%Y"),
              help="Дата последнего пересчёта прогнозов.")

        if USING_LGBM:
            st.caption(
                f":material/smart_toy: **LightGBM v2** · реальная точность на данных 2024–2026: "
                f"**53.3%** (5 дней) · **56.5%** (20 дней) при уверенных сигналах >55%"
            )
        st.divider()

        col_l, col_r = st.columns([1, 1])
        with col_l:
            st.markdown(f'<div class="section-header">Прогноз роста ({H1_DESC})</div>', unsafe_allow_html=True)
            df_sorted = df_table.sort_values(H1_LABEL, ascending=True)
            colors = ["#26c281" if p > 0.5 else "#e74c3c" for p in df_sorted[H1_LABEL]]
            fig_bar = go.Figure(go.Bar(
                x=df_sorted[H1_LABEL], y=df_sorted["Тикер"],
                orientation="h", marker_color=colors,
                text=[f"{p:.1%}" for p in df_sorted[H1_LABEL]], textposition="outside",
            ))
            fig_bar.add_vline(x=0.5, line_dash="dot", line_color="#64748b", opacity=0.5)
            apply_glass_chart_theme(
                fig_bar,
                height=max(300, len(rows) * 28),
                margin=dict(l=10, r=50, t=10, b=10),
                xaxis=dict(tickformat=".0%", range=[0, 1]),
                yaxis=dict(showgrid=False), showlegend=False,
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_r:
            st.markdown('<div class="section-header">Прогноз роста (20 дней)</div>', unsafe_allow_html=True)
            df_r20 = df_table.sort_values(H2_LABEL, ascending=True)
            colors20 = ["#26c281" if p > 0.5 else "#e74c3c" for p in df_r20[H2_LABEL]]
            fig_r20 = go.Figure(go.Bar(
                x=df_r20[H2_LABEL], y=df_r20["Тикер"],
                orientation="h", marker_color=colors20,
                text=[f"{p:.1%}" for p in df_r20[H2_LABEL]], textposition="outside",
            ))
            fig_r20.add_vline(x=0.5, line_dash="dot", line_color="#64748b", opacity=0.5)
            apply_glass_chart_theme(
                fig_r20,
                height=max(300, len(rows) * 28),
                margin=dict(l=10, r=60, t=10, b=10),
                xaxis=dict(tickformat=".0%", range=[0, 1]),
                yaxis=dict(showgrid=False), showlegend=False,
            )
            st.plotly_chart(fig_r20, use_container_width=True)

        st.markdown('<div class="section-header">Все прогнозы</div>', unsafe_allow_html=True)
        display = df_table.copy()
        display[H1_LABEL] = display[H1_LABEL].map("{:.1%}".format)
        display[H2_LABEL] = display[H2_LABEL].map("{:.1%}".format)
        st.dataframe(display, use_container_width=True, hide_index=True)

    with tab_us:
        render_market_tab(TICKERS_US, "США / Крипто")
    with tab_ru:
        render_market_tab(TICKERS_RU, "Россия MOEX")



# ═══════════════════════════════════════════════
#  СТРАНИЦА: ТИКЕР
# ═══════════════════════════════════════════════
elif page == ":material/search: Тикер":
    ticker = sel_ticker
    label  = TICKER_LABELS.get(ticker, ticker)
    st.title(f":material/search: {ticker} — {label}")

    if not models_loaded:
        st.stop()

    with st.spinner(f"Загружаю {ticker}…"):
        pred, df_raw = predict_ticker(ticker, models, feature_cols, macro_data)

    if df_raw.empty:
        st.error("Нет данных по тикеру.")
        st.stop()

    # ── Последняя цена ──
    last_row  = df_raw.iloc[-1]
    prev_row  = df_raw.iloc[-2]
    last_close = float(last_row["Close"])
    prev_close = float(prev_row["Close"])
    delta_pct  = (last_close - prev_close) / prev_close

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Цена (last close)", f"${last_close:,.2f}",
              f"{delta_pct:+.2%} vs пред. день",
              help=explain_price(last_close, delta_pct))
    _h1_key = "target_p5_up" if USING_LGBM else "target_p1_up"
    _h1_lbl = "5 дней"       if USING_LGBM else "1 день"
    if pred:
        p5  = pred.get(_h1_key, 0.5)
        p20 = pred.get("target_p20_up", 0.5)
        c2.metric(f"p↑ ({_h1_lbl})", f"{p5:.1%}",
                  "бычий" if p5 > 0.55 else "медвежий" if p5 < 0.45 else "нейтрально",
                  help=explain_probability(p5, _h1_lbl))
        c3.metric("p↑ (20 дней)", f"{p20:.1%}",
                  "бычий" if p20 > 0.55 else "медвежий" if p20 < 0.45 else "нейтрально",
                  help=explain_probability(p20, "20 дней"))
        c4.metric("Сигнал",
                  ":green[:material/circle:] РОСТ" if p5 > 0.55 else ":red[:material/circle:] СНИЖЕНИЕ" if p5 < 0.45 else ":gray[:material/circle:] НЕЙТРАЛЬНО",
                  help="Сигнал считается надёжным только если вероятность >55% или <45%.")
    else:
        c2.metric("Прогноз", "н/д", help="По этому активу сейчас недостаточно данных для расчёта.")

    st.divider()

    # ── График цены ──
    st.markdown('<div class="section-header">График цены</div>',
                unsafe_allow_html=True)

    df_plot = df_raw.tail({"3mo": 63, "6mo": 126, "1y": 252,
                            "2y": 504, "5y": 1260}.get(period, 252))

    # Скользящие средние
    df_plot = df_plot.copy()
    df_plot["MA50"]  = df_plot["Close"].rolling(50).mean()
    df_plot["MA200"] = df_plot["Close"].rolling(200).mean()

    fig = go.Figure()
    # Candle / area
    fig.add_trace(go.Scatter(
        x=df_plot.index, y=df_plot["Close"],
        mode="lines", name="Цена",
        line=dict(color="#6c63ff", width=2),
        fill="tozeroy", fillcolor="rgba(108,99,255,0.07)",
    ))
    fig.add_trace(go.Scatter(
        x=df_plot.index, y=df_plot["MA50"],
        mode="lines", name="MA50",
        line=dict(color="#f39c12", width=1.5, dash="dot"),
    ))
    fig.add_trace(go.Scatter(
        x=df_plot.index, y=df_plot["MA200"],
        mode="lines", name="MA200",
        line=dict(color="#e74c3c", width=1.5, dash="dash"),
    ))
    apply_glass_chart_theme(
        fig,
        height=380, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Volume + RSI ──
    col_v, col_rsi = st.columns(2)

    with col_v:
        st.markdown('<div class="section-header">Объём</div>',
                    unsafe_allow_html=True)
        if "Volume" in df_plot.columns and df_plot["Volume"].sum() > 0:
            vol_colors = ["#26c281" if c >= o else "#e74c3c"
                          for c, o in zip(df_plot["Close"], df_plot["Open"])]
            fig_vol = go.Figure(go.Bar(
                x=df_plot.index, y=df_plot["Volume"],
                marker_color=vol_colors, name="Volume",
            ))
            apply_glass_chart_theme(
                fig_vol,
                height=220, margin=dict(l=0, r=0, t=0, b=0),
                showlegend=False,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True),
            )
            st.plotly_chart(fig_vol, use_container_width=True)
        else:
            st.info("Объём недоступен для этого инструмента.")

    with col_rsi:
        st.markdown('<div class="section-header">RSI-14</div>',
                    unsafe_allow_html=True)
        df_feat = build_features(df_raw, macro_data)
        if not df_feat.empty and "rsi14" in df_feat.columns:
            rsi_plot = df_feat["rsi14"].tail(len(df_plot))
            rsi_colors = [
                "#e74c3c" if r > 70 else "#26c281" if r < 30 else "#6c63ff"
                for r in rsi_plot
            ]
            fig_rsi = go.Figure(go.Scatter(
                x=rsi_plot.index, y=rsi_plot,
                mode="lines", line=dict(color="#6c63ff", width=1.5),
            ))
            fig_rsi.add_hrect(y0=70, y1=100, fillcolor="rgba(231,76,60,0.1)",
                               line_width=0)
            fig_rsi.add_hrect(y0=0, y1=30, fillcolor="rgba(38,194,129,0.1)",
                               line_width=0)
            fig_rsi.add_hline(y=70, line_color="#e74c3c", line_dash="dot", opacity=0.5)
            fig_rsi.add_hline(y=30, line_color="#26c281", line_dash="dot", opacity=0.5)
            apply_glass_chart_theme(
                fig_rsi,
                height=220, margin=dict(l=0, r=0, t=0, b=0),
                showlegend=False,
                yaxis=dict(range=[0, 100], showgrid=True),
                xaxis=dict(showgrid=False),
            )
            st.plotly_chart(fig_rsi, use_container_width=True)

    # ── Прогнозная карточка ──
    if pred:
        st.divider()
        st.markdown('<div class="section-header">Детальный прогноз</div>',
                    unsafe_allow_html=True)
        col_g, col_t = st.columns([1, 2])

        with col_g:
            # Gauge для p5_up / p1_up
            _h1_k = "target_p5_up" if USING_LGBM else "target_p1_up"
            _h1_title = "Вероятность роста (5 дней)" if USING_LGBM else "Вероятность роста завтра"
            p1 = pred[_h1_k]
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=p1 * 100,
                title={"text": _h1_title, "font": {"color": "white"}},
                number={"suffix": "%", "font": {"color": "white", "size": 36}},
                gauge={
                    "axis": {"range": [0, 100], "tickcolor": "white"},
                    "bar":  {"color": "#6c63ff"},
                    "bgcolor": "rgba(0,0,0,0)",
                    "bordercolor": "rgba(255,255,255,0.1)",
                    "steps": [
                        {"range": [0, 40],  "color": "rgba(231,76,60,0.2)"},
                        {"range": [40, 60], "color": "rgba(255,255,255,0.05)"},
                        {"range": [60, 100],"color": "rgba(38,194,129,0.2)"},
                    ],
                    "threshold": {
                        "line": {"color": "white", "width": 2},
                        "thickness": 0.75,
                        "value": p1 * 100,
                    },
                },
            ))
            fig_gauge.update_layout(
                height=260, margin=dict(l=20, r=20, t=40, b=20),
                paper_bgcolor="rgba(255,255,255,0)", font=dict(color=CHART_FONT),
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

        with col_t:
            _p5k  = "target_p5_up"  if USING_LGBM else "target_p1_up"
            _p5l  = "5 дней"        if USING_LGBM else "1 день"
            p_h1  = pred[_p5k]
            p_h20 = pred["target_p20_up"]
            if USING_LGBM:
                st.markdown(f"""
| Горизонт | Вероятность роста | Сигнал |
|----------|-------------------|--------|
| **{_p5l}** | `{p_h1:.1%}` | {":green[:material/circle:] Рост" if p_h1 > 0.5 else ":red[:material/circle:] Падение"} |
| **20 дней** | `{p_h20:.1%}` | {":green[:material/circle:] Рост" if p_h20 > 0.5 else ":red[:material/circle:] Падение"} |
""")
            else:
                proj_1d  = last_close * (1 + pred["target_r1"])
                proj_20d = last_close * (1 + pred["target_R20"])
                st.markdown(f"""
| Метрика | Значение | Проекция цены |
|---------|----------|--------------|
| **r¹ (1 день)** | `{pred['target_r1']:+.4f}` | `${proj_1d:,.2f}` |
| **R²⁰ (20 дней)** | `{pred['target_R20']:+.4f}` | `${proj_20d:,.2f}` |
| **p↑ (t+1)** | `{p_h1:.1%}` | {":green[:material/circle:] Рост" if p_h1 > 0.5 else ":red[:material/circle:] Падение"} |
| **p↑ (t+20)** | `{p_h20:.1%}` | {":green[:material/circle:] Рост" if p_h20 > 0.5 else ":red[:material/circle:] Падение"} |
""")
            signal_color = "#26c281" if p_h1 > 0.5 else "#e74c3c"
            signal_text  = "ПОКУПКА" if p_h1 > 0.6 else \
                           "ПРОДАЖА" if p_h1 < 0.4 else "НЕЙТРАЛЬНО"
            st.markdown(
                f'<div style="text-align:center; margin-top:1rem;">'
                f'<span style="background:{signal_color};color:#fff;padding:.4rem 1.2rem;'
                f'border-radius:6px;font-weight:700;font-size:1.1rem;">'
                f'Сигнал: {signal_text}</span></div>',
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════
#  СТРАНИЦА: КОНФЛИКТЫ
# ═══════════════════════════════════════════════
elif page == ":material/swords: Конфликты":
    try:
        import importlib, sys
        # Безопасный reload: перезагружаем только если оба модуля уже в sys.modules
        mod_key = "app_pages._conflict_forecast"
        if mod_key in sys.modules and "pages" in sys.modules:
            importlib.reload(sys.modules[mod_key])
        from app_pages._conflict_forecast import render_conflict_page
        render_conflict_page()
    except Exception as _cf_err:
        import traceback as _tb
        st.error(f":material/cancel: Ошибка загрузки раздела конфликтов: {_cf_err}")
        st.code(_tb.format_exc())
elif page == ":material/toll: Монетка":
    import random as _random
    import sys as _sys, os as _os
    _SRC = _os.path.join(_os.path.dirname(__file__), "src")
    if _SRC not in _sys.path:
        _sys.path.insert(0, _SRC)
    from coin_flip import record_page_view, flip_coin, get_stats

    st.title(":material/toll: Монетка")
    st.caption(
        "Подбрасываем виртуальную монету. Почти всегда — орёл или решка, "
        "но примерно 1 раз из ~400 монета встаёт на ребро."
    )

    if not st.session_state.get("_coin_view_counted"):
        record_page_view()
        st.session_state["_coin_view_counted"] = True

    if "_coin_flip_n" not in st.session_state:
        st.session_state["_coin_flip_n"] = 0
        st.session_state["_coin_result"] = None

    col_coin, col_stats = st.columns([2, 1])

    with col_coin:
        if st.button(":material/casino: Подбросить монету", type="primary", use_container_width=True):
            result, _ = flip_coin()
            st.session_state["_coin_result"] = result
            st.session_state["_coin_flip_n"] += 1

        n = st.session_state["_coin_flip_n"]
        result = st.session_state["_coin_result"]

        # Финальный угол поворота (плюс несколько полных оборотов для эффекта вращения)
        spins = 3 * 360
        end_deg = {"heads": 0, "tails": 180, "edge": 90}.get(result, 0)
        total_deg = spins + end_deg if result else 0
        anim = "coin-spin-idle" if not result else f"coin-spin-{n}"

        st.markdown(
            f"""
            <style>
            .coin-scene {{
                perspective: 1200px;
                width: 190px; height: 190px;
                margin: 0.5rem auto 1.2rem;
            }}
            .coin {{
                width: 100%; height: 100%;
                position: relative;
                transform-style: preserve-3d;
                transform: rotateY({end_deg}deg);
                {"animation: " + anim + " 1.4s cubic-bezier(.25,.75,.35,1) forwards;" if result else ""}
            }}
            .coin-face {{
                position: absolute; inset: 0;
                border-radius: 50%;
                backface-visibility: hidden;
                display: flex; align-items: center; justify-content: center;
                font-weight: 800; font-size: 1.3rem; letter-spacing: .5px;
                background: radial-gradient(circle at 32% 28%, #fff6d0, #e6c14d 45%, #b8860b 85%, #8a6d1f 100%);
                border: 5px solid #96720f;
                box-shadow: 0 10px 28px rgba(0,0,0,.35), inset 0 0 22px rgba(255,255,255,.45);
                color: #5b4300;
            }}
            .coin-back {{ transform: rotateY(180deg); }}
            @keyframes {anim} {{
                0%   {{ transform: rotateY(0deg); }}
                100% {{ transform: rotateY({total_deg}deg); }}
            }}
            </style>
            <div class="coin-scene">
              <div class="coin">
                <div class="coin-face coin-front">ОРЁЛ</div>
                <div class="coin-face coin-back">РЕШКА</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if result == "edge":
            st.markdown(
                ":violet-badge[:material/bolt: РЕБРО! Это очень редкий исход]",
                text_alignment="center",
            )
        elif result == "heads":
            st.markdown("#### :material/check_circle: Орёл", text_alignment="center")
        elif result == "tails":
            st.markdown("#### :material/check_circle: Решка", text_alignment="center")
        else:
            st.markdown("<div style='text-align:center;color:#64748b;'>Нажмите кнопку, чтобы подбросить</div>", unsafe_allow_html=True)

    with col_stats:
        stats = get_stats()
        st.markdown("**:material/monitoring: Статистика раздела**")
        st.metric("Просмотров страницы", stats["page_views"])
        st.metric("Подбросов всего", stats["total_flips"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Орёл", stats["heads"])
        c2.metric("Решка", stats["tails"])
        c3.metric(":material/bolt: Ребро", stats["edge"])
        if stats["total_flips"] > 0:
            edge_rate = stats["edge"] / stats["total_flips"]
            st.caption(f"Фактическая доля рёбер: {edge_rate:.3%}")
        st.caption(
            "Счётчики хранятся локально в data/coin_stats.json. "
            "На Streamlit Community Cloud сбрасываются при редеплое контейнера — "
            "для устойчивой веб-аналитики понадобится внешний сервис "
            "(Plausible / Google Analytics)."
        )

elif page == ":material/volunteer_activism: Донат":
    try:
        from app_pages._donate import render_donate_page
        render_donate_page()
    except Exception as _don_err:
        import traceback as _tb
        st.error(f":material/cancel: Ошибка загрузки страницы доната: {_don_err}")
        st.code(_tb.format_exc())

