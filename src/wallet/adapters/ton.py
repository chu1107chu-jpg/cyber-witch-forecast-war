"""TON адаптер: заглушка. Раскомментировать при WEB3_ENABLE=true."""


def prepare_mint(meta: dict) -> dict:
    """Создать payload для TON-транзакции минтинга NFT."""
    return {
        "chain": "TON",
        "collection_address": meta.get("collection_address", ""),
        "recipient_wallet": meta.get("recipient_wallet", ""),
        "meta_uri": meta.get("meta_uri", ""),
        "deeplink": f"ton://transfer/{meta.get('collection_address', '')}",
        "note": "WEB3_ENABLE=false — activate in .env to use real TON RPC",
    }
