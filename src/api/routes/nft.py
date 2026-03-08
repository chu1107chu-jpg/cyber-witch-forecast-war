"""/api/v1/nft — list / mint-internal / upload / web3 stubs"""
from fastapi import APIRouter, Depends, Header, UploadFile, File, HTTPException
from pydantic import BaseModel
import uuid

router = APIRouter()


class MintInternalReq(BaseModel):
    nft_id: str


def get_current_user(authorization: str = Header(...)):
    from src.utils.auth import verify_jwt
    return verify_jwt(authorization.removeprefix("Bearer "))


@router.get("/list")
async def nft_list(user=Depends(get_current_user)):
    from src.utils.db import get_db
    resp = get_db().table("nft_items").select("*").eq("flagged", False).execute()
    return {"items": resp.data}


@router.post("/mint-internal")
async def mint_internal(req: MintInternalReq, user=Depends(get_current_user)):
    """Купить NFT за кредиты (off-chain)."""
    from src.utils.db import get_db
    from src.wallet.credits import debit

    db = get_db()
    item = db.table("nft_items").select("*").eq("nft_id", req.nft_id).single().execute()
    if not item.data:
        raise HTTPException(404, "NFT not found")
    if item.data["flagged"]:
        raise HTTPException(403, "NFT flagged")

    price = item.data["price_credits"]
    d = debit(user_id=user["sub"], amount=price, description="nft_buy",
              idempotency_key=f"nft_{req.nft_id}_{user['sub']}")
    if not d["ok"]:
        raise HTTPException(402, "Insufficient balance")

    db.table("nft_owners").insert({
        "nft_id": req.nft_id,
        "owner_id": user["sub"],
    }).execute()

    return {"ok": True, "nft_id": req.nft_id, "new_balance": d["new_balance"]}


@router.post("/upload")
async def upload_nft(
    file: UploadFile = File(...),
    x_admin_secret: str = Header(...),
):
    """Загрузить медиа для NFT. Проходит YOLO/OpenCV модерацию."""
    from src.utils.auth import check_admin
    check_admin(x_admin_secret)

    from src.vision.moderator import moderate_image
    content = await file.read()
    moderation = moderate_image(content)
    if moderation["flagged"]:
        raise HTTPException(422, f"Image flagged: {moderation['reason']}")

    from src.storage.r2 import upload_bytes
    key = f"nft/{uuid.uuid4().hex}/{file.filename}"
    url = upload_bytes(key, content, content_type=file.content_type)
    return {"ok": True, "media_url": url, "moderation": moderation}


# ── Web3 stubs ────────────────────────────────────────────────

@router.post("/mint-ton")
async def mint_ton(_user=Depends(get_current_user)):
    raise HTTPException(501, detail={
        "message": "TON minting not yet enabled (WEB3_ENABLE=false)",
        "expected_payload": {
            "nft_id": "uuid",
            "recipient_wallet": "UQ...",
            "collection_address": "EQ...",
            "meta_uri": "https://...",
        }
    })


@router.post("/mint-solana")
async def mint_solana(_user=Depends(get_current_user)):
    raise HTTPException(501, detail={
        "message": "Solana minting not yet enabled (WEB3_ENABLE=false)",
        "expected_payload": {
            "nft_id": "uuid",
            "recipient_wallet": "...",
            "metadata_uri": "https://...",
        }
    })
