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
    "started_at": None,
    "finished_at": None,
    "last_error": None,
    "next_try_at": 0.0,
    "log": [],
    "committed_dir": None,
    "last_summary": None,
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
    try:
        return (LIVE_DIR / "train_summary.json").stat().st_mtime
    except OSError:
        return 0.0


def pick_artifacts_dir(committed_dir: Path) -> Path:
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
        champion = pick_artifacts_dir(STATE["committed_dir"]) if STATE.get("committed_dir") else None
        summary = train_all(LIVE_DIR, run_cv=False, n_jobs=2, log=_log, champion_dir=champion)
        STATE["last_error"] = None
        # новая модель оказалась значимо хуже — оставляем действующую и не повторяем неделю
        STATE["next_try_at"] = 0.0 if summary.get("promoted", True) else time.time() + 7 * 86400
        STATE["last_summary"] = {"promoted": summary.get("promoted", True), "trained_at": summary.get("trained_at")}
    except Exception as e:
        STATE["last_error"] = f"{type(e).__name__}: {e}"
        STATE["next_try_at"] = time.time() + RETRY_AFTER_ERROR_SEC
        _log("ОШИБКА: " + "".join(traceback.format_exception_only(type(e), e)).strip())
    finally:
        STATE["finished_at"] = time.time()
        STATE["running"] = False


def read_history(committed_dir: Path) -> list:
    out = []
    for d in (committed_dir, LIVE_DIR):
        try:
            out += json.loads((Path(d) / "train_history.json").read_text(encoding="utf-8"))
        except Exception:
            pass
    seen, uniq = set(), []
    for h in sorted(out, key=lambda e: e.get("trained_at", "")):
        if h.get("trained_at") not in seen:
            seen.add(h.get("trained_at")); uniq.append(h)
    return uniq


def start(force: bool = False) -> bool:
    with _LOCK:
        if STATE["running"]:
            return False
        if not force and time.time() < STATE["next_try_at"]:
            return False
        STATE.update(running=True, started_at=time.time(), finished_at=None, log=[])
    threading.Thread(target=_worker, name="stock-retrain", daemon=True).start()
    return True


def maybe_start(committed_dir: Path, max_age_days: float = MAX_AGE_DAYS) -> bool:
    STATE["committed_dir"] = committed_dir
    age = model_age_days(committed_dir)
    if age is not None and age < max_age_days:
        return False
    return start(force=False)
