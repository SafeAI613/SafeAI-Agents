from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from pymongo.errors import DuplicateKeyError

from core.auth.mongo import users_collection

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

_JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
_JWT_ALGO = "HS256"
_JWT_EXPIRE_HOURS = 24 * 7  # 1 week


# ── password helpers ─────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


# ── JWT ──────────────────────────────────────────────────────────────────────

def create_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=_JWT_EXPIRE_HOURS)
    return jwt.encode({"sub": email, "exp": expire}, _JWT_SECRET, algorithm=_JWT_ALGO)


def decode_token(token: str) -> str:
    """Returns email from token, raises JWTError if invalid/expired."""
    payload = jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGO])
    email: str = payload.get("sub")
    if not email:
        raise JWTError("missing sub")
    return email


# ── register / login ─────────────────────────────────────────────────────────

def register_user(email: str, password: str) -> str:
    """Creates user, returns JWT token. Raises ValueError if email exists."""
    col = users_collection()
    doc = {
        "email": email.lower(),
        "password_hash": hash_password(password),
        "created_at": datetime.now(timezone.utc),
        "logins": [],
        "usage": [],
    }
    try:
        col.insert_one(doc)
    except DuplicateKeyError:
        raise ValueError("כתובת האימייל כבר רשומה במערכת")
    return create_token(email.lower())


def login_user(email: str, password: str, ip: str | None = None) -> str:
    """Verifies credentials, records login event, returns JWT token."""
    col = users_collection()
    user = col.find_one({"email": email.lower()})
    if not user or not verify_password(password, user["password_hash"]):
        raise ValueError("אימייל או סיסמה שגויים")

    col.update_one(
        {"email": email.lower()},
        {"$push": {"logins": {"timestamp": datetime.now(timezone.utc), "ip": ip}}},
    )
    return create_token(email.lower())


def record_usage(email: str, agent: str) -> None:
    """Increments question counter for (user, agent) in current session bucket."""
    col = users_collection()
    now = datetime.now(timezone.utc)
    col.update_one(
        {"email": email.lower()},
        {"$push": {"usage": {"timestamp": now, "agent": agent}}},
    )
