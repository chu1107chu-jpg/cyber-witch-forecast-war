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
    page_icon="🔮",
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
#  Загрузка моделей (кэш)
# ─────────────────────────────────────────────
@st.cache_resource(show_spinner="Загружаю модели…")
def load_models():
    models = joblib.load(ARTIFACTS / "models.pkl")
    features = joblib.load(ARTIFACTS / "feature_cols.pkl")
    with open(ARTIFACTS / "train_summary.json") as f:
        summary = json.load(f)
    return models, features, summary


@st.cache_data(ttl=300, show_spinner="Загружаю котировки…")
def fetch_data(ticker: str, period: str = "1y") -> pd.DataFrame:
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df = df.dropna()
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for n in [1, 3, 5, 10, 20]:
        d[f"ret{n}"] = d["Close"].pct_change(n)
    d["log_ret1"] = np.log(d["Close"] / d["Close"].shift(1))

    # RSI-14
    delta = d["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    d["rsi14"] = 100 - 100 / (1 + rs)

    # MACD histogram
    ema12 = d["Close"].ewm(span=12).mean()
    ema26 = d["Close"].ewm(span=26).mean()
    d["macd_h"] = ema12 - ema26 - (ema12 - ema26).ewm(span=9).mean()

    # ATR-14
    hl = d["High"] - d["Low"]
    hc = (d["High"] - d["Close"].shift()).abs()
    lc = (d["Low"] - d["Close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()
    d["atr14"] = atr14 / d["Close"]

    # Volatility
    d["vol10"] = d["log_ret1"].rolling(10).std()
    d["vol20"] = d["log_ret1"].rolling(20).std()
    d["vol_ratio"] = d["vol10"] / d["vol20"].replace(0, np.nan)

    # 52-week hi/lo distance
    hi52 = d["Close"].rolling(252).max()
    lo52 = d["Close"].rolling(252).min()
    d["dist_hi52"] = (d["Close"] - hi52) / hi52
    d["dist_lo52"] = (d["Close"] - lo52) / lo52.replace(0, np.nan)

    # Moving averages ratio
    d["ma50_ratio"]  = d["Close"] / d["Close"].rolling(50).mean()
    d["ma200_ratio"] = d["Close"] / d["Close"].rolling(200).mean()

    # Volume relative
    if "Volume" in d.columns and d["Volume"].sum() > 0:
        d["vol_rel"] = d["Volume"] / d["Volume"].rolling(20).mean().replace(0, np.nan)
    else:
        d["vol_rel"] = 1.0

    return d.dropna()


def predict_ticker(ticker: str, models, feature_cols):
    df_raw = fetch_data(ticker, "2y")
    if df_raw.empty or len(df_raw) < 250:
        return None, df_raw
    df = build_features(df_raw)
    if df.empty:
        return None, df_raw

    # Берём последнюю дату
    cols_present = [c for c in feature_cols if c in df.columns]
    if len(cols_present) < len(feature_cols):
        return None, df_raw

    X_last = df[feature_cols].iloc[[-1]]
    result = {}
    for target, pipe in models.items():
        if "up" in target:
            # Классификация → вероятность класса 1
            try:
                val = pipe.predict_proba(X_last)[0][1]
            except AttributeError:
                val = float(pipe.predict(X_last)[0])
        else:
            val = float(pipe.predict(X_last)[0])
        result[target] = float(val)

    return result, df_raw


# ─────────────────────────────────────────────
#  Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔮 Предсказания")
    st.caption("Рыночные прогнозы на базе ML")
    st.divider()

    page = st.radio(
        "Раздел",
        ["📊 Дашборд", "🔍 Тикер", "⚔️ Конфликты"],
        label_visibility="collapsed",
    )
    st.divider()

    if page == "🔍 Тикер":
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
if page == "📊 Дашборд":
    st.title("📊 Рыночный дашборд")
    st.caption("Прогнозы на основе обученных моделей. Обновляется каждые 5 минут.")

    if not models_loaded:
        st.stop()

    # Табы по рынкам
    tab_us, tab_ru = st.tabs(["🇺🇸 США / Крипто / Индексы", "🇷🇺 Россия (MOEX)"])

    def run_forecasts(ticker_list, label):
        rows = []
        prog = st.progress(0, text=f"Загружаю {label}…")
        for i, ticker in enumerate(ticker_list):
            prog.progress((i + 1) / len(ticker_list), text=f"↓ {ticker}")
            try:
                pred, _ = predict_ticker(ticker, models, feature_cols)
                if pred:
                    rows.append({
                        "Тикер": ticker,
                        "Название": TICKER_LABELS.get(ticker, ticker),
                        "r¹ (завтра)": pred.get("target_r1", 0),
                        "R²⁰ (20д)": pred.get("target_R20", 0),
                        "p↑(t+1)": pred.get("target_p1_up", 0.5),
                        "p↑(t+20)": pred.get("target_p20_up", 0.5),
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
        up1  = (df_table["p↑(t+1)"] > 0.5).sum()
        up20 = (df_table["p↑(t+20)"] > 0.5).sum()
        best = df_table.loc[df_table["p↑(t+1)"].idxmax(), "Тикер"]
        best_p = df_table["p↑(t+1)"].max()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📈 Растут завтра",  f"{up1} / {len(rows)}",
              help=explain_signal_count(up1, len(rows), "1 день"))
        c2.metric("📈 Растут за 20д", f"{up20} / {len(rows)}",
              help=explain_signal_count(up20, len(rows), "20 дней"))
        c3.metric("🏆 Лучший сигнал",  f"{best}", f"{best_p:.1%} вверх",
              help=f"Это актив с самым сильным шансом роста на завтра. По оценке модели у {best} вероятность роста около {best_p:.0%}.")
        c4.metric("📅 Дата прогноза",  datetime.now().strftime("%d.%m.%Y"),
              help="Дата, когда сервис в последний раз пересчитал этот экран.")
        st.divider()

        col_l, col_r = st.columns([3, 2])
        with col_l:
            st.markdown('<div class="section-header">Прогноз направления (t+1)</div>', unsafe_allow_html=True)
            df_sorted = df_table.sort_values("p↑(t+1)", ascending=True)
            colors = ["#26c281" if p > 0.5 else "#e74c3c" for p in df_sorted["p↑(t+1)"]]
            fig_bar = go.Figure(go.Bar(
                x=df_sorted["p↑(t+1)"], y=df_sorted["Тикер"],
                orientation="h", marker_color=colors,
                text=[f"{p:.1%}" for p in df_sorted["p↑(t+1)"]], textposition="outside",
            ))
            fig_bar.add_vline(x=0.5, line_dash="dot", line_color="white", opacity=0.4)
            apply_glass_chart_theme(
                fig_bar,
                height=max(300, len(rows) * 28),
                margin=dict(l=10, r=50, t=10, b=10),
                xaxis=dict(tickformat=".0%", range=[0, 1]),
                yaxis=dict(showgrid=False), showlegend=False,
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_r:
            st.markdown('<div class="section-header">Ожидаемый доход (20 дней)</div>', unsafe_allow_html=True)
            df_r20 = df_table.sort_values("R²⁰ (20д)", ascending=True)
            colors20 = ["#26c281" if r > 0 else "#e74c3c" for r in df_r20["R²⁰ (20д)"]]
            fig_r20 = go.Figure(go.Bar(
                x=df_r20["R²⁰ (20д)"], y=df_r20["Тикер"],
                orientation="h", marker_color=colors20,
                text=[f"{r:+.2%}" for r in df_r20["R²⁰ (20д)"]], textposition="outside",
            ))
            fig_r20.add_vline(x=0, line_dash="dot", line_color="white", opacity=0.4)
            apply_glass_chart_theme(
                fig_r20,
                height=max(300, len(rows) * 28),
                margin=dict(l=10, r=60, t=10, b=10),
                xaxis=dict(tickformat="+.1%"),
                yaxis=dict(showgrid=False), showlegend=False,
            )
            st.plotly_chart(fig_r20, use_container_width=True)

        st.markdown('<div class="section-header">Все прогнозы</div>', unsafe_allow_html=True)
        display = df_table.copy()
        display["r¹ (завтра)"] = display["r¹ (завтра)"].map("{:+.4f}".format)
        display["R²⁰ (20д)"]  = display["R²⁰ (20д)"].map("{:+.4f}".format)
        display["p↑(t+1)"]    = display["p↑(t+1)"].map("{:.1%}".format)
        display["p↑(t+20)"]   = display["p↑(t+20)"].map("{:.1%}".format)
        st.dataframe(display, use_container_width=True, hide_index=True)

    with tab_us:
        render_market_tab(TICKERS_US, "США / Крипто")
    with tab_ru:
        render_market_tab(TICKERS_RU, "Россия MOEX")



# ═══════════════════════════════════════════════
#  СТРАНИЦА: ТИКЕР
# ═══════════════════════════════════════════════
elif page == "🔍 Тикер":
    ticker = sel_ticker
    label  = TICKER_LABELS.get(ticker, ticker)
    st.title(f"🔍 {ticker} — {label}")

    if not models_loaded:
        st.stop()

    with st.spinner(f"Загружаю {ticker}…"):
        pred, df_raw = predict_ticker(ticker, models, feature_cols)

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
    if pred:
        c2.metric("r¹ (завтра)", f"{pred['target_r1']:+.4f}",
                  "↑" if pred["target_r1"] > 0 else "↓",
                  help=explain_return(pred["target_r1"], "1 день"))
        c3.metric("p↑ (t+1)", f"{pred['target_p1_up']:.1%}",
                  "бычий сигнал" if pred["target_p1_up"] > 0.5 else "медвежий",
                  help=explain_probability(pred["target_p1_up"], "1 день"))
        c4.metric("p↑ (t+20)", f"{pred['target_p20_up']:.1%}",
                  help=explain_probability(pred["target_p20_up"], "20 дней"))
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
        df_feat = build_features(df_raw)
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
            # Gauge для p1_up
            p1 = pred["target_p1_up"]
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=p1 * 100,
                title={"text": "Вероятность роста завтра", "font": {"color": "white"}},
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
            proj_1d  = last_close * (1 + pred["target_r1"])
            proj_20d = last_close * (1 + pred["target_R20"])
            st.markdown(f"""
| Метрика | Значение | Проекция цены |
|---------|----------|--------------|
| **r¹ (1 день)** | `{pred['target_r1']:+.4f}` | `${proj_1d:,.2f}` |
| **R²⁰ (20 дней)** | `{pred['target_R20']:+.4f}` | `${proj_20d:,.2f}` |
| **p↑ (t+1)** | `{pred['target_p1_up']:.1%}` | {"🟢 Рост" if pred['target_p1_up'] > 0.5 else "🔴 Падение"} |
| **p↑ (t+20)** | `{pred['target_p20_up']:.1%}` | {"🟢 Рост" if pred['target_p20_up'] > 0.5 else "🔴 Падение"} |
""")
            signal_color = "#26c281" if pred["target_p1_up"] > 0.5 else "#e74c3c"
            signal_text  = "ПОКУПКА" if pred["target_p1_up"] > 0.6 else \
                           "ПРОДАЖА" if pred["target_p1_up"] < 0.4 else "НЕЙТРАЛЬНО"
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
elif page == "⚔️ Конфликты":
    try:
        import importlib, sys
        mod_key = "pages._conflict_forecast"
        if mod_key in sys.modules:
            importlib.reload(sys.modules[mod_key])
        from pages._conflict_forecast import render_conflict_page
        render_conflict_page()
    except Exception as _cf_err:
        import traceback as _tb
        st.error(f"❌ Ошибка загрузки раздела конфликтов: {_cf_err}")
        st.code(_tb.format_exc())


