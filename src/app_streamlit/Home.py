"""Streamlit ЛК — Home (карточки активов, прогнозы, баланс)."""
import os
import requests
import streamlit as st

API = os.environ.get("BASE_URL", "http://localhost:8000") + "/api/v1"

st.set_page_config(page_title="Предсказания", page_icon="📈", layout="wide")
st.title("📈 Предсказания — Market Forecast")

# ── Auth ─────────────────────────────────────────────────────
token = st.session_state.get("token", "")
if not token:
    with st.form("login"):
        st.subheader("Войти")
        email = st.text_input("Email")
        pwd   = st.text_input("Password", type="password")
        if st.form_submit_button("Войти"):
            # TODO: Supabase Auth login
            st.warning("Введи токен вручную (Supabase Auth не настроен в demo)")
    token_input = st.text_input("Или вставь JWT-токен напрямую")
    if token_input:
        st.session_state["token"] = token_input
        st.rerun()
    st.stop()

headers = {"Authorization": f"Bearer {token}"}

# ── Balance ──────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
try:
    bal = requests.get(f"{API}/wallet/balance", headers=headers, timeout=5).json()
    col1.metric("💰 Баланс кредитов", bal.get("balance", "—"))
except Exception:
    col1.metric("💰 Баланс кредитов", "недоступно")

# ── Tickers ──────────────────────────────────────────────────
try:
    tickers = requests.get(f"{API}/data/tickers", timeout=5).json().get("tickers", [])
except Exception:
    tickers = ["AAPL", "MSFT", "BTC-USD", "ETH-USD"]

selected = col2.selectbox("Тикер", tickers)

# ── Forecast ─────────────────────────────────────────────────
st.subheader(f"Прогноз для {selected}")
if st.button("Получить прогноз"):
    from datetime import date
    payload = {"date": str(date.today()), "tickers": [selected]}
    try:
        resp = requests.post(f"{API}/forecast/predict", json=payload,
                             headers=headers, timeout=30)
        preds = resp.json().get("preds", [])
        if preds:
            p = preds[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("r¹ (завтра)", f"{p['r1']:+.4f}")
            c2.metric("R²⁰ (20д)", f"{p['R20']:+.4f}")
            c3.metric("p↑ (t+1)", f"{p['p1']:.2%}")
            c4.metric("p↑ (t+20)", f"{p['p20']:.2%}")
        else:
            st.warning("Нет данных")
    except Exception as e:
        st.error(f"Ошибка: {e}")

# ── Quick metrics ─────────────────────────────────────────────
with st.expander("Метрики модели"):
    try:
        m = requests.get(f"{API}/forecast/metrics", timeout=5).json()
        st.json(m)
    except Exception:
        st.info("Метрики недоступны")

st.sidebar.page_link("Home.py",               label="🏠 Главная")
st.sidebar.page_link("pages/1_Forecasts.py",  label="📊 Прогнозы")
st.sidebar.page_link("pages/2_News.py",       label="📰 Новости")
st.sidebar.page_link("pages/3_Games.py",      label="🎮 Игры")
st.sidebar.page_link("pages/4_Spin.py",       label="🎰 Спин")
st.sidebar.page_link("pages/5_Snake.py",      label="🐍 Змейка")
st.sidebar.page_link("pages/6_NFT.py",        label="🖼️ NFT")
st.sidebar.page_link("pages/7_Wallet.py",     label="💳 Кошелёк")
