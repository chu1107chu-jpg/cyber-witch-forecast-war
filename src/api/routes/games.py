"""/api/v1/games — guess-sign, history"""
from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field
from typing import Literal, Optional
import uuid

router = APIRouter()


class GuessSignReq(BaseModel):
    ticker: str
    horizon: Literal["t+1", "t+20"]
    stake: int = Field(gt=0)
    choice: Literal["up", "down"]
    idempotency_key: str = Field(default_factory=lambda: str(uuid.uuid4()))


def get_current_user(authorization: str = Header(...)):
    from src.utils.auth import verify_jwt
    return verify_jwt(authorization.removeprefix("Bearer "))


@router.post("/guess-sign")
async def guess_sign(req: GuessSignReq, user=Depends(get_current_user)):
    """Сделать ставку на направление цены."""
    from src.wallet.credits import debit, credit
    from src.pipeline.predict import run_predict
    from datetime import date

    # списываем ставку
    d = debit(
        user_id=user["sub"],
        amount=req.stake,
        description="game_bet",
        idempotency_key=req.idempotency_key,
    )
    if not d["ok"]:
        from fastapi import HTTPException
        raise HTTPException(402, "Insufficient balance")

    # получаем прогноз как «real_sign» (упрощённо)
    preds = run_predict(date.today().isoformat(), [req.ticker])
    pred = preds[0] if preds else None
    real_sign = "up" if (pred and pred.r1 > 0) else "down"

    win = req.choice == real_sign
    payout = int(req.stake * 0.95) if win else 0
    if win:
        credit(user_id=user["sub"], amount=payout, description="game_win")

    # запись раунда
    from src.utils.db import get_db
    db = get_db()
    db.table("game_rounds").insert({
        "user_id": user["sub"],
        "game_type": "guess-sign",
        "input": req.model_dump(),
        "outcome": {"win": win, "payout": payout, "real_sign": real_sign},
    }).execute()

    bal = d["new_balance"] + (payout if win else 0)
    return {
        "result": {"win": win, "payout": payout, "real_sign": real_sign},
        "balance": bal,
    }


@router.get("/history")
async def history(
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user),
):
    from src.utils.db import get_db
    resp = (
        get_db()
        .table("game_rounds")
        .select("*")
        .eq("user_id", user["sub"])
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return {"items": resp.data}
