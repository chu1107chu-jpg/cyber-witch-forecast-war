"""
FastAPI сервер Political Arena.
Порт 8502. SQLite persistence. Telegram Login. Daily bonus. Referral.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import random
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
    MAX_BET, MIN_BET, FREE_FIGHTS_PER_DAY, PAYOUT_MULT, ROUNDS,
    simulate_fight, fight_result_to_dict,
    create_fight_state, play_round, get_user_moves, FightState,
)
from game.fighters import FIGHTERS
from game.db import (
    get_or_create_user, link_telegram, update_balance,
    claim_daily, process_referral, record_fight,
    get_history, get_leaderboard, get_user_by_tg, set_field,
)

# ── Paths ────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")

# ── App ──────────────────────────────────────────────────
app = FastAPI(title="Political Arena", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Fight states (in-memory, stateless on restart) ───────
_fight_states: dict[str, tuple[FightState, int]] = {}  # fight_id → (state, user_id)

STARTING_BALANCE = 100

# ── Helpers ──────────────────────────────────────────────

def _get_sid(request: Request) -> str:
    sid = request.cookies.get("arena_sid")
    if not sid:
        sid = secrets.token_hex(16)
    return sid

def _get_user(request: Request) -> dict:
    sid = _get_sid(request)
    return get_or_create_user(sid)

def _set_cookie(response: Response, sid: str):
    response.set_cookie("arena_sid", sid, max_age=86400 * 90, httponly=True, samesite="lax")

def _wallet_dict(u: dict) -> dict:
    return {
        "balance": u["balance"],
        "fights_today": u["fights_today"],
        "free_remaining": max(0, FREE_FIGHTS_PER_DAY - u["fights_today"]),
        "streak": u["streak"],
        "best_streak": u["best_streak"],
    }

# ── Pydantic ─────────────────────────────────────────────

class FightStartRequest(BaseModel):
    fighter_a: str
    fighter_b: str
    bet_fighter: str
    bet_amount: int = Field(ge=0, le=MAX_BET)
    client_seed: str = ""

class RoundRequest(BaseModel):
    fight_id: str
    move_index: int = Field(ge=0, le=3)

class TelegramAuth(BaseModel):
    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    photo_url: str = ""
    auth_date: int
    hash: str

class ReferralClaim(BaseModel):
    ref_code: str

# ── API: Page ────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    return (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")

# ── API: Fighters ────────────────────────────────────────

@app.get("/api/fighters")
def api_fighters():
    result = []
    for f in FIGHTERS:
        avatar_png = STATIC_DIR / "avatars" / f"{f['id']}.png"
        avatar_ext = "png" if avatar_png.exists() else "svg"
        total = f["hp"] + f["atk"] + f["def"] + f["spd"] + f.get("luck", 0)
        if total >= 350: tier = "legendary"
        elif total >= 300: tier = "epic"
        elif total >= 250: tier = "rare"
        elif total >= 200: tier = "uncommon"
        else: tier = "common"
        result.append({
            "id": f["id"], "name": f["name"], "name_en": f["name_en"],
            "emoji": f["emoji"], "country": f["country"],
            "type": f["type"], "color": f["color"], "gradient": f["gradient"],
            "hp": f["hp"], "atk": f["atk"], "def": f["def"],
            "spd": f["spd"], "luck": f.get("luck", 5),
            "taunt": f["taunt"],
            "weakness": f.get("weakness", ""),
            "strength": f.get("strength", ""),
            "strength_meme": f.get("strength_meme", ""),
            "weakness_meme": f.get("weakness_meme", ""),
            "avatar": f"/static/avatars/{f['id']}.{avatar_ext}",
            "tier": tier,
        })
    return {"fighters": result, "total": len(result)}

@app.get("/api/fighters/{fighter_id}")
def api_fighter_detail(fighter_id: str):
    for f in FIGHTERS:
        if f["id"] == fighter_id:
            return f
    raise HTTPException(404, "Fighter not found")

# ── API: Auth ────────────────────────────────────────────

@app.get("/api/auth/me")
def api_auth_me(request: Request, response: Response):
    user = _get_user(request)
    _set_cookie(response, user["sid"])
    return {
        "id": user["id"],
        "sid": user["sid"],
        "telegram_id": user["telegram_id"],
        "telegram_name": user["telegram_name"],
        "telegram_user": user["telegram_user"],
        "telegram_photo": user["telegram_photo"],
        "balance": user["balance"],
        "total_wins": user["total_wins"],
        "total_losses": user["total_losses"],
        "streak": user["streak"],
        "best_streak": user["best_streak"],
        "referral_count": user["referral_count"],
        "daily_streak": user["daily_streak"],
        "last_daily_date": user["last_daily_date"],
        "ref_code": user["sid"][:8],
    }

@app.post("/api/auth/telegram")
def api_auth_telegram(auth: TelegramAuth, request: Request, response: Response):
    # Verify Telegram auth hash
    if TG_BOT_TOKEN:
        check_data = "\n".join(
            f"{k}={v}" for k, v in sorted(auth.model_dump().items())
            if k != "hash" and v != ""
        )
        secret = hashlib.sha256(TG_BOT_TOKEN.encode()).digest()
        expected = hmac.new(secret, check_data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, auth.hash):
            raise HTTPException(403, "Invalid Telegram auth")
        # Check auth_date not too old (1 day)
        if time.time() - auth.auth_date > 86400:
            raise HTTPException(403, "Auth expired")

    user = _get_user(request)
    name = f"{auth.first_name} {auth.last_name}".strip()
    linked = link_telegram(user["id"], auth.id, name, auth.username, auth.photo_url)
    _set_cookie(response, linked["sid"])
    return {"ok": True, "user": {
        "telegram_id": linked["telegram_id"],
        "telegram_name": linked["telegram_name"],
        "telegram_user": linked["telegram_user"],
        "telegram_photo": linked["telegram_photo"],
        "balance": linked["balance"],
    }}

# ── API: Daily Bonus ─────────────────────────────────────

@app.post("/api/daily")
def api_daily(request: Request, response: Response):
    user = _get_user(request)
    _set_cookie(response, user["sid"])
    result = claim_daily(user["id"])
    return result

# ── API: Referral ────────────────────────────────────────

@app.post("/api/referral")
def api_referral(req: ReferralClaim, request: Request, response: Response):
    user = _get_user(request)
    _set_cookie(response, user["sid"])
    # Find referrer by ref_code (first 8 chars of their sid)
    from game.db import get_db
    conn = get_db()
    referrer = conn.execute(
        "SELECT * FROM users WHERE substr(sid,1,8) = ?", (req.ref_code,)
    ).fetchone()
    conn.close()
    if not referrer:
        raise HTTPException(404, "Invalid referral code")
    result = process_referral(referrer["id"], user["id"])
    if not result["ok"]:
        raise HTTPException(400, result["reason"])
    # Get updated balance
    fresh = get_or_create_user(user["sid"])
    return {"ok": True, "bonus": result["referred_bonus"], "balance": fresh["balance"]}

# ── API: Leaderboard ─────────────────────────────────────

@app.get("/api/leaderboard")
def api_leaderboard():
    return {"top": get_leaderboard(20)}

# ── API: Spin Wheel ──────────────────────────────────────

SPIN_SEGMENTS = [
    {"mult": 0.5, "weight": 25, "label": "×0.5"},
    {"mult": 1.0, "weight": 35, "label": "×1.0"},
    {"mult": 1.5, "weight": 20, "label": "×1.5"},
    {"mult": 2.0, "weight": 12, "label": "×2.0"},
    {"mult": 3.0, "weight": 5,  "label": "×3.0"},
    {"mult": 5.0, "weight": 3,  "label": "×5.0"},
]

@app.post("/api/spin")
def api_spin(request: Request, response: Response):
    user = _get_user(request)
    _set_cookie(response, user["sid"])
    # Weighted random
    total_w = sum(s["weight"] for s in SPIN_SEGMENTS)
    r = random.random() * total_w
    acc = 0
    chosen = SPIN_SEGMENTS[1]  # default ×1.0
    for seg in SPIN_SEGMENTS:
        acc += seg["weight"]
        if r <= acc:
            chosen = seg
            break
    return {
        "mult": chosen["mult"],
        "label": chosen["label"],
        "segments": SPIN_SEGMENTS,
    }

# ── API: Fight (step-by-step) ────────────────────────────

@app.post("/api/fight/start")
def api_fight_start(req: FightStartRequest, request: Request, response: Response):
    user = _get_user(request)
    _set_cookie(response, user["sid"])

    is_free = req.bet_amount == 0
    if is_free:
        if user["fights_today"] >= FREE_FIGHTS_PER_DAY:
            raise HTTPException(429, f"Daily limit: {FREE_FIGHTS_PER_DAY} free fights")
    else:
        if req.bet_amount < MIN_BET:
            raise HTTPException(400, f"Min bet: {MIN_BET}₲")
        if req.bet_amount > user["balance"]:
            raise HTTPException(400, f"Not enough ₲. Balance: {user['balance']}₲")
        update_balance(user["id"], -req.bet_amount)

    try:
        state = create_fight_state(
            fighter_a_id=req.fighter_a, fighter_b_id=req.fighter_b,
            bet_fighter_id=req.bet_fighter, bet_amount=req.bet_amount,
            client_seed=req.client_seed,
        )
    except ValueError as e:
        if not is_free:
            update_balance(user["id"], req.bet_amount)
        raise HTTPException(400, str(e))

    _fight_states[state.fight_id] = (state, user["id"])
    moves, ai_hint = get_user_moves(state)

    return {
        "fight_id": state.fight_id,
        "user_is_a": state.user_is_a,
        "round": state.current_round,
        "total_rounds": ROUNDS,
        "moves": moves,
        "ai_hint": ai_hint,
        "fighter_a": {
            "id": state.fa_orig["id"], "name": state.fa_orig["name"],
            "emoji": state.fa_orig["emoji"], "hp": state.fa_orig["hp"],
        },
        "fighter_b": {
            "id": state.fb_orig["id"], "name": state.fb_orig["name"],
            "emoji": state.fb_orig["emoji"], "hp": state.fb_orig["hp"],
        },
    }

@app.post("/api/fight/round")
def api_fight_round(req: RoundRequest, request: Request, response: Response):
    user = _get_user(request)
    _set_cookie(response, user["sid"])

    entry = _fight_states.get(req.fight_id)
    if not entry:
        raise HTTPException(404, "Fight not found")
    state, uid = entry
    if uid != user["id"]:
        raise HTTPException(403, "Not your fight")

    try:
        rd = play_round(state, req.move_index)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if rd.get("fight_over"):
        result = rd["result"]
        bet_won = result["bet"]["won"]
        bet_amount = result["bet"]["amount"]
        payout = result["bet"]["payout"]

        # Streak multiplier
        current_streak = user["streak"]
        if bet_won:
            new_streak = current_streak + 1
        else:
            new_streak = 0

        if bet_won and bet_amount > 0:
            if new_streak >= 5:
                payout = int(payout * 2.0)
            elif new_streak >= 3:
                payout = int(payout * 1.5)
            elif new_streak >= 2:
                payout = int(payout * 1.2)
            result["bet"]["payout"] = payout
            update_balance(user["id"], payout)

        # Record in DB
        record_fight(
            user["id"], state.fight_id,
            state.fa_orig["id"], state.fb_orig["id"],
            result["winner_id"], state.bet_fighter_id,
            bet_amount, payout, bet_won,
        )

        # Refresh user for wallet
        fresh = get_or_create_user(user["sid"])
        rd["wallet"] = _wallet_dict(fresh)
        rd["wallet"]["streak"] = fresh["streak"]
        del _fight_states[req.fight_id]

    return rd

# ── API: Wallet ──────────────────────────────────────────

@app.get("/api/wallet")
def api_wallet(request: Request, response: Response):
    user = _get_user(request)
    _set_cookie(response, user["sid"])
    history = get_history(user["id"], 10)
    return {
        **_wallet_dict(user),
        "total_fights": user["total_wins"] + user["total_losses"],
        "wins": user["total_wins"],
        "losses": user["total_losses"],
        "winrate": round(user["total_wins"] / max(1, user["total_wins"] + user["total_losses"]) * 100, 1),
        "history": history,
    }

@app.post("/api/wallet/deposit")
def api_wallet_deposit(request: Request, response: Response):
    user = _get_user(request)
    _set_cookie(response, user["sid"])
    new_bal = update_balance(user["id"], 100)
    return {"balance": new_bal}
