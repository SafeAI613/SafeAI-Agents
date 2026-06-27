"""MCP client layer.

client.py    — MCPManager (sync facade), ServerSpec, ToolInfo; stdio + streamable-http.
registry.py  — loads infra/mcp-servers/servers.yaml, shared manager, OpenAI tool schema.

All connections are gated by the permission broker (command allowlist for stdio, domain
allowlist for http). Tools are exposed to the model/UI namespaced as 'server.tool'.
"""

from core.tools.mcp.client import MCPManager, PermissionError_, ServerSpec, ToolInfo
from core.tools.mcp.registry import (
    autoconnect,
    describe_tools,
    get_manager,
    load_specs,
    tool_id_from_openai_name,
    tools_as_openai_schema,
)

__all__ = [
    "MCPManager", "ServerSpec", "ToolInfo", "PermissionError_",
    "autoconnect", "describe_tools", "get_manager", "load_specs",
    "tool_id_from_openai_name", "tools_as_openai_schema",
]
