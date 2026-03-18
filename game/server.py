"""
FastAPI сервер Political Arena.
Порт 8502. Эндпоинты: fighters, fight, wallet.
"""

from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from game.engine import (
    MAX_BET, MIN_BET, FREE_FIGHTS_PER_DAY, PAYOUT_MULT,
    simulate_fight, fight_result_to_dict,
)
from game.fighters import FIGHTERS

# ── Пути ─────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# ── Приложение ───────────────────────────────────────────
app = FastAPI(title="Political Arena", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── In-memory сессии (без БД) ────────────────────────────
# sid → {balance, fights_today, last_fight_date, history[]}
_sessions: dict[str, dict[str, Any]] = {}
STARTING_BALANCE = 100  # 100₲ при старте

def _get_session(sid: str) -> dict[str, Any]:
    if sid not in _sessions:
        _sessions[sid] = {
            "balance": STARTING_BALANCE,
            "fights_today": 0,
            "last_fight_date": "",
            "history": [],
        }
    sess = _sessions[sid]
    today = time.strftime("%Y-%m-%d")
    if sess["last_fight_date"] != today:
        sess["fights_today"] = 0
        sess["last_fight_date"] = today
    return sess


def _get_sid(request: Request) -> str:
    sid = request.cookies.get("arena_sid")
    if not sid:
        sid = secrets.token_hex(16)
    return sid


# ── Pydantic модели ──────────────────────────────────────

class FightRequest(BaseModel):
    fighter_a: str
    fighter_b: str
    bet_fighter: str
    bet_amount: int = Field(ge=0, le=MAX_BET)
    client_seed: str = ""


class DepositRequest(BaseModel):
    amount: int = Field(ge=1, le=10000)


# ── API: Бойцы ───────────────────────────────────────────

@app.get("/api/fighters")
def api_fighters():
    """Список всех бойцов (без moves для экономии трафика)."""
    result = []
    for f in FIGHTERS:
        result.append({
            "id": f["id"],
            "name": f["name"],
            "name_en": f["name_en"],
            "emoji": f["emoji"],
            "country": f["country"],
            "type": f["type"],
            "color": f["color"],
            "gradient": f["gradient"],
            "hp": f["hp"],
            "atk": f["atk"],
            "def": f["def"],
            "spd": f["spd"],
            "luck": f["luck"],
            "taunt": f["taunt"],
        })
    return {"fighters": result, "total": len(result)}


@app.get("/api/fighters/{fighter_id}")
def api_fighter_detail(fighter_id: str):
    """Детали бойца с moves."""
    for f in FIGHTERS:
        if f["id"] == fighter_id:
            return f
    raise HTTPException(404, "Боец не найден")


# ── API: Бой ─────────────────────────────────────────────

@app.post("/api/fight")
def api_fight(req: FightRequest, request: Request, response: Response):
    """Запустить бой и получить результат."""
    sid = _get_sid(request)
    sess = _get_session(sid)

    # Проверяем бесплатные бои
    is_free = req.bet_amount == 0
    if is_free:
        if sess["fights_today"] >= FREE_FIGHTS_PER_DAY:
            raise HTTPException(429, f"Лимит бесплатных боёв: {FREE_FIGHTS_PER_DAY}/день. Сделайте ставку!")
    else:
        if req.bet_amount < MIN_BET:
            raise HTTPException(400, f"Минимальная ставка: {MIN_BET}₲")
        if req.bet_amount > sess["balance"]:
            raise HTTPException(400, f"Недостаточно ₲. Баланс: {sess['balance']}₲")

    # Списываем ставку
    if not is_free:
        sess["balance"] -= req.bet_amount

    # Бой
    try:
        result = simulate_fight(
            fighter_a_id=req.fighter_a,
            fighter_b_id=req.fighter_b,
            bet_fighter_id=req.bet_fighter,
            bet_amount=req.bet_amount,
            client_seed=req.client_seed,
        )
    except ValueError as e:
        # Возвращаем ставку при ошибке
        if not is_free:
            sess["balance"] += req.bet_amount
        raise HTTPException(400, str(e))

    # Начисляем выигрыш
    if result.bet_won and not is_free:
        sess["balance"] += result.payout

    sess["fights_today"] += 1

    # Записываем историю (последние 20)
    sess["history"].append({
        "fight_id": result.fight_id,
        "winner": result.winner_id,
        "bet_won": result.bet_won,
        "amount": req.bet_amount,
        "payout": result.payout,
        "ts": int(time.time()),
    })
    if len(sess["history"]) > 20:
        sess["history"] = sess["history"][-20:]

    # Ответ
    data = fight_result_to_dict(result)
    data["wallet"] = {
        "balance": sess["balance"],
        "fights_today": sess["fights_today"],
        "free_remaining": max(0, FREE_FIGHTS_PER_DAY - sess["fights_today"]),
    }

    response.set_cookie("arena_sid", sid, max_age=86400 * 30, httponly=True, samesite="lax")
    return data


# ── API: Кошелёк ─────────────────────────────────────────

@app.get("/api/wallet")
def api_wallet(request: Request, response: Response):
    """Текущий баланс и статистика."""
    sid = _get_sid(request)
    sess = _get_session(sid)
    response.set_cookie("arena_sid", sid, max_age=86400 * 30, httponly=True, samesite="lax")

    wins = sum(1 for h in sess["history"] if h["bet_won"])
    total = len(sess["history"])

    return {
        "balance": sess["balance"],
        "fights_today": sess["fights_today"],
        "free_remaining": max(0, FREE_FIGHTS_PER_DAY - sess["fights_today"]),
        "total_fights": total,
        "wins": wins,
        "losses": total - wins,
        "winrate": round(wins / total * 100, 1) if total > 0 else 0,
        "history": sess["history"][-10:],
    }


@app.post("/api/wallet/deposit")
def api_deposit(req: DepositRequest, request: Request, response: Response):
    """Пополнение баланса (заглушка — без реальной оплаты)."""
    sid = _get_sid(request)
    sess = _get_session(sid)
    sess["balance"] += req.amount
    response.set_cookie("arena_sid", sid, max_age=86400 * 30, httponly=True, samesite="lax")
    return {"balance": sess["balance"], "deposited": req.amount}


# ── Главная страница ─────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    """Отдаёт фронтенд."""
    html_path = TEMPLATES_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Political Arena</h1><p>Frontend coming soon...</p>")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ── Запуск ───────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("ARENA_PORT", 8502))
    uvicorn.run("game.server:app", host="0.0.0.0", port=port, reload=True)
