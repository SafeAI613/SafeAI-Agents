"""Permission broker.

Every sensitive action (network, file, browser) must be authorized here against the
agent's declared policy before it runs. The plumber agent uses no tools, so nothing is
brokered yet — but tool-using agents (news reviewer, device guide) will route through
`authorize()`.

This is the single choke point for the domain allowlist and capability scoping.
"""

from __future__ import annotations

from urllib.parse import urlparse


class PermissionError_(Exception):
    pass


class PermissionBroker:
    def __init__(self, *, domain_allowlist: list[str] | None = None,
                 allow_network: bool = False, allow_fs: bool = False):
        self.domain_allowlist = set(domain_allowlist or [])
        self.allow_network = allow_network
        self.allow_fs = allow_fs

    def authorize_url(self, url: str) -> None:
        if not self.allow_network:
            raise PermissionError_("network access not permitted for this agent")
        host = urlparse(url).hostname or ""
        if self.domain_allowlist and host not in self.domain_allowlist:
            raise PermissionError_(f"domain '{host}' is not in the allowlist")

    def authorize_fs(self, path: str) -> None:
        if not self.allow_fs:
            raise PermissionError_("filesystem access not permitted for this agent")
