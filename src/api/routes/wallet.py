"""/api/v1/wallet — balance / spend / charge"""
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import uuid

router = APIRouter()


class SpendReq(BaseModel):
    amount: int = Field(gt=0)
    reason: str
    idempotency_key: str = Field(default_factory=lambda: str(uuid.uuid4()))


class ChargeReq(BaseModel):
    user_id: str
    amount: int = Field(gt=0)
    reason: str = "admin_grant"


class BalanceResp(BaseModel):
    balance: int


class TxResp(BaseModel):
    ok: bool
    new_balance: int
    tx_id: str


def get_current_user(authorization: str = Header(...)):
    """Простой JWT-парсер → user_id. TODO: заменить на полноценный."""
    from src.utils.auth import verify_jwt
    return verify_jwt(authorization.removeprefix("Bearer "))


@router.get("/balance", response_model=BalanceResp)
async def balance(user=Depends(get_current_user)):
    from src.wallet.credits import get_balance
    b = get_balance(user["sub"])
    return BalanceResp(balance=b)


@router.post("/spend", response_model=TxResp)
async def spend(req: SpendReq, user=Depends(get_current_user)):
    from src.wallet.credits import debit
    result = debit(
        user_id=user["sub"],
        amount=req.amount,
        description=req.reason,
        idempotency_key=req.idempotency_key,
    )
    if not result["ok"]:
        raise HTTPException(status_code=402, detail=result.get("error", "Insufficient balance"))
    return TxResp(**result)


@router.post("/charge")
async def charge(req: ChargeReq, x_admin_secret: str = Header(...)):
    from src.utils.auth import check_admin
    check_admin(x_admin_secret)
    from src.wallet.credits import credit
    result = credit(user_id=req.user_id, amount=req.amount, description=req.reason)
    return result
