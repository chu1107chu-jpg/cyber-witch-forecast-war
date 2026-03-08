"""Внутренние кредиты (utility-tokens): debit / credit / balance.

  Схема wallet_tx: id (auto), user_id, type ('credit'|'debit'),
                   amount (всегда > 0), description, idempotency_key.
  Схема wallets:   id (auto), user_id, balance (>= 0, CHECK на уровне БД).
"""
import logging
import uuid

logger = logging.getLogger(__name__)


def _db():
    from src.utils.db import get_db
    return get_db()


def get_balance(user_id: str) -> int:
    resp = _db().table("wallets").select("balance").eq("user_id", user_id).maybe_single().execute()
    if resp.data:
        return resp.data["balance"]
    # Кошелёк не найден — создаём с нулевым балансом
    _db().table("wallets").insert({"user_id": user_id, "balance": 0}).execute()
    return 0


def debit(user_id: str, amount: int, description: str,
          idempotency_key: str | None = None) -> dict:
    """Списать amount кредитов. Атомарность через CHECK balance>=0 в БД."""
    if not idempotency_key:
        idempotency_key = str(uuid.uuid4())

    # Idempotency: если уже выполнялось — вернуть прежний результат
    existing = (
        _db().table("wallet_tx")
        .select("id, amount")
        .eq("idempotency_key", idempotency_key)
        .execute()
    )
    if existing.data:
        balance = get_balance(user_id)
        return {"ok": True, "new_balance": balance, "tx_id": existing.data[0]["id"]}

    # Атомарное списание: обновляем только если balance >= amount
    # (CHECK constraint ловит нарушение на уровне БД)
    balance = get_balance(user_id)
    if balance < amount:
        return {"ok": False, "error": "Insufficient balance", "new_balance": balance}

    upd = (
        _db().table("wallets")
        .update({"balance": balance - amount})
        .eq("user_id", user_id)
        .gte("balance", amount)   # guard: списываем только если хватает
        .execute()
    )
    if not upd.data:
        # Другой запрос уже списал — перечитываем
        return {"ok": False, "error": "Insufficient balance",
                "new_balance": get_balance(user_id)}

    new_balance = upd.data[0]["balance"]
    tx = _db().table("wallet_tx").insert({
        "user_id": user_id,
        "type": "debit",
        "amount": amount,          # всегда положительное
        "description": description,
        "idempotency_key": idempotency_key,
    }).execute()

    tx_id = tx.data[0]["id"] if tx.data else str(uuid.uuid4())
    logger.info("DEBIT user=%s amount=%d desc=%s balance=%d",
                user_id, amount, description, new_balance)
    return {"ok": True, "new_balance": new_balance, "tx_id": tx_id}


def credit(user_id: str, amount: int, description: str,
           idempotency_key: str | None = None) -> dict:
    """Начислить amount кредитов."""
    if not idempotency_key:
        idempotency_key = str(uuid.uuid4())

    existing = (
        _db().table("wallet_tx")
        .select("id")
        .eq("idempotency_key", idempotency_key)
        .execute()
    )
    if existing.data:
        balance = get_balance(user_id)
        return {"ok": True, "new_balance": balance, "tx_id": existing.data[0]["id"]}

    upd = (
        _db().table("wallets")
        .upsert({"user_id": user_id, "balance": get_balance(user_id) + amount},
                on_conflict="user_id")
        .execute()
    )
    new_balance = upd.data[0]["balance"] if upd.data else get_balance(user_id)

    tx = _db().table("wallet_tx").insert({
        "user_id": user_id,
        "type": "credit",
        "amount": amount,
        "description": description,
        "idempotency_key": idempotency_key,
    }).execute()

    tx_id = tx.data[0]["id"] if tx.data else str(uuid.uuid4())
    logger.info("CREDIT user=%s amount=%d desc=%s balance=%d",
                user_id, amount, description, new_balance)
    return {"ok": True, "new_balance": new_balance, "tx_id": tx_id}
