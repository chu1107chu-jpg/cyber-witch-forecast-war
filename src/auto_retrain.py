"""
auto_retrain.py
===============
Фоновое переобучение модели прямо внутри работающего Streamlit-приложения.

Зачем: GitHub Actions у владельца заблокированы (проблема биллинга аккаунта), а
Streamlit Cloud и так ходит в Yahoo Finance за котировками. Поэтому обучаем здесь.

Как работает:
  * модуль живёт в sys.modules, поэтому состояние (STATE) общее для всех сессий и
    переживает перезапуски скрипта Streamlit — одновременно идёт максимум одно обучение;
  * maybe_start() вызывается при каждом запуске скрипта, но реально стартует только если
    свежая модель (live или из репозитория) старше MAX_AGE_DAYS и нет паузы после ошибки;
  * результат пишется в LIVE_DIR (временная папка контейнера) атомарно; приложение
    подхватывает его по mtime файла (см. live_version() / pick_artifacts_dir());
  * после перезапуска контейнера (Streamlit Cloud усыпляет бесплатные приложения)
    LIVE_DIR пропадает, берётся модель из репозитория, и при ближайшем визите,
    если она старше недели, обучение запускается снова.
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

LIVE_DIR = Path(tempfile.gettempdir()) / "cwf_lgbm_live"
MAX_AGE_DAYS = 7
RETRY_AFTER_ERROR_SEC = 6 * 3600     # не долбим Yahoo при каждой перезагрузке страницы

_LOCK = threading.Lock()
STATE: dict = {
    "running": False,
    "started_at": None,      # epoch
    "finished_at": None,     # epoch
    "last_error": None,
    "next_try_at": 0.0,
    "log": [],
}


def _read_summary(d: Path) -> dict | None:
    try:
        return json.loads((d / "train_summary.json").read_text(encoding="utf-8"))
    except Exception:
        return None


def _trained_at(summary: dict | None) -> datetime | None:
    if not summary or not summary.get("trained_at"):
        return None
    try:
        dt = datetime.fromisoformat(summary["trained_at"])
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def live_version() -> float:
    """mtime live-модели (0.0 если её нет) — ключ кэша для st.cache_resource."""
    try:
        return (LIVE_DIR / "train_summary.json").stat().st_mtime
    except OSError:
        return 0.0


def pick_artifacts_dir(committed_dir: Path) -> Path:
    """Live-модель, если она есть, целая и свежее репозиторной; иначе репозиторная."""
    live = _read_summary(LIVE_DIR)
    if live and (LIVE_DIR / "models.pkl").exists() and (LIVE_DIR / "feature_cols.pkl").exists():
        t_live, t_repo = _trained_at(live), _trained_at(_read_summary(committed_dir))
        if t_live and (t_repo is None or t_live >= t_repo):
            return LIVE_DIR
    return committed_dir


def model_age_days(committed_dir: Path) -> float | None:
    d = pick_artifacts_dir(committed_dir)
    t = _trained_at(_read_summary(d))
    return None if t is None else (datetime.now(timezone.utc) - t).total_seconds() / 86400


def _log(msg: str) -> None:
    STATE["log"] = (STATE["log"] + [msg])[-40:]


def _worker() -> None:
    try:
        # импорт здесь: тяжёлые зависимости не нужны, пока обучение не стартует
        from stock_training import train_all
        train_all(LIVE_DIR, run_cv=False, n_jobs=2, log=_log)
        STATE["last_error"] = None
        STATE["next_try_at"] = 0.0
    except Exception as e:
        STATE["last_error"] = f"{type(e).__name__}: {e}"
        STATE["next_try_at"] = time.time() + RETRY_AFTER_ERROR_SEC
        _log("ОШИБКА: " + "".join(traceback.format_exception_only(type(e), e)).strip())
    finally:
        STATE["finished_at"] = time.time()
        STATE["running"] = False


def start(force: bool = False) -> bool:
    """Запускает обучение в фоне. True — если запустили, False — уже идёт / пауза."""
    with _LOCK:
        if STATE["running"]:
            return False
        if not force and time.time() < STATE["next_try_at"]:
            return False
        STATE.update(running=True, started_at=time.time(), finished_at=None, log=[])
    threading.Thread(target=_worker, name="stock-retrain", daemon=True).start()
    return True


def maybe_start(committed_dir: Path, max_age_days: float = MAX_AGE_DAYS) -> bool:
    """Запускает обучение, если модель устарела. Дёшево вызывать на каждом rerun."""
    age = model_age_days(committed_dir)
    if age is not None and age < max_age_days:
        return False
    return start(force=False)
