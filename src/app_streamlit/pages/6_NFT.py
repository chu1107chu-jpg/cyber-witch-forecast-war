"""Страница: NFT — галерея, минт, загрузка (admin)."""
import os
import io
import requests
import streamlit as st

API   = os.environ.get("BASE_URL", "http://localhost:8000") + "/api/v1"
token = st.session_state.get("token", "")
headers = {"Authorization": f"Bearer {token}"}
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")

st.title("🖼️ NFT Gallery")
st.caption("Внутренние NFT-сертификаты. Минт стоит кредиты; хранение в Cloudflare R2.")

# --- Галерея ---
try:
    items = requests.get(f"{API}/nft/list", headers=headers, timeout=8).json().get("items", [])
except Exception:
    items = []

if items:
    cols = st.columns(3)
    for i, nft in enumerate(items):
        with cols[i % 3]:
            url = nft.get("image_url", "")
            if url:
                st.image(url, use_container_width=True)
            st.caption(f"**{nft['name']}**")
            st.caption(f"Owner: {nft.get('owner_id','')[:8]}…")
else:
    st.info("NFT пока нет. Стань первым!")

st.divider()

# --- Минт ---
st.subheader("Минт нового NFT")
nft_name = st.text_input("Название", placeholder="Мой прогноз #1")
nft_desc = st.text_area("Описание", placeholder="Был ли бычий рынок?..")
nft_cost = 200  # кредитов

if st.button(f"Минтнуть (−{nft_cost} cr)", type="primary"):
    if not nft_name.strip():
        st.warning("Введи название")
    else:
        payload = {"name": nft_name, "description": nft_desc}
        try:
            resp = requests.post(f"{API}/nft/mint-internal",
                                 json=payload, headers=headers, timeout=15).json()
            if resp.get("id"):
                st.success(f"NFT создан! ID: {resp['id']}")
                st.metric("Новый баланс", resp.get("balance", "—"))
                st.rerun()
            else:
                st.error(resp.get("detail", "Ошибка минта"))
        except Exception as e:
            st.error(str(e))

st.divider()

# --- Admin: загрузка изображения ---
with st.expander("🔐 Admin: загрузить изображение"):
    adm_secret = st.text_input("Admin secret", type="password")
    uploaded   = st.file_uploader("Изображение (jpeg/png/gif, макс 5 МБ)",
                                  type=["jpg","jpeg","png","gif","webp"])
    if st.button("Загрузить и проверить через YOLO"):
        if not adm_secret:
            st.warning("Введи admin secret")
        elif not uploaded:
            st.warning("Выбери файл")
        else:
            data = uploaded.read()
            try:
                resp = requests.post(
                    f"{API}/nft/upload",
                    files={"file": (uploaded.name, io.BytesIO(data), uploaded.type)},
                    data={"admin_secret": adm_secret},
                    timeout=30,
                ).json()
                if resp.get("url"):
                    st.success(f"Загружено: {resp['url']}")
                    st.image(data, width=200)
                else:
                    st.error(resp.get("detail", "Ошибка загрузки"))
            except Exception as e:
                st.error(str(e))
