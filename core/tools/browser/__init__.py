"""Browser automation — NOT YET IMPLEMENTED.

Per the architecture, browser control is exposed as a Playwright MCP server (see
infra/mcp-servers/playwright/) and consumed through core/tools/mcp/client.py, gated by
the permission broker's domain allowlist. Default strategy: DOM / accessibility-tree
driven (no vision model). Needed by the "AI news reviewer" agent.
"""
