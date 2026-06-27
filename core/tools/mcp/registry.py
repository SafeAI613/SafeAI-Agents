"""MCP server registry + the process-wide manager.

`servers.yaml` (under infra/mcp-servers/) declares the available MCP servers. This module
loads it, builds the shared MCPManager, and exposes helpers the server endpoints and the
tool-calling agent use:

  * load_specs()                 -> all declared ServerSpec, with ${ENV} expanded
  * get_manager()                -> shared MCPManager (lazy singleton, broker-gated)
  * autoconnect()                -> connect every spec marked enabled: true
  * tools_as_openai_schema()     -> the connected tools, as OpenAI/OpenRouter tool defs

The broker is built from config/default.yaml: the domain allowlist gates http servers,
and an mcp.command_allowlist gates which local executables stdio servers may launch.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from core.security.permissions import PermissionBroker
from core.security.secrets import load_config
from core.tools.mcp.client import MCPManager, ServerSpec, ToolInfo

_SERVERS_YAML = Path(__file__).resolve().parents[3] / "infra" / "mcp-servers" / "servers.yaml"
_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand(value: Any) -> Any:
    """Recursively expand ${ENV_VAR} in strings (keys never hold secrets directly)."""
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, list):
        return [_expand(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    return value


def load_specs() -> list[ServerSpec]:
    if not _SERVERS_YAML.exists():
        return []
    raw = yaml.safe_load(_SERVERS_YAML.read_text(encoding="utf-8")) or {}
    specs: list[ServerSpec] = []
    for name, cfg in (raw.get("servers") or {}).items():
        cfg = _expand(cfg or {})
        specs.append(ServerSpec(
            name=name,
            transport=cfg.get("transport", "stdio"),
            command=cfg.get("command"),
            args=cfg.get("args", []) or [],
            env=cfg.get("env"),
            url=cfg.get("url"),
            headers=cfg.get("headers"),
            enabled=bool(cfg.get("enabled", True)),
        ))
    return specs


def _build_broker() -> PermissionBroker:
    cfg = load_config()
    sec = cfg.get("security", {}) or {}
    mcp_cfg = cfg.get("mcp", {}) or {}
    return PermissionBroker(
        domain_allowlist=sec.get("domain_allowlist", []) or [],
        allow_network=True,                       # MCP servers are explicitly declared
        command_allowlist=mcp_cfg.get("command_allowlist", []) or [],
    )


@lru_cache(maxsize=1)
def get_manager() -> MCPManager:
    return MCPManager(broker=_build_broker())


def autoconnect() -> dict[str, str]:
    """Connect every enabled server. Returns {server: 'ok' | 'error: ...'}."""
    mgr = get_manager()
    status: dict[str, str] = {}
    for spec in load_specs():
        if not spec.enabled:
            continue
        try:
            mgr.connect(spec)
            status[spec.name] = "ok"
        except Exception as exc:                  # one bad server must not block others
            status[spec.name] = f"error: {exc}"
    return status


def tools_as_openai_schema(server: str | None = None) -> list[dict]:
    """Connected MCP tools as OpenAI-style tool definitions (function calling)."""
    defs: list[dict] = []
    for t in get_manager().list_tools(server):
        defs.append({
            "type": "function",
            "function": {
                "name": t.qualified.replace(".", "__"),   # dots are illegal in tool names
                "description": t.description,
                "parameters": t.input_schema,
            },
        })
    return defs


def tool_id_from_openai_name(name: str) -> str:
    """Reverse of the name munging above: 'server__tool' -> 'server.tool'."""
    return name.replace("__", ".", 1)


def describe_tools(server: str | None = None) -> list[dict]:
    """Plain dicts for the UI (server, name, description, schema)."""
    out = []
    for t in get_manager().list_tools(server):
        out.append({
            "id": t.qualified,
            "server": t.server,
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
        })
    return out
