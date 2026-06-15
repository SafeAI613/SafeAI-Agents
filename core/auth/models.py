from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str


class LoginEvent(BaseModel):
    timestamp: datetime
    ip: str | None = None


class UsageRecord(BaseModel):
    timestamp: datetime
    agent: str
    questions_count: int = 1
