"""Provably-Fair RNG для Spin-игры (HMAC-SHA256).

SpinEngine создаётся ОДИН РАЗ на game_id на уровне процесса (get_engine).
Это важно: _spin_counter хранит монотонный счётчик per-user и должен
жить между запросами. В multi-worker деплое нужен Redis-счётчик.
"""
import hashlib
import hmac
import os
from datetime import date
from typing import Optional

# Реестр движков: {game_id: SpinEngine}
_ENGINE_REGISTRY: dict[str, "SpinEngine"] = {}


def _build_cum(payouts: dict) -> list:
    result = []
    acc = 0.0
    for bucket, vals in payouts.items():
        acc += vals["p"]
        result.append((acc, bucket, vals["r"]))
    return result


def _day_key() -> bytes:
    salt = os.environ.get("SECRET_KEY", "default_salt").encode()
    return hashlib.sha256(salt + date.today().isoformat().encode()).digest()


def _hmac_bytes(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


def _to_u01(b: bytes) -> float:
    return int.from_bytes(b[:32], "big") / (1 << 256)


def get_engine(game_id: str = "utility_slot_v1") -> "SpinEngine":
    """Вернуть (или создать) синглтон SpinEngine для данного game_id.
    Сбрасывается автоматически при смене дня (_server_seed ротируется).
    """
    today = date.today().isoformat()
    key = f"{game_id}:{today}"
    if key not in _ENGINE_REGISTRY:
        # Чистим устаревшие ключи (другой день)
        stale = [k for k in _ENGINE_REGISTRY if not k.endswith(today)]
        for k in stale:
            del _ENGINE_REGISTRY[k]
        _ENGINE_REGISTRY[key] = SpinEngine(game_id)
    return _ENGINE_REGISTRY[key]


class SpinEngine:
    def __init__(self, game_id: str = "utility_slot_v1"):
        from src.utils.config import load_games_config
        games = load_games_config()
        self.game_id = game_id
        self.cfg = next((g for g in games if g["game_id"] == game_id), {})
        payouts = self.cfg.get("payouts", {
            "JACKPOT": {"p": 0.005, "r": 10.0},
            "BIG":     {"p": 0.015, "r": 5.0},
            "MEDIUM":  {"p": 0.03,  "r": 2.0},
            "SMALL":   {"p": 0.10,  "r": 1.0},
            "MINOR":   {"p": 0.20,  "r": 0.5},
            "BONUS":   {"p": 0.25,  "r": 0.2},
            "NONE":    {"p": 0.40,  "r": 0.0},
        })
        self._cum = _build_cum(payouts)
        self._server_seed = _hmac_bytes(_day_key(), game_id.encode())
        self._seed_hash = "sha256:" + hashlib.sha256(self._server_seed).hexdigest()
        self._spin_counter: dict[str, int] = {}

    def check_limits(self, user_id: str, stake: int):
        limits = self.cfg.get("limits", {})
        min_bet = limits.get("min_bet", 10)
        max_bet = limits.get("max_bet", 1000)
        if stake < min_bet:
            from fastapi import HTTPException
            raise HTTPException(422, f"Stake below min_bet={min_bet}")
        if stake > max_bet:
            from fastapi import HTTPException
            raise HTTPException(422, f"Stake above max_bet={max_bet}")
        # TODO: per-user cooldown via Redis/cache

    def draw(self, user_id: str, client_nonce: str) -> dict:
        k = self._spin_counter.get(user_id, 0)
        self._spin_counter[user_id] = k + 1

        data = f"{client_nonce}:{k}".encode()
        raw = _hmac_bytes(self._server_seed, data)
        u = _to_u01(raw)

        bucket = "NONE"
        r = 0.0
        near_miss = False
        for cum_p, b, rv in self._cum:
            if u <= cum_p:
                bucket = b
                r = rv
                break

        # near-miss: u очень близко к границе JACKPOT
        jackpot_boundary = self._cum[0][0]
        if abs(u - jackpot_boundary) < 0.002 and bucket != "JACKPOT":
            near_miss = True

        return {
            "bucket": bucket,
            "r": r,
            "u": round(u, 8),
            "k": k,
            "server_seed_hash": self._seed_hash,
            "near_miss": near_miss,
        }
