"""FastAPI sidecar — the local API the desktop UI (Tauri) attaches to.

Auth + agents (existing):
    POST /auth/register | /auth/login        -> JWT
    GET/POST/DELETE /auth/key                 -> OpenRouter key in OS keychain
    GET  /agents                              -> list agents
    POST /run                                 -> run an agent (returns final state)
    WS   /ws/run                              -> stream node + tool-call events

Tools surface for the desktop UI (new):
    GET  /mcp/servers     POST /mcp/connect   -> connect/disconnect MCP servers
    GET  /mcp/tools       POST /mcp/call      -> list / invoke MCP tools
    POST /code/run                            -> run code in the sandbox
    GET  /files  /files/read   POST /files/write  /files/upload  -> workspace file ops
    POST /stt                                 -> transcribe uploaded audio
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import (Depends, FastAPI, File, Form, HTTPException, Query, Request,
                     UploadFile, WebSocket, WebSocketDisconnect)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from pydantic import BaseModel

from core.agents.registry import get_agent, list_agents
from core.auth.models import TokenResponse, UserLogin, UserRegister
from core.auth.service import decode_token, login_user, record_usage, register_user
from core.runtime.orchestrator import run_agent
from core.security.api_keys import clear_key, get_stored_key, store_key
from core.security.secrets import load_config

app = FastAPI(title="AI Agents Desktop — core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:1420", "tauri://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_bearer = HTTPBearer()


def current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> str:
    try:
        return decode_token(creds.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="טוקן לא תקין או פג תוקף")


# ── auth (public) ─────────────────────────────────────────────────────────────

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


# ── api key ───────────────────────────────────────────────────────────────────

class KeyRequest(BaseModel):
    key: str


@app.post("/auth/key")
def set_api_key(body: KeyRequest, email: str = Depends(current_user)) -> dict[str, str]:
    if not body.key.startswith("sk-"):
        raise HTTPException(status_code=422, detail="מפתח לא תקין")
    store_key(body.key)
    stored = get_stored_key() or ""
    masked = f"...{stored[-4:]}" if len(stored) >= 4 else "מוגדר"
    return {"status": "ok", "masked": masked}


@app.get("/auth/key")
def key_status(email: str = Depends(current_user)) -> dict[str, Any]:
    stored = get_stored_key()
    if stored:
        return {"set": True, "masked": f"...{stored[-4:]}"}
    return {"set": False, "masked": None}


@app.delete("/auth/key")
def delete_api_key(email: str = Depends(current_user)) -> dict[str, str]:
    clear_key()
    return {"status": "ok"}


# ── agents / run ──────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    agent: str = "plumber"
    question: str
    mock: bool | None = None


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


# ── MCP ───────────────────────────────────────────────────────────────────────

class McpConnectRequest(BaseModel):
    name: str
    action: str = "connect"      # "connect" | "disconnect"


class McpCallRequest(BaseModel):
    tool: str                    # "server.tool"
    arguments: dict[str, Any] = {}


@app.get("/mcp/servers")
def mcp_servers(email: str = Depends(current_user)) -> dict[str, Any]:
    from core.tools.mcp import get_manager, load_specs
    mgr = get_manager()
    connected = set(mgr.connected_servers())
    specs = [{
        "name": s.name, "transport": s.transport, "enabled": s.enabled,
        "connected": s.name in connected,
    } for s in load_specs()]
    return {"servers": specs}


@app.post("/mcp/connect")
def mcp_connect(req: McpConnectRequest, email: str = Depends(current_user)) -> dict[str, Any]:
    from core.tools.mcp import get_manager, load_specs
    mgr = get_manager()
    if req.action == "disconnect":
        mgr.disconnect(req.name)
        return {"status": "disconnected", "name": req.name}
    spec = next((s for s in load_specs() if s.name == req.name), None)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"שרת MCP '{req.name}' לא מוגדר")
    try:
        tools = mgr.connect(spec)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "connected", "name": req.name, "tool_count": len(tools)}


@app.get("/mcp/tools")
def mcp_tools(server: str | None = None, email: str = Depends(current_user)) -> dict[str, Any]:
    from core.tools.mcp import describe_tools
    return {"tools": describe_tools(server)}


@app.post("/mcp/call")
def mcp_call(req: McpCallRequest, email: str = Depends(current_user)) -> dict[str, Any]:
    from core.tools.mcp import get_manager
    try:
        result = get_manager().call_tool(req.tool, req.arguments)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"tool": req.tool, "result": result}


# ── code execution ────────────────────────────────────────────────────────────

class CodeRunRequest(BaseModel):
    code: str
    language: str = "python"
    stdin: str = ""


@app.post("/code/run")
def code_run(req: CodeRunRequest, email: str = Depends(current_user)) -> dict[str, Any]:
    from core.tools.code_exec import run_code
    from core.security.permissions import PermissionError_
    try:
        res = run_code(req.code, language=req.language, stdin=req.stdin)
    except PermissionError_ as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "ok": res.ok, "stdout": res.stdout, "stderr": res.stderr,
        "exit_code": res.exit_code, "timed_out": res.timed_out, "backend": res.backend,
    }


# ── files (scoped to a workspace root) ────────────────────────────────────────

def _workspace() -> Path:
    raw = (load_config().get("files", {}) or {}).get("workspace", "~/ai-agents-workspace")
    root = Path(os.path.expanduser(raw)).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe(rel: str) -> Path:
    root = _workspace()
    target = (root / rel.lstrip("/\\")).resolve() if rel else root
    if target != root and root not in target.parents:
        raise HTTPException(status_code=403, detail="נתיב מחוץ לסביבת העבודה")
    return target


class FileWriteRequest(BaseModel):
    path: str
    content: str


@app.get("/files")
def files_list(path: str = "", email: str = Depends(current_user)) -> dict[str, Any]:
    target = _safe(path)
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="תיקייה לא נמצאה")
    items = []
    for p in sorted(target.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        items.append({
            "name": p.name,
            "path": str(p.relative_to(_workspace())),
            "is_dir": p.is_dir(),
            "size": p.stat().st_size if p.is_file() else None,
        })
    return {"path": path, "items": items}


@app.get("/files/read")
def files_read(path: str = Query(...), email: str = Depends(current_user)) -> dict[str, Any]:
    target = _safe(path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="קובץ לא נמצא")
    if target.stat().st_size > 1_000_000:
        raise HTTPException(status_code=413, detail="הקובץ גדול מדי לתצוגה (>1MB)")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail="קובץ בינארי — לא ניתן להציג כטקסט")
    return {"path": path, "content": content}


@app.post("/files/write")
def files_write(req: FileWriteRequest, email: str = Depends(current_user)) -> dict[str, str]:
    target = _safe(req.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(req.content, encoding="utf-8")
    return {"status": "ok", "path": req.path}


@app.post("/files/upload")
async def files_upload(file: UploadFile = File(...), path: str = Form(""),
                       email: str = Depends(current_user)) -> dict[str, Any]:
    dest_dir = _safe(path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = _safe(str(Path(path) / (file.filename or "upload.bin")))
    dest.write_bytes(await file.read())
    return {"status": "ok", "path": str(dest.relative_to(_workspace())),
            "size": dest.stat().st_size}


# ── speech-to-text ────────────────────────────────────────────────────────────

@app.post("/stt")
async def stt(file: UploadFile = File(...),
              email: str = Depends(current_user)) -> dict[str, Any]:
    from core.tools.stt import transcribe
    data = await file.read()
    try:
        result = transcribe(data, filename=file.filename or "audio.webm")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"text": result.text, "language": result.language, "backend": result.backend}
