"""Secrets & config access.

Secrets are read from the environment (or a .env file loaded at startup). Never hardcode
keys in source. Config (budgets, model, allowlists) is read from config/default.yaml.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]


def get_secret(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


@lru_cache(maxsize=1)
def load_config() -> dict:
    cfg_path = _ROOT / "config" / "default.yaml"
    if not cfg_path.exists():
        return {}
    with cfg_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}
