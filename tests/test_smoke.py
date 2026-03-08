"""Basic smoke tests — run with: pytest tests/ -v"""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_config_loaders():
    from src.utils.config import get_app_config, get_games_config, get_model_config
    cfg = get_app_config()
    assert "app" in cfg or isinstance(cfg, dict)


def test_rng_spin_engine():
    from src.utils.rng import SpinEngine
    engine = SpinEngine()
    result = engine.draw(user_id="test-user", client_nonce="abc123")
    assert "bucket" in result
    assert "u" in result
    assert 0.0 <= result["u"] < 1.0


def test_rng_determinism():
    from src.utils.rng import SpinEngine
    engine = SpinEngine()
    r1 = engine.draw("user1", "nonce1")
    r2 = engine.draw("user1", "nonce1")
    # Same seed => same result on same day
    assert r1["u"] == r2["u"]


def test_logging():
    from src.utils.logging import get_logger
    log = get_logger("test")
    log.info("test log ok")


def test_credits_module_importable():
    import src.wallet.credits  # noqa: F401


def test_r2_module_importable():
    import src.storage.r2  # noqa: F401


def test_ton_stub():
    from src.wallet.adapters.ton import prepare_mint
    payload = prepare_mint({"name": "test", "description": "x", "image_url": "http://x"})
    assert payload["chain"] == "ton"


def test_solana_stub():
    from src.wallet.adapters.solana import prepare_mint
    payload = prepare_mint({"name": "test", "description": "x", "image_url": "http://x"})
    assert payload["chain"] == "solana"
