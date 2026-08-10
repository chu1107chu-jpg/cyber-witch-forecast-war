"""
Страница доната.
Пока без подключённых реквизитов — показываем нейтральную заглушку вместо
нерабочих кнопок/QR-кодов с плейсхолдерами. Когда появятся реальные
реквизиты (Boosty / крипто-кошелёк / ЮMoney) — впиши их в DONATE_METHODS
и включи блок ниже.
"""
import streamlit as st

AUTHOR_NAME  = "Автор проекта"
PROJECT_NAME = "Предсказания"

# ─────────────────────────────────────────────
#  Впиши реальные реквизиты сюда, когда будут готовы — и переключи
#  DONATE_METHODS_READY = True, чтобы показать рабочие кнопки.
# ─────────────────────────────────────────────
DONATE_METHODS_READY = False
BOOSTY_URL          = ""   # напр. "https://boosty.to/твой_ник"
USDT_TRC20_ADDRESS  = ""   # адрес кошелька USDT (сеть TRC20)
YOOMONEY_PHONE      = ""   # номер телефона для перевода по СБП


def render_donate_page() -> None:
    st.markdown("## :material/volunteer_activism: Поддержать проект")
    st.markdown(
        f"Если **{PROJECT_NAME}** оказался полезен — скоро здесь появится возможность "
        "поддержать автора. Это помогает развивать модели, добавлять новые источники "
        "данных и не платить за сервер из кармана :material/favorite:"
    )

    st.divider()

    if DONATE_METHODS_READY:
        if BOOSTY_URL:
            st.link_button(":material/payments: Задонатить на Boosty", BOOSTY_URL, type="primary", use_container_width=True)
        if USDT_TRC20_ADDRESS:
            st.markdown("**USDT (сеть TRC20):**")
            st.code(USDT_TRC20_ADDRESS, language=None)
        if YOOMONEY_PHONE:
            st.markdown(f"**Перевод по номеру телефона (СБП):** `{YOOMONEY_PHONE}`")
    else:
        st.info(
            ":material/hourglass_top: Раздел donate пока в разработке — реквизиты ещё не "
            "подключены. Загляните позже."
        )
