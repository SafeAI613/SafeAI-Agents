"""OpenRouter provider.

Owns the single client that talks to the model. OpenRouter only gives us completions +
tool calling; everything else (RAG, MCP, code-exec) is implemented elsewhere as tools.

Two modes:
  * real  -> POST to OpenRouter (OpenAI-compatible chat/completions). Requires
             OPENROUTER_API_KEY.
  * mock  -> returns a canned response without any network call.

Budget caps are enforced here: a run that exceeds its token budget raises BudgetExceeded.

This file adds `complete_with_tools()` on top of the original `complete()`: it sends an
OpenAI-style `tools` array and returns either assistant text or a list of requested tool
calls, so a workflow can run a tool-calling loop (MCP tools, code-exec) over the model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

from core.security.api_keys import resolve_openrouter_key

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class BudgetExceeded(Exception):
    pass


@dataclass
class Completion:
    text: str
    input_tokens: int
    output_tokens: int


@dataclass
class ToolCall:
    id: str
    name: str                       # OpenAI-style function name (server__tool)
    arguments: dict


@dataclass
class ToolTurn:
    """One assistant turn that may carry text and/or tool calls."""
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_message: dict | None = None     # the assistant message, to append to history
    input_tokens: int = 0
    output_tokens: int = 0


class OpenRouterProvider:
    def __init__(self, *, model: str, max_output_tokens: int = 1024,
                 budget_tokens: int | None = None, mock: bool | None = None):
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.budget_tokens = budget_tokens
        self._api_key = resolve_openrouter_key()
        self.mock = mock if mock is not None else (self._api_key is None)

    # --- plain completion (unchanged) -------------------------------------
    def complete(self, messages: list[dict], *, used_tokens: int = 0) -> Completion:
        if self.mock:
            return self._mock_complete(messages)
        return self._real_complete(messages, used_tokens=used_tokens)

    def _mock_complete(self, messages: list[dict]) -> Completion:
        user_turns = [m for m in messages if m["role"] == "user"]
        last_user = user_turns[-1]["content"] if user_turns else ""
        text = f"‎[MOCK] תשובה לדוגמה. (הגדירי OPENROUTER_API_KEY לתשובות אמיתיות.) «{last_user[:80]}»"
        return Completion(text=text, input_tokens=len(last_user) // 4 + 20,
                          output_tokens=len(text) // 4)

    def _real_complete(self, messages: list[dict], *, used_tokens: int) -> Completion:
        payload = {"model": self.model, "messages": messages,
                   "max_tokens": self.max_output_tokens}
        headers = {"Authorization": f"Bearer {self._api_key}",
                   "Content-Type": "application/json"}
        with httpx.Client(timeout=60) as client:
            resp = client.post(OPENROUTER_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {}) or {}
        in_tok = usage.get("prompt_tokens", 0)
        out_tok = usage.get("completion_tokens", 0)
        self._enforce_budget(used_tokens, in_tok, out_tok)
        return Completion(text=text, input_tokens=in_tok, output_tokens=out_tok)

    # --- tool-calling turn (new) ------------------------------------------
    def complete_with_tools(self, messages: list[dict], tools: list[dict], *,
                            used_tokens: int = 0) -> ToolTurn:
        """One assistant turn with tool calling enabled.

        `tools` is an OpenAI tools array. Returns a ToolTurn carrying any text and/or the
        tool calls the model requested. If `tools` is empty, behaves like a completion.
        """
        if self.mock:
            return self._mock_tool_turn(messages, tools)

        payload: dict = {"model": self.model, "messages": messages,
                         "max_tokens": self.max_output_tokens}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {"Authorization": f"Bearer {self._api_key}",
                   "Content-Type": "application/json"}
        with httpx.Client(timeout=90) as client:
            resp = client.post(OPENROUTER_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        msg = data["choices"][0]["message"]
        usage = data.get("usage", {}) or {}
        in_tok = usage.get("prompt_tokens", 0)
        out_tok = usage.get("completion_tokens", 0)
        self._enforce_budget(used_tokens, in_tok, out_tok)

        calls: list[ToolCall] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=tc.get("id", ""), name=fn.get("name", ""), arguments=args))

        return ToolTurn(text=msg.get("content") or "", tool_calls=calls,
                        raw_message=msg, input_tokens=in_tok, output_tokens=out_tok)

    def _mock_tool_turn(self, messages: list[dict], tools: list[dict]) -> ToolTurn:
        # Deterministic mock: never calls a tool, just answers, so the loop terminates.
        comp = self._mock_complete(messages)
        return ToolTurn(text=comp.text, tool_calls=[],
                        raw_message={"role": "assistant", "content": comp.text},
                        input_tokens=comp.input_tokens, output_tokens=comp.output_tokens)

    # --- budget -----------------------------------------------------------
    def _enforce_budget(self, used: int, in_tok: int, out_tok: int) -> None:
        if self.budget_tokens is not None and used + in_tok + out_tok > self.budget_tokens:
            raise BudgetExceeded(
                f"token budget {self.budget_tokens} exceeded ({used + in_tok + out_tok})"
            )
