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
TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "BRK-B", "XOM", "JPM",
    "BTC-USD", "ETH-USD", "GC=F", "^GSPC", "^IXIC",
]
TICKER_LABELS = {
    "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Google", "AMZN": "Amazon",
    "NVDA": "NVIDIA", "META": "Meta", "TSLA": "Tesla", "BRK-B": "Berkshire",
    "XOM": "ExxonMobil", "JPM": "JPMorgan", "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum", "GC=F": "Gold", "^GSPC": "S&P 500", "^IXIC": "NASDAQ",
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
[data-testid="stMetricValue"] { font-size: 1.5rem; font-weight: 700; }
[data-testid="stMetricLabel"] { font-size: 0.78rem; opacity: .7; }
.metric-up   { color: #26c281; }
.metric-down { color: #e74c3c; }
.section-header {
    font-size: 1.1rem; font-weight: 600;
    border-left: 3px solid #6c63ff;
    padding-left: .6rem; margin: 1.2rem 0 .6rem;
}
div[data-testid="stSidebar"] { background: #0e1117; }
</style>
""", unsafe_allow_html=True)


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
        ["📊 Дашборд", "🔍 Тикер", "🧠 О модели"],
        label_visibility="collapsed",
    )
    st.divider()

    if page == "🔍 Тикер":
        sel_ticker = st.selectbox(
            "Тикер",
            TICKERS,
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

    # Запускаем прогнозы для всех тикеров
    with st.spinner("Считаю прогнозы для всех тикеров…"):
        rows = []
        prog = st.progress(0, text="Загружаю данные…")
        for i, ticker in enumerate(TICKERS):
            prog.progress((i + 1) / len(TICKERS), text=f"↓ {ticker}")
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

    if not rows:
        st.warning("Не удалось получить прогнозы. Проверьте интернет.")
        st.stop()

    df_table = pd.DataFrame(rows)

    # ── Сводные метрики ──
    up1  = (df_table["p↑(t+1)"] > 0.5).sum()
    up20 = (df_table["p↑(t+20)"] > 0.5).sum()
    best = df_table.loc[df_table["p↑(t+1)"].idxmax(), "Тикер"]
    best_p = df_table["p↑(t+1)"].max()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📈 Растут завтра",  f"{up1} / {len(rows)}")
    c2.metric("📈 Растут за 20д", f"{up20} / {len(rows)}")
    c3.metric("🏆 Лучший сигнал",  f"{best}", f"{best_p:.1%} вверх")
    c4.metric("📅 Дата прогноза",  datetime.now().strftime("%d.%m.%Y"))

    st.divider()

    # ── Визуализация ──
    col_l, col_r = st.columns([3, 2])

    with col_l:
        st.markdown('<div class="section-header">Прогноз направления (t+1)</div>',
                    unsafe_allow_html=True)

        # Горизонтальный бар-чарт вероятностей
        df_sorted = df_table.sort_values("p↑(t+1)", ascending=True)
        colors = ["#26c281" if p > 0.5 else "#e74c3c"
                  for p in df_sorted["p↑(t+1)"]]
        fig_bar = go.Figure(go.Bar(
            x=df_sorted["p↑(t+1)"],
            y=df_sorted["Тикер"],
            orientation="h",
            marker_color=colors,
            text=[f"{p:.1%}" for p in df_sorted["p↑(t+1)"]],
            textposition="outside",
        ))
        fig_bar.add_vline(x=0.5, line_dash="dot", line_color="white", opacity=0.4)
        fig_bar.update_layout(
            height=420,
            margin=dict(l=10, r=50, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            xaxis=dict(tickformat=".0%", range=[0, 1], showgrid=True,
                       gridcolor="rgba(255,255,255,0.07)"),
            yaxis=dict(showgrid=False),
            showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_r:
        st.markdown('<div class="section-header">Ожидаемый доход (20 дней)</div>',
                    unsafe_allow_html=True)
        df_r20 = df_table.sort_values("R²⁰ (20д)", ascending=True)
        colors20 = ["#26c281" if r > 0 else "#e74c3c" for r in df_r20["R²⁰ (20д)"]]
        fig_r20 = go.Figure(go.Bar(
            x=df_r20["R²⁰ (20д)"],
            y=df_r20["Тикер"],
            orientation="h",
            marker_color=colors20,
            text=[f"{r:+.2%}" for r in df_r20["R²⁰ (20д)"]],
            textposition="outside",
        ))
        fig_r20.add_vline(x=0, line_dash="dot", line_color="white", opacity=0.4)
        fig_r20.update_layout(
            height=420,
            margin=dict(l=10, r=60, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="white"),
            xaxis=dict(tickformat="+.1%", showgrid=True,
                       gridcolor="rgba(255,255,255,0.07)"),
            yaxis=dict(showgrid=False),
            showlegend=False,
        )
        st.plotly_chart(fig_r20, use_container_width=True)

    # ── Таблица ──
    st.markdown('<div class="section-header">Все прогнозы</div>',
                unsafe_allow_html=True)

    display = df_table.copy()
    display["r¹ (завтра)"] = display["r¹ (завтра)"].map("{:+.4f}".format)
    display["R²⁰ (20д)"]  = display["R²⁰ (20д)"].map("{:+.4f}".format)
    display["p↑(t+1)"]    = display["p↑(t+1)"].map("{:.1%}".format)
    display["p↑(t+20)"]   = display["p↑(t+20)"].map("{:.1%}".format)
    st.dataframe(display, use_container_width=True, hide_index=True)


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
              f"{delta_pct:+.2%} vs пред. день")
    if pred:
        c2.metric("r¹ (завтра)", f"{pred['target_r1']:+.4f}",
                  "↑" if pred["target_r1"] > 0 else "↓")
        c3.metric("p↑ (t+1)", f"{pred['target_p1_up']:.1%}",
                  "бычий сигнал" if pred["target_p1_up"] > 0.5 else "медвежий")
        c4.metric("p↑ (t+20)", f"{pred['target_p20_up']:.1%}")
    else:
        c2.metric("Прогноз", "н/д")

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
    fig.update_layout(
        height=380, margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
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
            fig_vol.update_layout(
                height=220, margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"), showlegend=False,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
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
            fig_rsi.update_layout(
                height=220, margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="white"), showlegend=False,
                yaxis=dict(range=[0, 100], showgrid=True,
                           gridcolor="rgba(255,255,255,0.05)"),
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
                paper_bgcolor="rgba(0,0,0,0)", font=dict(color="white"),
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
#  СТРАНИЦА: О МОДЕЛИ
# ═══════════════════════════════════════════════
elif page == "🧠 О модели":
    st.title("🧠 О модели")

    if not models_loaded:
        st.stop()

    st.markdown('<div class="section-header">Метрики обучения</div>',
                unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    metrics = train_summary.get("metrics", {})

    c1.metric("target_r1 MAE",
              f"{metrics.get('target_r1', {}).get('mae', 0):.5f}")
    c2.metric("target_R20 MAE",
              f"{metrics.get('target_R20', {}).get('mae', 0):.5f}")
    c3.metric("target_p1_up ROC-AUC",
              f"{metrics.get('target_p1_up', {}).get('roc_auc', 0):.4f}")
    c4.metric("target_p20_up ROC-AUC",
              f"{metrics.get('target_p20_up', {}).get('roc_auc', 0):.4f}")

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown('<div class="section-header">Параметры обучения</div>',
                    unsafe_allow_html=True)
        info = {
            "Тикеров": train_summary.get("n_tickers", 15),
            "Сэмплов": f"{train_summary.get('n_samples', 0):,}",
            "Признаков": train_summary.get("n_features", 17),
            "Период": "7 лет (yfinance)",
            "Кросс-валидация": "TimeSeriesSplit(5 folds)",
            "Дата обучения": train_summary.get("trained_at", "—")[:10],
        }
        for k, v in info.items():
            st.markdown(f"**{k}:** {v}")

    with col_b:
        st.markdown('<div class="section-header">Архитектура</div>',
                    unsafe_allow_html=True)
        st.markdown("""
**Регрессия** (`target_r1`, `target_R20`):
```
StackingRegressor(
  estimators=[
    Ridge(α=1.0),
    ElasticNet(),
    RandomForestRegressor(n=200),
    ExtraTreesRegressor(n=200),
  ],
  final_estimator=Ridge()
)
```

**Классификация** (`target_p1_up`, `target_p20_up`):
```
Pipeline(
  StandardScaler(),
  LogisticRegression(C=0.1)
)
```
""")

    st.divider()
    st.markdown('<div class="section-header">Признаки (17)</div>',
                unsafe_allow_html=True)
    feat_desc = {
        "ret1/3/5/10/20": "Скользящие доходности за N дней",
        "log_ret1": "Логарифмическая доходность (1 день)",
        "rsi14": "RSI-14",
        "macd_h": "MACD гистограмма",
        "atr14": "ATR-14 / цена",
        "vol10 / vol20": "Историческая волатильность (10d, 20d)",
        "vol_ratio": "vol10 / vol20",
        "dist_hi52 / dist_lo52": "Расстояние до 52-нед. хай/лоу",
        "ma50_ratio / ma200_ratio": "Цена / MA50, цена / MA200",
        "vol_rel": "Объём / MA(объём, 20)",
    }
    for feat, desc in feat_desc.items():
        st.markdown(f"- **`{feat}`** — {desc}")

    st.divider()
    with st.expander("Полный train_summary.json"):
        st.json(train_summary)
