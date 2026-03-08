"""/api/v1/snake — Utility Snake «Лови бонусы» (Провабли-фэир)"""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid, time, hashlib, hmac

router = APIRouter()

CANVAS_W, CANVAS_H = 800, 600
BASKET_W_PCT = 0.12
MAX_PAYOUT_X = 10.0

PAYOUTS = [
    ("GOLD",   0.005, 10.0),
    ("PURPLE", 0.015,  5.0),
    ("BLUE",   0.030,  2.0),
    ("GREEN",  0.100,  1.0),
    ("YELLOW", 0.200,  0.5),
    ("RED",    0.250,  0.2),
    ("GRAY",   0.400,  0.0),
]
_CUM = []
_acc = 0.0
for _, p, _ in PAYOUTS:
    _acc += p
    _CUM.append(_acc)


def _hmac_bytes(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


def _to_u01(b: bytes) -> float:
    return int.from_bytes(b[:32], "big") / (1 << 256)


def _draw_bucket(u: float):
    for (name, p, r), c in zip(PAYOUTS, _CUM):
        if u <= c:
            return name, r
    return "GRAY", 0.0


def _day_key() -> bytes:
    import os
    from datetime import date
    salt = os.getenv("SECRET_KEY", "default_secret_salt").encode()
    return hashlib.sha256(salt + date.today().isoformat().encode()).digest()


# In-memory store (в проде — Supabase/Redis)
ROUND_STORE: dict = {}


class StartReq(BaseModel):
    stake: int = Field(gt=0)
    client_seed: Optional[str] = None
    idempotency_key: str = Field(default_factory=lambda: str(uuid.uuid4()))


class PosEvent(BaseModel):
    ts: int    # мс от начала раунда
    x: float


class FinishReq(BaseModel):
    round_id: str
    client_nonce: str
    positions: List[PosEvent]


def get_current_user(authorization: str = Header(...)):
    from src.utils.auth import verify_jwt
    return verify_jwt(authorization.removeprefix("Bearer "))


@router.post("/session/start")
async def start_session(req: StartReq, user=Depends(get_current_user)):
    from src.wallet.credits import debit
    from src.utils.config import load_games_config

    cfg = next((g for g in load_games_config() if g["game_id"] == "snake_v1"), {})
    diff = cfg.get("difficulty", {})
    dur_sec = diff.get("round_duration_sec", 45)

    d = debit(
        user_id=user["sub"],
        amount=req.stake,
        description="snake_bet",
        idempotency_key=req.idempotency_key,
    )
    if not d["ok"]:
        raise HTTPException(402, "Insufficient balance")

    rid = "rnd_" + uuid.uuid4().hex[:12]
    server_seed = _hmac_bytes(_day_key(), rid.encode())
    ROUND_STORE[rid] = {
        "stake": req.stake,
        "user_id": user["sub"],
        "server_seed": server_seed,
        "started_at": time.time(),
        "cfg": cfg,
    }

    return {
        "ok": True,
        "data": {
            "round_id": rid,
            "server_seed_hash": "sha256:" + hashlib.sha256(server_seed).hexdigest(),
            "round_duration_sec": dur_sec,
            "canvas": {"w": CANVAS_W, "h": CANVAS_H},
            "basket": {"width_pct": diff.get("basket_width_pct", 12)},
            "spawn_params": {
                "rate": diff.get("spawn_rate_per_sec", 1.0),
                "jitter": diff.get("spawn_jitter", 0.5),
                "speed_base": diff.get("fall_speed_base", 180),
                "speed_jitter": diff.get("fall_speed_jitter", 60),
            },
        },
    }


@router.post("/session/finish")
async def finish_session(req: FinishReq, user=Depends(get_current_user)):
    st = ROUND_STORE.get(req.round_id)
    if not st:
        raise HTTPException(404, "round not found")
    if st["user_id"] != user["sub"]:
        raise HTTPException(403, "not your round")

    stake = st["stake"]
    server_seed = st["server_seed"]
    cfg = st.get("cfg", {})
    diff = cfg.get("difficulty", {})
    dur_ms = diff.get("round_duration_sec", 45) * 1000
    spawn_rate = diff.get("spawn_rate_per_sec", 1.0)
    spawn_jitter = diff.get("spawn_jitter", 0.5)
    speed_base = diff.get("fall_speed_base", 180)
    speed_jitter = diff.get("fall_speed_jitter", 60)
    basket_w = (diff.get("basket_width_pct", 12) / 100.0) * CANVAS_W

    base = _hmac_bytes(server_seed, b"spawns:" + req.client_nonce.encode())

    # generate deterministic spawns
    spawns = []
    t = 0.0
    while t < dur_ms / 1000:
        u_gap = _to_u01(_hmac_bytes(base, f"gap:{len(spawns)}".encode()))
        gap = max(0.1, (1.0 / spawn_rate) + (u_gap - 0.5) * spawn_jitter)
        t += gap
        if t > dur_ms / 1000:
            break
        u_x = _to_u01(_hmac_bytes(base, f"x:{len(spawns)}".encode()))
        u_ty = _to_u01(_hmac_bytes(base, f"type:{len(spawns)}".encode()))
        u_sp = _to_u01(_hmac_bytes(base, f"speed:{len(spawns)}".encode()))
        kind, r = _draw_bucket(u_ty)
        speed = max(60.0, speed_base + (u_sp - 0.5) * 2 * speed_jitter)
        spawns.append({"t0": t, "x": u_x * CANVAS_W, "kind": kind, "r": r, "v": speed})

    # interpolate basket position
    positions = sorted(req.positions, key=lambda p: p.ts)

    def basket_x_at(ms: int) -> float:
        if not positions:
            return CANVAS_W / 2
        for i in range(1, len(positions)):
            if ms <= positions[i].ts:
                a, b = positions[i - 1], positions[i]
                if b.ts == a.ts:
                    return b.x
                k = (ms - a.ts) / (b.ts - a.ts)
                return a.x + k * (b.x - a.x)
        return positions[-1].x

    payout = 0.0
    caught = []
    for s in spawns:
        t_hit = s["t0"] + CANVAS_H / s["v"]
        if t_hit * 1000 > dur_ms:
            continue
        bx = basket_x_at(int(t_hit * 1000))
        if abs(bx - s["x"]) <= basket_w / 2:
            gain = stake * s["r"]
            payout += gain
            caught.append({"t": int(t_hit * 1000), "kind": s["kind"], "r": s["r"]})

    payout = min(payout, stake * MAX_PAYOUT_X)
    payout_int = int(round(payout))

    if payout_int > 0:
        from src.wallet.credits import credit
        credit(user_id=user["sub"], amount=payout_int, description="snake_reward")

    # persist
    from src.utils.db import get_db
    get_db().table("snake_rounds").insert({
        "round_id": req.round_id,
        "user_id": user["sub"],
        "stake": stake,
        "payout": payout_int,
        "server_seed_hash": "sha256:" + hashlib.sha256(server_seed).hexdigest(),
        "client_seed": st.get("client_seed"),
        "client_nonce": req.client_nonce,
        "rtp_snapshot": payout / stake if stake else 0,
    }).execute()

    del ROUND_STORE[req.round_id]

    return {
        "ok": True,
        "data": {
            "payout": payout_int,
            "caught": caught,
            "rtp_estimate": round(payout / stake, 4) if stake else 0.0,
            "balance_after": None,  # TODO: fetch from wallet
            "provably_fair": {
                "server_seed_hash": "sha256:" + hashlib.sha256(server_seed).hexdigest(),
                "server_seed_reveal_at": "next day 00:00 UTC",
                "client_seed": req.client_nonce,
            },
        },
    }
