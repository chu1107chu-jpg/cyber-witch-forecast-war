"""Страница: Spin — слот-машина с provably-fair RNG."""
import os
import time
import uuid
import requests
import streamlit as st

API = os.environ.get("BASE_URL", "http://localhost:8000") + "/api/v1"
token   = st.session_state.get("token", "")
headers = {"Authorization": f"Bearer {token}"}

BUCKET_ICONS = {
    "null":     ("⬛", "Нет выплаты"),
    "x025":     ("🟦", "×0.25"),
    "x050":     ("🟩", "×0.50"),
    "x100":     ("⬜", "×1.00"),
    "x200":     ("🟨", "×2.00"),
    "x500":     ("🟧", "×5.00"),
    "x1000":    ("🟥", "×10.00"),
    "near_miss":("🔶", "Почти!"),
}

st.title("🎰 Utility Spin")
st.caption("Провably-fair слот на внутренние кредиты. RTP ≈ 43.5%.")

# Получить список конфигов
try:
    games_cfg = requests.get(f"{API}/spin/games", timeout=5).json().get("games", [])
    game_id = st.selectbox("Игра", [g["id"] for g in games_cfg]) if games_cfg else "utility_slot_v1"
except Exception:
    game_id = "utility_slot_v1"

stake    = st.slider("Ставка (кредиты)", 10, 1000, 100, step=10)
c_nonce  = st.text_input("Client nonce (необязательно)", value=str(uuid.uuid4()))
idm_key  = str(uuid.uuid4())

col1, col2 = st.columns([2, 1])
with col1:
    spin_btn = st.button("🎯 SPIN", type="primary", use_container_width=True)
with col2:
    st.metric("Ставка", f"{stake} cr")

if spin_btn:
    payload = {"game_id": game_id, "stake": stake, "client_nonce": c_nonce}
    hdrs    = {**headers, "Idempotency-Key": idm_key}
    try:
        with st.spinner("Крутим..."):
            time.sleep(0.4)
            resp = requests.post(f"{API}/spin/play", json=payload,
                                 headers=hdrs, timeout=15).json()
        bucket  = resp.get("bucket", "null")
        payout  = resp.get("payout", 0)
        icon, label = BUCKET_ICONS.get(bucket, ("❓", bucket))

        st.markdown(f"<h1 style='text-align:center;font-size:5rem'>{icon}</h1>",
                    unsafe_allow_html=True)
        st.markdown(f"<h3 style='text-align:center'>{label}</h3>",
                    unsafe_allow_html=True)
        if payout > stake:
            st.balloons()
        st.metric("Выплата", f"{payout} cr", delta=payout - stake)
        st.metric("Новый баланс", resp.get("balance", "—"))

        with st.expander("Доказательство честности (provably fair)"):
            st.json({
                "server_seed_hash": resp.get("server_seed_hash"),
                "client_nonce":     c_nonce,
                "k":                resp.get("k"),
                "u":                resp.get("u"),
                "near_miss":        resp.get("near_miss"),
            })
    except Exception as e:
        st.error(f"Ошибка запроса: {e}")

# История
with st.expander("История спинов (последние 20)"):
    try:
        hist = requests.get(f"{API}/spin/history",
                            headers=headers, timeout=5).json()
        import pandas as pd
        df = pd.DataFrame(hist.get("items", []))
        if not df.empty:
            st.dataframe(df[["created_at","game_id","stake","bucket","payout"]],
                         use_container_width=True)
    except Exception:
        st.info("История недоступна")
