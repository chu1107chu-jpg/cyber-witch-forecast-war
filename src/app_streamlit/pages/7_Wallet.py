"""Страница: Кошелёк — баланс, история транзакций, пополнение (admin)."""
import os
import requests
import pandas as pd
import streamlit as st

API   = os.environ.get("BASE_URL", "http://localhost:8000") + "/api/v1"
token = st.session_state.get("token", "")
headers = {"Authorization": f"Bearer {token}"}

st.title("💳 Кошелёк")
st.caption("Внутренние утility-кредиты. Монетизация через TON/Solana — в дорожной карте.")

# --- Баланс ---
try:
    bal_data = requests.get(f"{API}/wallet/balance", headers=headers, timeout=5).json()
    balance  = bal_data.get("balance", 0)
except Exception:
    balance  = "—"

col1, col2, col3 = st.columns(3)
col1.metric("Баланс", f"{balance} cr")
col2.metric("Валюта", "Internal Credits")
col3.metric("Сеть", "Internal (TON ready)")

st.divider()

# --- История транзакций ---
st.subheader("История транзакций")
try:
    tx_resp = requests.get(f"{API}/wallet/transactions",
                           headers=headers, timeout=5).json()
    txs = tx_resp.get("items", [])
    if txs:
        df = pd.DataFrame(txs)
        df["amount"] = df.apply(
            lambda r: f"+{r['amount']}" if r.get("type") == "credit" else f"-{r['amount']}",
            axis=1
        )
        st.dataframe(
            df[["created_at","type","amount","description","idempotency_key"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Транзакций пока нет")
except Exception as e:
    st.info(f"Ошибка загрузки истории: {e}")

st.divider()

# --- Admin: пополнение ---
with st.expander("🔐 Admin: начислить кредиты"):
    admin_secret = st.text_input("Admin secret", type="password", key="wallet_adm")
    user_id      = st.text_input("User ID (UUID)")
    amount_cr    = st.number_input("Сумма (кредиты)", min_value=1, value=500, step=50)
    reason       = st.text_input("Причина", value="manual_topup")

    if st.button("Начислить", type="primary"):
        if not admin_secret or not user_id:
            st.warning("Заполни все поля")
        else:
            payload = {
                "user_id": user_id,
                "amount":  int(amount_cr),
                "description": reason,
                "admin_secret": admin_secret,
            }
            try:
                resp = requests.post(f"{API}/wallet/charge",
                                     json=payload, headers=headers, timeout=10).json()
                if resp.get("ok"):
                    st.success(f"Начислено! Новый баланс: {resp.get('balance')} cr")
                else:
                    st.error(resp.get("detail", "Ошибка"))
            except Exception as e:
                st.error(str(e))
