"""
Страница доната — USDT TRC20 + Boosty.
Отредактируй константы ниже под свои реальные реквизиты.
"""
import streamlit as st

# ─────────────────────────────────────────────
#  ✏️  ЗАПОЛНИ СВОИМИ ДАННЫМИ
# ─────────────────────────────────────────────
USDT_TRC20_ADDRESS = "ТВОЙ_USDT_TRC20_АДРЕС_ИЗ_BYBIT"   # Bybit → Assets → Deposit → USDT → TRC20
USDT_ERC20_ADDRESS = ""   # опционально, оставь пустым если не нужно
BTC_ADDRESS        = ""   # опционально
BOOSTY_URL         = "https://boosty.to/ТВОй_НИК"        # твой профиль на boosty.to
AUTHOR_NAME        = "Автор проекта"
PROJECT_NAME       = "Предсказания"
# ─────────────────────────────────────────────

QR_API = "https://api.qrserver.com/v1/create-qr-code/?data={data}&size=220x220&bgcolor=ffffff&color=1e293b&margin=10"


def _qr_url(data: str) -> str:
    import urllib.parse
    return QR_API.format(data=urllib.parse.quote(data, safe=""))


def render_donate_page() -> None:
    st.markdown("## :material/volunteer_activism: Поддержать проект")
    st.markdown(
        f"Если **{PROJECT_NAME}** оказался полезен — можно поддержать автора. "
        "Это помогает развивать модели, добавлять новые источники данных и не платить за сервер из кармана :material/favorite:"
    )

    st.divider()

    # ── CRYPTO ────────────────────────────────────────────────────────────────
    st.markdown("### :material/toll: Криптовалюта (из любой страны)")
    st.caption("Мгновенно · Анонимно · Комиссия ~$0 (TRC20)")

    crypto_tabs = ["USDT TRC20"]
    if USDT_ERC20_ADDRESS:
        crypto_tabs.append("USDT ERC20")
    if BTC_ADDRESS:
        crypto_tabs.append("BTC")

    tabs = st.tabs(crypto_tabs)

    # USDT TRC20
    with tabs[0]:
        if USDT_TRC20_ADDRESS and USDT_TRC20_ADDRESS != "ТВОЙ_USDT_TRC20_АДРЕС_ИЗ_BYBIT":
            col_qr, col_info = st.columns([1, 2], gap="large")
            with col_qr:
                st.image(_qr_url(USDT_TRC20_ADDRESS), width=200, caption="USDT TRC20")
            with col_info:
                st.markdown("**Сеть:** `TRON (TRC20)`")
                st.markdown("**Токен:** `USDT`")
                st.markdown("**Адрес:**")
                st.code(USDT_TRC20_ADDRESS, language=None)
                st.caption(":material/warning: Отправляй только USDT по сети TRC20 — иначе средства потеряются")
        else:
            st.warning(":material/settings: Адрес ещё не настроен. Открой `pages/_donate.py` и вставь свой USDT TRC20 адрес из Bybit.")
            st.markdown("""
**Как получить адрес в Bybit:**
1. Bybit → **Assets** → **Deposit**
2. Валюта: **USDT**
3. Сеть: **TRC20**
4. Скопируй адрес и вставь в `USDT_TRC20_ADDRESS` в файле `pages/_donate.py`
""")

    # USDT ERC20 (опционально)
    if USDT_ERC20_ADDRESS and len(tabs) > 1:
        with tabs[1]:
            col_qr, col_info = st.columns([1, 2], gap="large")
            with col_qr:
                st.image(_qr_url(USDT_ERC20_ADDRESS), width=200, caption="USDT ERC20")
            with col_info:
                st.markdown("**Сеть:** `Ethereum (ERC20)`")
                st.markdown("**Токен:** `USDT`")
                st.code(USDT_ERC20_ADDRESS, language=None)
                st.caption(":material/warning: Комиссия сети Ethereum обычно $5–20")

    # BTC (опционально)
    if BTC_ADDRESS:
        with tabs[-1]:
            col_qr, col_info = st.columns([1, 2], gap="large")
            with col_qr:
                st.image(_qr_url(BTC_ADDRESS), width=200, caption="Bitcoin")
            with col_info:
                st.markdown("**Сеть:** `Bitcoin`")
                st.code(BTC_ADDRESS, language=None)

    st.divider()

    # ── BOOSTY ────────────────────────────────────────────────────────────────
    st.markdown("### 🇷🇺 Boosty (рублёвая карта / зарубежная карта)")
    st.caption("Аналог Patreon · Принимает карты РФ и других стран · Разовый или регулярный донат")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(
            "Boosty — российский сервис для поддержки авторов. "
            "Принимает **карты РФ** (Visa/MC/Мир), а также **зарубежные карты** и **СБП**. "
            "Регистрация не нужна, достаточно выбрать сумму и оплатить."
        )
        if BOOSTY_URL and "ТВОй_НИК" not in BOOSTY_URL:
            st.link_button(":material/payments: Задонатить на Boosty", BOOSTY_URL, type="primary", use_container_width=True)
        else:
            st.warning(":material/settings: Вставь свой URL из Boosty в `BOOSTY_URL` в файле `pages/_donate.py`")
            st.markdown("""
**Как зарегистрироваться на Boosty:**
1. Зайди на [boosty.to](https://boosty.to) и войди через VK / телефон
2. Создай страницу автора
3. Скопируй ссылку на страницу (вида `boosty.to/твой_ник`) и вставь в `BOOSTY_URL`
""")
    with col2:
        st.image(
            "https://api.qrserver.com/v1/create-qr-code/"
            f"?data={BOOSTY_URL.replace('ТВОй_НИК', 'boosty.to') if 'ТВОй_НИК' not in BOOSTY_URL else 'https://boosty.to'}"
            "&size=160x160&bgcolor=ffffff&color=1e293b&margin=8",
            width=160,
            caption="QR → Boosty",
        )

    st.divider()

    # ── FAQ ───────────────────────────────────────────────────────────────────
    with st.expander(":material/help: FAQ — безопасно ли это? законно ли?"):
        st.markdown("""
**Криптовалюта (USDT):**
- :material/check_circle: Принимать USDT на личный кошелёк от других физлиц — легально в большинстве стран
- :material/check_circle: Bybit — лицензированная биржа, хранит USDT в cold storage
- :material/check_circle: Транзакции в сети TRC20 стоят ~$1 и занимают ~1 минуту
- ℹ️ В РФ: по закону о ЦФА криптовалюту можно получать, но нельзя использовать как средство платежа за товары/услуги. Для личных донатов — нет прямого запрета.

**Boosty:**
- :material/check_circle: Российский сервис, работает по российскому законодательству
- :material/check_circle: Выплаты через банковский перевод на ИП / самозанятого / физлицо
- :material/check_circle: Принимает карты из 40+ стран
        """)
