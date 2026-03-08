"""Страница: Новости — фильтры, карточки с sentiment."""
import os
import requests
import pandas as pd
import streamlit as st
from datetime import date, timedelta

API = os.environ.get("BASE_URL", "http://localhost:8000") + "/api/v1"
st.title("📰 Новости")

tickers = requests.get(f"{API}/data/tickers", timeout=5).json().get("tickers", ["AAPL"])
ticker = st.selectbox("Тикер", tickers)
col1, col2 = st.columns(2)
from_date = col1.date_input("С", date.today() - timedelta(days=30))
to_date   = col2.date_input("По", date.today())

params = {"ticker": ticker, "from": str(from_date), "to": str(to_date), "limit": 100}
try:
    resp = requests.get(f"{API}/data/news", params=params, timeout=15).json()
    items = resp.get("items", [])
    if items:
        df = pd.DataFrame(items)
        st.metric("Найдено новостей", len(df))
        # colorize sentiment
        def color_sent(val):
            if isinstance(val, float):
                if val > 0.2: return "background-color: #1a4a1a; color: #7fff7f"
                if val < -0.2: return "background-color: #4a1a1a; color: #ff7f7f"
            return ""
        show_cols = [c for c in ["published_at", "title", "source", "sentiment_score", "url"] if c in df.columns]
        st.dataframe(
            df[show_cols].style.applymap(color_sent, subset=["sentiment_score"] if "sentiment_score" in df.columns else []),
            height=500,
        )
    else:
        st.info("Новости не найдены")
except Exception as e:
    st.error(f"Ошибка: {e}")
