import base64
import json
import os
import re
from pathlib import Path

import streamlit as st

ARENA_DIR = Path(__file__).resolve().parent.parent / "static" / "arena"
# Относительный путь (без «/» в начале): на Streamlit Cloud приложение живёт под префиксом /~/+/,
# и абсолютный «/app/static/…» туда не попадает.
STATIC_URL = "app/static/arena/"
FRAME_HEIGHT = 860


def _external_url() -> str:
    try:
        url = st.secrets.get("GAME_URL", "")
    except Exception:
        url = ""
    url = (url or os.environ.get("GAME_URL", "")).strip()
    return url if url.startswith(("https://", "http://")) else ""


@st.cache_data(show_spinner=False)
def _bundle_html() -> str:
    html = (ARENA_DIR / "index.html").read_text(encoding="utf-8")

    def inline_css(m: re.Match) -> str:
        return "<style>\n" + (ARENA_DIR / m.group(1)).read_text(encoding="utf-8") + "\n</style>"

    def inline_js(m: re.Match) -> str:
        code = (ARENA_DIR / m.group(1)).read_text(encoding="utf-8").replace("</script>", "<\\/script>")
        return "<script>\n" + code + "\n</script>"

    html = re.sub(r'<link rel="stylesheet" href="((?!https?:)[^"]+\.css)">', inline_css, html)
    html = re.sub(r'<script src="([^"]+\.js)"></script>', inline_js, html)
    # картинки бойцов встраиваем в страницу (data:) — так они видны, даже если статическая раздача
    # недоступна; ARENA_BASE — запасной вариант (srcdoc резолвит относительные адреса от страницы-родителя)
    imgs = {}
    for f in sorted((ARENA_DIR / "img").iterdir()):
        mime = {".jpg": "image/jpeg", ".svg": "image/svg+xml"}.get(f.suffix)
        if mime:
            imgs[f.stem] = f"data:{mime};base64," + base64.b64encode(f.read_bytes()).decode()
    inject = (f"<script>window.ARENA_BASE = {json.dumps(STATIC_URL)};"
              f"window.ARENA_IMG = {json.dumps(imgs)};</script>")
    return html.replace("<head>", "<head>\n" + inject, 1)


def render_game_page() -> None:
    st.markdown("## :material/sports_esports: Политическая арена")
    ext = _external_url()

    if ext:
        st.link_button("Открыть на весь экран", ext, icon=":material/open_in_new:")
        _frame(ext)
        return

    st.markdown(
        f'<a href="{STATIC_URL}index.html" target="_blank" style="font-size:13px;">'
        "Открыть на весь экран ↗</a>",
        unsafe_allow_html=True,
    )
    _frame(_bundle_html())


def _frame(src: str) -> None:
    if hasattr(st, "iframe"):
        st.iframe(src, height=FRAME_HEIGHT)
    else:
        import streamlit.components.v1 as components
        if src.startswith(("http://", "https://")):
            components.iframe(src, height=FRAME_HEIGHT, scrolling=True)
        else:
            components.html(src, height=FRAME_HEIGHT, scrolling=True)
