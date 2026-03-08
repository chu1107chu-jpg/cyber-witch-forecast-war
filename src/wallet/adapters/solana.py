"""Solana адаптер: заглушка. Раскомментировать при WEB3_ENABLE=true."""


def prepare_mint(meta: dict) -> dict:
    """Создать payload для Solana-транзакции минтинга NFT."""
    return {
        "chain": "Solana",
        "recipient_wallet": meta.get("recipient_wallet", ""),
        "metadata_uri": meta.get("metadata_uri", ""),
        "note": "WEB3_ENABLE=false — activate in .env to use real Solana RPC",
    }
