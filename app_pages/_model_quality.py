from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

LABELS = {"target_p5_up": "Рост через 5 дней", "target_p20_up": "Рост через 20 дней"}


def _fmt_ci(ci) -> str:
    return f"{ci[0]:.3f}–{ci[1]:.3f}" if ci else "—"


def _verdict_auc(auc: float, ci) -> str:
    if ci:
        if ci[0] > 0.5:
            return "значимо выше 0.5, но запас небольшой"
        return "в пределах шума: от случайного угадывания не отличить"
    return "почти случайно (0.5 = монетка)" if abs(auc - 0.5) < 0.03 else "выше случайного"


def _verdict_diff(diff, ci) -> str:
    if diff is None or not ci:
        return "—"
    if ci[0] > 0:
        return "лучше"
    if ci[1] < 0:
        return "хуже"
    return "в пределах шума"


def render_model_quality(summary: dict, history: list, source: str) -> None:
    metrics = summary.get("metrics", {})
    trained = summary.get("trained_at", "")
    try:
        dt = datetime.fromisoformat(trained)
        dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - dt).days
        when = f"{dt:%d.%m.%Y} ({age} дн. назад)"
    except Exception:
        when = "неизвестно"
    src = "переобучена в приложении" if source == "live" else "из репозитория"
    through = summary.get("trained_through") or (summary.get("train_period", "").split("→")[-1].strip() or "?")

    st.markdown(f"**Модель обучена:** {when} · {src} · данные до {through}")

    rows = []
    for t, m in metrics.items():
        auc = m.get("oos_auc")
        ci = m.get("oos_auc_ci95")
        acc, base = m.get("oos_acc"), m.get("oos_acc_baseline")
        rows.append({
            "Прогноз": LABELS.get(t, t),
            "AUC на новых данных": f"{auc:.3f}" if auc is not None else "—",
            "95% интервал": _fmt_ci(ci),
            "Точность": f"{acc:.1%}" if acc is not None else "н/д",
            "Если всегда «вверх/вниз»": f"{base:.1%}" if base is not None else "н/д",
            "Вывод": _verdict_auc(auc, ci) if auc is not None else "—",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        if any(m.get("oos_acc") is None for m in metrics.values()):
            st.caption("«н/д» — эта модель обучена по старой схеме, доверительные интервалы и точность появятся после первого переобучения в приложении.")

    st.caption(
        "AUC 0.5 — это угадывание монеткой, 1.0 — идеал. На рынке акций устойчивые 0.52–0.55 уже считаются хорошим "
        "результатом. «Новые данные» — период, который модель при обучении не видела. «Точность» без сравнения со "
        "стратегией «всегда вверх» ничего не значит: рынок растёт чуть чаще, чем падает."
    )

    if history:
        st.markdown("**История переобучений**")
        h_rows = []
        for h in reversed(history[-10:]):
            t5 = (h.get("targets") or {}).get("target_p5_up", {})
            t20 = (h.get("targets") or {}).get("target_p20_up", {})
            vc = (h.get("vs_champion") or {}).get("target_p20_up") or (h.get("vs_champion") or {}).get("target_p5_up") or {}
            h_rows.append({
                "Дата": (h.get("trained_at") or "")[:10],
                "Статус": {"promoted": "принята", "rejected": "отклонена (хуже прежней)"}.get(h.get("status"), h.get("status")),
                "AUC 5д": t5.get("oos_auc"), "AUC 20д": t20.get("oos_auc"),
                "К прежней (20д)": (f"{vc['diff']:+.3f} · {_verdict_diff(vc.get('diff'), vc.get('diff_ci95'))}" if vc.get("diff") is not None else "—"),
            })
        st.dataframe(pd.DataFrame(h_rows), hide_index=True, use_container_width=True)
        st.caption(
            "«К прежней» — разница AUC новой и старой модели на одних и тех же датах, которых не видела ни одна из них, "
            "с 95%-интервалом по месяцам. «В пределах шума» значит: вывод «стало лучше» делать нельзя. "
            "Если новая модель значимо хуже, приложение её не принимает и оставляет прежнюю."
        )

    comp = summary.get("vs_champion") or {}
    if comp:
        for t, c in comp.items():
            st.markdown(
                f"- **{LABELS.get(t, t)}:** новая {c['new_auc']:.3f} против прежней {c['old_auc']:.3f} на {c['window']} "
                f"({c['n']} наблюдений), разница {c['diff']:+.3f} [95%: {c['diff_ci95'][0]:+.3f}…{c['diff_ci95'][1]:+.3f}] — "
                f"{_verdict_diff(c['diff'], c['diff_ci95'])}"
            )
