"""SafeAI guardrails proxy.

ALL model I/O is meant to flow through here. The proxy:
  1. runs the input through local policies (and, when configured, the SafeAI gateway),
  2. calls the underlying provider,
  3. runs the output through local policies (and SafeAI),
returning either the cleared text or a block decision.

By default SafeAI is OFF (pass-through to local policies only) so the project runs
out of the box. Set guardrails.safeai.enabled + url in config/default.yaml to route
through your existing SafeAI gateway. The HTTP call below is the integration seam —
point it at your deployed SafeAI moderation endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from core.guardrails import policies
from core.providers.openrouter import Completion, OpenRouterProvider
from core.security.secrets import load_config


@dataclass
class GuardedResult:
    text: str
    blocked: bool
    reason: str
    completion: Completion | None


class SafeAIProxy:
    def __init__(self, provider: OpenRouterProvider):
        self.provider = provider
        gw = (load_config().get("guardrails", {}) or {}).get("safeai", {}) or {}
        self.safeai_enabled = bool(gw.get("enabled", False))
        self.safeai_url = gw.get("url")

    # --- external SafeAI gateway (optional) -------------------------------
    def _safeai_check(self, text: str, direction: str) -> policies.PolicyResult:
        """Call the deployed SafeAI gateway. direction = 'input' | 'output'.

        Adapt the payload/parse to your SafeAI API contract. Fails OPEN to local
        policies on transport error (log + continue) so a gateway hiccup does not
        brick every agent; change to fail-closed if you prefer stricter behavior.
        """
        if not (self.safeai_enabled and self.safeai_url):
            return policies.PolicyResult(True)
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(self.safeai_url,
                                   json={"text": text, "direction": direction})
                resp.raise_for_status()
                data = resp.json()
            if data.get("blocked"):
                return policies.PolicyResult(False, data.get("reason", "blocked by SafeAI"))
            return policies.PolicyResult(True)
        except Exception:
            return policies.PolicyResult(True)  # fail-open to local policies

    # --- main entry -------------------------------------------------------
    def complete(self, messages: list[dict], *, used_tokens: int = 0) -> GuardedResult:
        user_text = next((m["content"] for m in reversed(messages)
                          if m["role"] == "user"), "")

        inp = policies.check_input(user_text)
        if inp.ok:
            inp = self._safeai_check(user_text, "input")
        if not inp.ok:
            return GuardedResult("", True, f"input: {inp.reason}", None)

        completion = self.provider.complete(messages, used_tokens=used_tokens)

        out = policies.check_output(completion.text)
        if out.ok:
            out = self._safeai_check(completion.text, "output")
        if not out.ok:
            return GuardedResult("", True, f"output: {out.reason}", completion)

        return GuardedResult(completion.text, False, "", completion)

    def stream_complete(self, messages: list[dict], on_token: callable, *,
                        used_tokens: int = 0) -> GuardedResult:
        user_text = next((m["content"] for m in reversed(messages)
                          if m["role"] == "user"), "")

        inp = policies.check_input(user_text)
        if inp.ok:
            inp = self._safeai_check(user_text, "input")
        if not inp.ok:
            return GuardedResult("", True, f"input: {inp.reason}", None)

        completion = self.provider.stream_complete(messages, on_token, used_tokens=used_tokens)

        out = policies.check_output(completion.text)
        if out.ok:
            out = self._safeai_check(completion.text, "output")
        if not out.ok:
            return GuardedResult("", True, f"output: {out.reason}", completion)

        return GuardedResult(completion.text, False, "", completion)
