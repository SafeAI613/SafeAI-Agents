"""MCP client layer — connect to MCP servers, list and call their tools.

Implemented against the official `mcp` Python SDK (>=1.8). Two transports:
  * stdio            — launches a local server process, talks newline-delimited JSON
  * streamable-http  — talks to a remote/local server over one HTTP endpoint

The SDK is async; the rest of the runtime (nodes, FastAPI /run) is sync and runs each
agent in a worker thread. To bridge that cleanly we keep ONE background event loop in a
dedicated thread. Connections (subprocesses / HTTP sessions) are opened once there and
stay alive, so repeated tool calls don't re-spawn servers. Sync callers submit coroutines
with `run_coroutine_threadsafe(...).result()`.

Every connection is authorized through the permission broker first (stdio command must be
on the allowlist; http url host must be on the domain allowlist). Nothing connects silently.
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from core.security.permissions import PermissionBroker, PermissionError_


@dataclass
class ServerSpec:
    """One MCP server, as declared in servers.yaml."""
    name: str
    transport: str                      # "stdio" | "streamable-http"
    command: str | None = None          # stdio: executable
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    url: str | None = None              # http: endpoint, e.g. http://localhost:8765/mcp
    headers: dict[str, str] | None = None
    enabled: bool = True


@dataclass
class ToolInfo:
    server: str
    name: str                           # bare tool name on its server
    description: str
    input_schema: dict[str, Any]

    @property
    def qualified(self) -> str:
        """Namespaced id exposed to the model / UI: 'server.tool'."""
        return f"{self.server}.{self.name}"


class _Connection:
    """Holds a live ClientSession plus the AsyncExitStack that owns its transport."""

    def __init__(self, spec: ServerSpec):
        self.spec = spec
        self.session: ClientSession | None = None
        self._stack = AsyncExitStack()
        self.tools: list[ToolInfo] = []

    async def open(self) -> None:
        if self.spec.transport == "stdio":
            params = StdioServerParameters(
                command=self.spec.command or "",
                args=self.spec.args,
                env=self.spec.env,
            )
            read, write = await self._stack.enter_async_context(stdio_client(params))
        elif self.spec.transport in ("streamable-http", "http"):
            ctx = streamablehttp_client(self.spec.url or "", headers=self.spec.headers)
            read, write, _ = await self._stack.enter_async_context(ctx)
        else:
            raise ValueError(f"unknown transport '{self.spec.transport}'")

        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        await self._refresh_tools()

    async def _refresh_tools(self) -> None:
        assert self.session is not None
        listed = await self.session.list_tools()
        self.tools = [
            ToolInfo(
                server=self.spec.name,
                name=t.name,
                description=t.description or "",
                input_schema=t.inputSchema or {"type": "object", "properties": {}},
            )
            for t in listed.tools
        ]

    async def call(self, tool: str, arguments: dict[str, Any]) -> str:
        assert self.session is not None
        result = await self.session.call_tool(tool, arguments=arguments)
        # Flatten content blocks into text; non-text blocks are summarized.
        parts: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            parts.append(text if text is not None else f"[{getattr(block, 'type', 'content')}]")
        out = "\n".join(parts).strip()
        if getattr(result, "isError", False):
            return f"[tool error] {out}"
        return out

    async def close(self) -> None:
        await self._stack.aclose()
        self.session = None


class MCPManager:
    """Sync facade over a background asyncio loop holding all MCP connections."""

    def __init__(self, broker: PermissionBroker | None = None):
        self._broker = broker
        self._conns: dict[str, _Connection] = {}
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True,
                                        name="mcp-loop")
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    # --- authorization ----------------------------------------------------
    def _authorize(self, spec: ServerSpec) -> None:
        if self._broker is None:
            return
        if spec.transport == "stdio":
            self._broker.authorize_mcp_command(spec.command or "")
        else:
            self._broker.authorize_url(spec.url or "")

    # --- public sync API --------------------------------------------------
    def connect(self, spec: ServerSpec) -> list[ToolInfo]:
        """Connect (or reconnect) one server and return its tools."""
        self._authorize(spec)
        if spec.name in self._conns:
            self.disconnect(spec.name)
        conn = _Connection(spec)
        self._submit(conn.open())
        self._conns[spec.name] = conn
        return conn.tools

    def disconnect(self, name: str) -> None:
        conn = self._conns.pop(name, None)
        if conn is not None:
            try:
                self._submit(conn.close())
            except Exception:
                pass

    def connected_servers(self) -> list[str]:
        return sorted(self._conns)

    def list_tools(self, server: str | None = None) -> list[ToolInfo]:
        tools: list[ToolInfo] = []
        for name, conn in self._conns.items():
            if server and name != server:
                continue
            tools.extend(conn.tools)
        return tools

    def call_tool(self, qualified: str, arguments: dict[str, Any]) -> str:
        """Call a tool by its 'server.tool' id."""
        if "." not in qualified:
            raise ValueError(f"tool id must be 'server.tool', got '{qualified}'")
        server, tool = qualified.split(".", 1)
        conn = self._conns.get(server)
        if conn is None:
            raise PermissionError_(f"MCP server '{server}' is not connected")
        return self._submit(conn.call(tool, arguments))

    def shutdown(self) -> None:
        for name in list(self._conns):
            self.disconnect(name)
        self._loop.call_soon_threadsafe(self._loop.stop)
