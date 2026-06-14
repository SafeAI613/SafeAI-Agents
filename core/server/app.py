"""FastAPI sidecar — the local API the desktop UI (Tauri) will attach to.

Endpoints:
    GET  /agents        -> list available agents
    POST /run           -> run an agent, return final state + trace
    WS   /ws/run        -> run an agent, stream node events live, then the result

The CLI is enough to validate the pipeline now; this server is the integration seam
for the UI step-inspector. Run it with:
    uvicorn core.server.app:app --reload
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from core.agents.registry import get_agent, list_agents
from core.runtime.orchestrator import run_agent

app = FastAPI(title="AI Agents Desktop — core")


class RunRequest(BaseModel):
    agent: str = "plumber"
    question: str
    mock: bool | None = None


@app.get("/agents")
def agents() -> dict[str, Any]:
    return {"agents": list_agents()}


@app.post("/run")
def run(req: RunRequest) -> dict[str, Any]:
    agent = get_agent(req.agent, mock=req.mock)
    final = run_agent(agent, req.question)
    return final


@app.websocket("/ws/run")
async def ws_run(ws: WebSocket) -> None:
    await ws.accept()
    try:
        req = await ws.receive_json()
        agent = get_agent(req.get("agent", "plumber"), mock=req.get("mock"))

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def on_event(ev: dict) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, ev)

        async def stream() -> None:
            while True:
                ev = await queue.get()
                await ws.send_json({"kind": "event", "data": ev})

        streamer = asyncio.create_task(stream())
        final = await asyncio.to_thread(run_agent, agent, req["question"],
                                        on_event=on_event)
        await asyncio.sleep(0.05)  # flush remaining events
        streamer.cancel()
        await ws.send_json({"kind": "result", "data": final})
    except WebSocketDisconnect:
        pass
    finally:
        await ws.close()
