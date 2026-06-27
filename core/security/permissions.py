"""Permission broker.

Every sensitive action (network, filesystem, launching an MCP server process, executing
generated code) must be authorized here against the agent's / config's declared policy
before it runs. This is the single choke point for:
  * the domain allowlist          (http MCP servers, web tool)
  * the MCP stdio command allowlist (which local executables may be launched)
  * the filesystem allowlist        (which roots file tools may touch)
  * the code-execution switch       (Docker sandbox vs. blocked vs. host-subprocess)

Backward compatible with the original broker (authorize_url / authorize_fs unchanged).
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse


class PermissionError_(Exception):
    pass


class PermissionBroker:
    def __init__(self, *, domain_allowlist: list[str] | None = None,
                 allow_network: bool = False, allow_fs: bool = False,
                 command_allowlist: list[str] | None = None,
                 fs_roots: list[str] | None = None,
                 allow_code_exec: bool = False):
        self.domain_allowlist = set(domain_allowlist or [])
        self.allow_network = allow_network
        self.allow_fs = allow_fs
        self.command_allowlist = set(command_allowlist or [])
        self.fs_roots = [Path(p).resolve() for p in (fs_roots or [])]
        self.allow_code_exec = allow_code_exec

    # --- network ----------------------------------------------------------
    def authorize_url(self, url: str) -> None:
        if not self.allow_network:
            raise PermissionError_("network access not permitted for this agent")
        host = urlparse(url).hostname or ""
        if self.domain_allowlist and host not in self.domain_allowlist:
            raise PermissionError_(f"domain '{host}' is not in the allowlist")

    # --- MCP stdio --------------------------------------------------------
    def authorize_mcp_command(self, command: str) -> None:
        """A stdio MCP server launches a local process — only allow declared binaries."""
        if not command:
            raise PermissionError_("empty MCP command")
        base = os.path.basename(command)
        allowed = self.command_allowlist
        if allowed and command not in allowed and base not in allowed:
            raise PermissionError_(
                f"MCP command '{command}' is not in mcp.command_allowlist"
            )

    # --- filesystem -------------------------------------------------------
    def authorize_fs(self, path: str) -> None:
        if not self.allow_fs and not self.fs_roots:
            raise PermissionError_("filesystem access not permitted for this agent")
        if self.fs_roots:
            target = Path(path).resolve()
            if not any(self._within(target, root) for root in self.fs_roots):
                raise PermissionError_(f"path '{path}' is outside the allowed roots")

    @staticmethod
    def _within(target: Path, root: Path) -> bool:
        try:
            target.relative_to(root)
            return True
        except ValueError:
            return False

    # --- code execution ---------------------------------------------------
    def authorize_code_exec(self, *, on_host: bool) -> None:
        if not self.allow_code_exec:
            raise PermissionError_("code execution is disabled (see config: code_exec.enabled)")
        if on_host:
            # Running generated code directly on the host is opt-in and dangerous.
            raise PermissionError_(
                "host code execution is blocked; use the Docker sandbox "
                "(set code_exec.allow_host: true only if you accept the risk)"
            )
