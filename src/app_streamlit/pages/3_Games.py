"""Страница: Игра guess-sign — ставка на направление цены."""
import os
import requests
import streamlit as st

API = os.environ.get("BASE_URL", "http://localhost:8000") + "/api/v1"
token = st.session_state.get("token", "")
headers = {"Authorization": f"Bearer {token}"}

st.title("🎮 Guess the Sign")
st.caption("Угадай направление цены и выиграй кредиты!")

tickers = requests.get(f"{API}/data/tickers", timeout=5).json().get("tickers", ["AAPL"])
ticker  = st.selectbox("Тикер", tickers)
horizon = st.radio("Горизонт", ["t+1", "t+20"], horizontal=True)
stake   = st.slider("Ставка (кредиты)", 10, 500, 50, step=10)
choice  = st.radio("Прогноз", ["up ↑", "down ↓"], horizontal=True)

if st.button("Сделать ставку", type="primary"):
    payload = {
        "ticker": ticker,
        "horizon": horizon,
        "stake": stake,
        "choice": "up" if "up" in choice else "down",
    }
    try:
        resp = requests.post(f"{API}/games/guess-sign",
                             json=payload, headers=headers, timeout=30).json()
        result = resp.get("result", {})
        if result.get("win"):
            st.balloons()
            st.success(f"✅ Победа! Выплата: {result['payout']} кредитов. "
                       f"Реальный знак: {result['real_sign']}")
        else:
            st.error(f"❌ Проигрыш. Реальный знак: {result.get('real_sign', '?')}")
        st.metric("Новый баланс", resp.get("balance", "—"))
    except Exception as e:
        st.error(f"Ошибка: {e}")

# История
with st.expander("История игр"):
    try:
        hist = requests.get(f"{API}/games/history", headers=headers, timeout=5).json()
        import pandas as pd
        st.dataframe(pd.DataFrame(hist.get("items", [])))
    except Exception:
        st.info("История недоступна")
