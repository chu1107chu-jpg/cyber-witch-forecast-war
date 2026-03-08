"""/api/v1/admin — game config, risk summary, RTP preview"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Any, Dict

router = APIRouter()


def require_admin(x_admin_secret: str = Header(...)):
    from src.utils.auth import check_admin
    check_admin(x_admin_secret)


class DistributionSetReq(BaseModel):
    game_id: str
    distribution: Dict[str, Any]   # JACKPOT/BIG/… → {p, r}


@router.post("/game/distribution/set")
async def set_distribution(req: DistributionSetReq, _=Header(..., alias="x-admin-secret")):
    """Обновить вероятности/выплаты игры. Отклоняет если RTP > 0.45."""
    require_admin(_)
    # validation
    rtp = sum(v["p"] * v["r"] for v in req.distribution.values())
    if rtp > 0.45:
        raise HTTPException(422, f"Theoretical RTP {rtp:.4f} > 0.45 — конфиг не сохранён")
    # TODO: persist to game_distributions table
    return {"ok": True, "game_id": req.game_id, "theoretical_rtp": round(rtp, 4)}


@router.get("/rtp/preview")
async def rtp_preview(game_id: str, _=Header(..., alias="x-admin-secret")):
    """Превью RTP по текущему конфигу + rolling-фактический RTP."""
    require_admin(_)
    from src.utils.config import load_games_config
    cfg = next((g for g in load_games_config() if g["game_id"] == game_id), None)
    if not cfg:
        raise HTTPException(404, "game not found")
    payouts = cfg.get("payouts", {})
    theoretical_rtp = sum(v["p"] * v["r"] for v in payouts.values())
    # rolling actual RTP from DB
    from src.utils.db import get_db
    resp = (
        get_db()
        .table("spins")
        .select("stake, payout")
        .eq("game_id", game_id)
        .order("created_at", desc=True)
        .limit(cfg.get("rtp", {}).get("rolling_window", 1000))
        .execute()
    )
    rows = resp.data or []
    if rows:
        total_stake = sum(r["stake"] for r in rows)
        total_payout = sum(r["payout"] for r in rows)
        actual_rtp = total_payout / total_stake if total_stake else 0.0
    else:
        actual_rtp = None

    return {
        "game_id": game_id,
        "theoretical_rtp": round(theoretical_rtp, 4),
        "actual_rtp_rolling": round(actual_rtp, 4) if actual_rtp is not None else None,
        "sample_size": len(rows),
        "rtp_ok": theoretical_rtp <= 0.45,
    }


@router.get("/risk/summary")
async def risk_summary(_=Header(..., alias="x-admin-secret")):
    """Сводка по дневным лимитам, payouts, аномалиям."""
    require_admin(_)
    from src.utils.db import get_db
    from datetime import date
    today = date.today().isoformat()

    spins_today = (
        get_db()
        .table("spins")
        .select("user_id, stake, payout, bucket")
        .gte("created_at", today)
        .execute()
    ).data or []

    total_stake = sum(r["stake"] for r in spins_today)
    total_payout = sum(r["payout"] for r in spins_today)
    jackpot_count = sum(1 for r in spins_today if r["bucket"] == "JACKPOT")

    return {
        "date": today,
        "spin_count": len(spins_today),
        "total_stake": total_stake,
        "total_payout": total_payout,
        "house_take": total_stake - total_payout,
        "actual_rtp": round(total_payout / total_stake, 4) if total_stake else None,
        "jackpot_count": jackpot_count,
        "alert_jackpot_anomaly": jackpot_count > max(3, len(spins_today) * 0.02),
    }
