"""FastAPI sidecar — the local API the desktop UI (Tauri) will attach to.

Endpoints:
    POST /auth/register  -> register new user, returns JWT
    POST /auth/login     -> login, returns JWT
    GET  /agents         -> list available agents  [requires JWT]
    POST /run            -> run an agent            [requires JWT]
    WS   /ws/run         -> stream node events      [requires JWT via ?token=]
"""

from __future__ import annotations

import asyncio
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel

from core.agents.registry import get_agent, list_agents
from core.auth.models import TokenResponse, UserLogin, UserRegister
from core.auth.service import decode_token, login_user, record_usage, register_user
from core.runtime.orchestrator import run_agent
from core.security.api_keys import clear_key, get_stored_key, store_key

app = FastAPI(title="AI Agents Desktop — core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:1420", "tauri://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_bearer = HTTPBearer()


def current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    """FastAPI dependency — validates JWT and returns email."""
    try:
        return decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="טוקן לא תקין או פג תוקף")


# ── auth endpoints (public) ───────────────────────────────────────────────────

@app.post("/auth/register", response_model=TokenResponse)
def auth_register(body: UserRegister) -> TokenResponse:
    try:
        token = register_user(body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return TokenResponse(access_token=token, email=body.email.lower())


@app.post("/auth/login", response_model=TokenResponse)
def auth_login(body: UserLogin, request: Request) -> TokenResponse:
    ip = request.client.host if request.client else None
    try:
        token = login_user(body.email, body.password, ip=ip)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return TokenResponse(access_token=token, email=body.email.lower())


# ── protected endpoints ───────────────────────────────────────────────────────

class RunRequest(BaseModel):
    agent: str = "plumber"
    question: str
    mock: bool | None = None


class KeyRequest(BaseModel):
    key: str


@app.post("/auth/key")
def set_api_key(body: KeyRequest, email: str = Depends(current_user)) -> dict[str, str]:
    """Store the user's OpenRouter key in the OS keychain. Key never logged."""
    if not body.key.startswith("sk-"):
        raise HTTPException(status_code=422, detail="מפתח לא תקין")
    store_key(body.key)
    stored = get_stored_key() or ""
    masked = f"...{stored[-4:]}" if len(stored) >= 4 else "מוגדר"
    return {"status": "ok", "masked": masked}


@app.get("/auth/key")
def key_status(email: str = Depends(current_user)) -> dict[str, Any]:
    """Returns whether a key is stored and its last 4 chars. Never returns the full key."""
    stored = get_stored_key()
    if stored:
        return {"set": True, "masked": f"...{stored[-4:]}"}
    return {"set": False, "masked": None}


@app.delete("/auth/key")
def delete_api_key(email: str = Depends(current_user)) -> dict[str, str]:
    clear_key()
    return {"status": "ok"}


@app.get("/agents")
def agents(email: str = Depends(current_user)) -> dict[str, Any]:
    return {"agents": list_agents()}


@app.post("/run")
def run(req: RunRequest, email: str = Depends(current_user)) -> dict[str, Any]:
    agent = get_agent(req.agent, mock=req.mock)
    final = run_agent(agent, req.question)
    record_usage(email, req.agent)
    return final


@app.websocket("/ws/run")
async def ws_run(ws: WebSocket, token: str = Query(...)) -> None:
    # WebSocket doesn't support Authorization header — token passed as query param
    try:
        email = decode_token(token)
    except JWTError:
        await ws.close(code=4001)
        return

    await ws.accept()
    try:
        req = await ws.receive_json()
        agent = get_agent(req.get("agent", "plumber"), mock=req.get("mock"))

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def on_event(ev: dict) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, {"kind": "event", "data": ev})

        def on_token(chunk: str) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, {"kind": "token", "data": chunk})

        async def stream() -> None:
            while True:
                msg = await queue.get()
                await ws.send_json(msg)

        streamer = asyncio.create_task(stream())
        final = await asyncio.to_thread(run_agent, agent, req["question"],
                                        on_event=on_event, on_token=on_token)
        record_usage(email, req.get("agent", "plumber"))
        await asyncio.sleep(0.05)
        streamer.cancel()
        await ws.send_json({"kind": "result", "data": final})
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await ws.send_json({"kind": "error", "data": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass
