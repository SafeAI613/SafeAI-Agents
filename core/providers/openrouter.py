"""OpenRouter provider.

Owns the single client that talks to the model. OpenRouter only gives us completions +
tool calling; everything else (RAG, browser, code-exec) is implemented elsewhere as tools.

Two modes:
  * real  -> POST to OpenRouter (OpenAI-compatible chat/completions). Requires
             OPENROUTER_API_KEY.
  * mock  -> returns a canned response without any network call. Lets you run and inspect
             the full pipeline before wiring a key. Auto-selected when the key is missing,
             or forced with mock=True.

Budget caps are enforced here: a run that exceeds its token budget raises BudgetExceeded.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from core.security.secrets import get_secret

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class BudgetExceeded(Exception):
    pass


@dataclass
class Completion:
    text: str
    input_tokens: int
    output_tokens: int


class OpenRouterProvider:
    def __init__(self, *, model: str, max_output_tokens: int = 1024,
                 budget_tokens: int | None = None, mock: bool | None = None):
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.budget_tokens = budget_tokens
        self._api_key = get_secret("OPENROUTER_API_KEY")
        # mock if explicitly requested, or if no key is available
        self.mock = mock if mock is not None else (self._api_key is None)

    def complete(self, messages: list[dict], *, used_tokens: int = 0) -> Completion:
        if self.mock:
            return self._mock_complete(messages)
        return self._real_complete(messages, used_tokens=used_tokens)

    # --- mock -------------------------------------------------------------
    def _mock_complete(self, messages: list[dict]) -> Completion:
        user = next((m["content"] for m in reversed(messages)
                     if m["role"] == "user"), "")
        text = (
            "‎[MOCK] תשובת אינסטלטור לדוגמה.\n"
            f"קיבלתי את השאלה: «{user[:120]}».\n"
            "במצב אמיתי כאן תופיע תשובה שנוצרה על ידי המודל דרך OpenRouter. "
            "הגדירי OPENROUTER_API_KEY כדי לקבל תשובות אמיתיות."
        )
        return Completion(text=text, input_tokens=len(user) // 4 + 20,
                          output_tokens=len(text) // 4)

    # --- real -------------------------------------------------------------
    def _real_complete(self, messages: list[dict], *, used_tokens: int) -> Completion:
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_output_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        
        with httpx.Client(timeout=60) as client:
            resp = client.post(OPENROUTER_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {}) or {}
        in_tok = usage.get("prompt_tokens", 0)
        out_tok = usage.get("completion_tokens", 0)

        if self.budget_tokens is not None and used_tokens + in_tok + out_tok > self.budget_tokens:
            raise BudgetExceeded(
                f"token budget {self.budget_tokens} exceeded "
                f"({used_tokens + in_tok + out_tok})"
            )

        return Completion(text=text, input_tokens=in_tok, output_tokens=out_tok)
