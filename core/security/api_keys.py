"""Per-request API key management via ContextVar + OS keychain.

Precedence: request key → stored keychain key → OPENROUTER_API_KEY env var.
The key never enters AgentState or logs.
"""

from __future__ import annotations

import os
from contextvars import ContextVar

_request_key: ContextVar[str | None] = ContextVar("openrouter_api_key", default=None)

_SERVICE = "ai-agents-desktop"


def set_request_key(key: str | None) -> None:
    _request_key.set(key)


def get_stored_key() -> str | None:
    try:
        import keyring
        return keyring.get_password(_SERVICE, "openrouter")
    except Exception:
        return None


def store_key(key: str) -> None:
    import keyring
    keyring.set_password(_SERVICE, "openrouter", key)


def clear_key() -> None:
    try:
        import keyring
        keyring.delete_password(_SERVICE, "openrouter")
    except Exception:
        pass


def resolve_openrouter_key() -> str | None:
    return _request_key.get() or get_stored_key() or os.environ.get("OPENROUTER_API_KEY")
