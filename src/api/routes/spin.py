"""/api/v1/spin — Utility-token Spin (slot) механика (Provably Fair)"""
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
import uuid, time

router = APIRouter()


class PlayReq(BaseModel):
    game_id: str = "utility_slot_v1"
    stake: int = Field(gt=0)
    client_nonce: str = Field(default_factory=lambda: uuid.uuid4().hex)
    idempotency_key: str = Field(default_factory=lambda: str(uuid.uuid4()))


def get_current_user(authorization: str = Header(...)):
    from src.utils.auth import verify_jwt
    return verify_jwt(authorization.removeprefix("Bearer "))


@router.get("/games")
async def list_games():
    from src.utils.config import load_games_config
    return {"ok": True, "data": {"items": load_games_config()}}


@router.post("/play")
async def play(req: PlayReq, user=Depends(get_current_user)):
    from fastapi import HTTPException
    from src.wallet.credits import debit, credit, get_balance
    from src.utils.rng import get_engine   # ← синглтон, не новый объект

    engine = get_engine(game_id=req.game_id)

    # Проверка лимитов ставки
    engine.check_limits(user["sub"], req.stake)

    # Списание ставки
    d = debit(
        user_id=user["sub"],
        amount=req.stake,
        description="spin_bet",
        idempotency_key=req.idempotency_key,
    )
    if not d["ok"]:
        raise HTTPException(402, "Insufficient balance")

    # Бросок колеса
    result = engine.draw(user_id=user["sub"], client_nonce=req.client_nonce)
    max_payout_x = engine.cfg.get("limits", {}).get("max_payout_x", 10)  # дефолт 10x
    payout = min(int(req.stake * result["r"]), int(req.stake * max_payout_x))

    credit_tx_id = None
    if payout > 0:
        cr = credit(user_id=user["sub"], amount=payout, description="spin_reward")
        credit_tx_id = cr.get("tx_id")

    # Сохраняем в БД; id генерирует Postgres автоматически
    from src.utils.db import get_db
    ins = get_db().table("spins").insert({
        "user_id": user["sub"],
        "game_id": req.game_id,
        "stake": req.stake,
        "bucket": result["bucket"],
        "payout": payout,
        "server_seed_hash": result["server_seed_hash"],
        "client_nonce": req.client_nonce,
        "k": str(result["k"]),
        "u": result["u"],
        "near_miss": result.get("near_miss", False),
        "idempotency_key": req.idempotency_key,
    }).execute()
    spin_id = ins.data[0]["id"] if ins.data else "unknown"

    # Перечитываем актуальный баланс после всех транзакций
    bal_after = get_balance(user["sub"])
    return {
        "ok": True,
        "data": {
            "spin_id": spin_id,
            "bucket": result["bucket"],
            "multiplier": result["r"],
            "payout": payout,
            "balance_after": bal_after,
            "provably_fair": {
                "server_seed_hash": result["server_seed_hash"],
                "client_nonce": req.client_nonce,
                "k": result["k"],
                "u": result["u"],
            },
            "visual": {
                "near_miss": result.get("near_miss", False),
                "confetti": payout > 0,
            },
        },
        "meta": {"request_id": uuid.uuid4().hex, "took_ms": 0},
    }


@router.get("/history")
async def history(user=Depends(get_current_user)):
    from src.utils.db import get_db
    resp = (
        get_db()
        .table("spins")
        .select("*")
        .eq("user_id", user["sub"])
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return {"ok": True, "data": resp.data}
