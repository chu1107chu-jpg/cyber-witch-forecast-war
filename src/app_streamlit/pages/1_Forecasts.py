"""Страница: Прогнозы — чарты + таблица метрик."""
import os
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datetime import date, timedelta

API = os.environ.get("BASE_URL", "http://localhost:8000") + "/api/v1"
token = st.session_state.get("token", "")
headers = {"Authorization": f"Bearer {token}"}

st.title("📊 Прогнозы")

tickers = requests.get(f"{API}/data/tickers", timeout=5).json().get("tickers", ["AAPL"])
ticker = st.selectbox("Тикер", tickers)
horizon = st.radio("Горизонт", ["t+1", "t+20"], horizontal=True)

# ── Котировки ────────────────────────────────────────────────
try:
    qd = requests.get(f"{API}/data/quotes", params={"ticker": ticker, "window": 120},
                      timeout=10).json()
    df_q = pd.DataFrame(qd.get("data", []))
    if not df_q.empty:
        fig = go.Figure(go.Scatter(x=df_q["date"], y=df_q["close"], mode="lines",
                                   name="Close", line=dict(color="#4f8ef7")))
        fig.update_layout(height=300, margin=dict(t=20, b=20), xaxis_title="Дата",
                          yaxis_title="Цена", template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.error(f"Котировки: {e}")

# ── Прогноз ──────────────────────────────────────────────────
if st.button("Прогноз сейчас"):
    payload = {"date": str(date.today()), "tickers": [ticker]}
    resp = requests.post(f"{API}/forecast/predict", json=payload,
                         headers=headers, timeout=30)
    preds = resp.json().get("preds", [])
    if preds:
        p = preds[0]
        st.dataframe(pd.DataFrame([p]))

# ── Big News Analysis ─────────────────────────────────────────
with st.expander("📌 Аналитика крупных новостей (5 лет)"):
    try:
        bna = requests.get(f"{API}/data/big-news-analysis", params={"ticker": ticker},
                           timeout=30).json()
        col1, col2, col3 = st.columns(3)
        col1.metric("Крупных событий", bna.get("big_event_count", "—"))
        col2.metric("↑ роста", bna.get("up_count", "—"))
        col3.metric("↓ паденей", bna.get("down_count", "—"))
        events = bna.get("events_with_news", [])
        if events:
            st.dataframe(pd.DataFrame(events).drop(columns=["top_news"], errors="ignore"))
    except Exception as e:
        st.info(f"Недоступно: {e}")

# ── Метрики ──────────────────────────────────────────────────
with st.expander("Метрики модели"):
    split = st.selectbox("Сплит", ["val", "test"])
    try:
        m = requests.get(f"{API}/forecast/metrics", params={"split": split}, timeout=5).json()
        st.json(m)
    except Exception:
        st.info("—")
