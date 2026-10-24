"""
Страница «Игра» — встраивает «Политическую арену» (FastAPI-сервер в game/).

Streamlit Community Cloud отдаёт наружу только один порт, поэтому сервер игры
запускается отдельно (см. render.yaml) и подключается сюда по URL.

Где задаётся URL (по приоритету):
  1. Streamlit secrets:  GAME_URL = "https://political-arena.onrender.com"
  2. переменная окружения GAME_URL
  3. константа DEFAULT_GAME_URL ниже
"""
import os

import streamlit as st

DEFAULT_GAME_URL = ""  # впиши сюда адрес после деплоя, если не хочешь использовать secrets


def _game_url() -> str:
    try:
        url = st.secrets.get("GAME_URL", "")
    except Exception:
        url = ""
    url = (url or os.environ.get("GAME_URL", "") or DEFAULT_GAME_URL).strip().rstrip("/")
    # только абсолютные http(s)-адреса — защита от случайной/подставной подстановки
    return url if url.startswith(("https://", "http://")) else ""


def render_game_page() -> None:
    st.markdown("## :material/sports_esports: Политическая арена")
    url = _game_url()

    if not url:
        st.info(
            "Игра скоро появится здесь. Сервер игры ещё не подключён: "
            "после деплоя укажите его адрес в `GAME_URL` (Streamlit → Settings → Secrets).",
            icon=":material/construction:",
        )
        return

    st.link_button("Открыть на весь экран", url, icon=":material/open_in_new:")
    st.caption("Если сервер «спал», первая загрузка может занять около минуты.")
    if hasattr(st, "iframe"):          # новые версии Streamlit (components.v1.iframe устарел)
        st.iframe(url, height=760)
    else:
        import streamlit.components.v1 as components
        components.iframe(url, height=760, scrolling=True)
