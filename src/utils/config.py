"""Загрузка YAML-конфигов из configs/."""
import os
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parents[3] / "configs"


@lru_cache(maxsize=None)
def load_app_config() -> dict:
    return _load("app.yaml")


@lru_cache(maxsize=None)
def load_news_config() -> dict:
    return _load("news.yaml")


@lru_cache(maxsize=None)
def load_model_config() -> dict:
    return _load("model.yaml")


def load_games_config() -> list[dict]:
    """Загружает multi-document YAML (slot + snake)."""
    path = CONFIG_DIR / "games.yaml"
    with open(path, "r", encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    return [d for d in docs if d]


def _load(filename: str) -> dict:
    path = CONFIG_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
