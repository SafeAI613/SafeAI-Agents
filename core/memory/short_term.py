"""Short-term memory: the conversation window passed to the provider.

Distinct from RAG (external knowledge) and from long-term semantic memory (the agent's
own persisted memory, added later under memory/long_term.py).
"""

from __future__ import annotations


def build_messages(system_prompt: str, user_input: str,
                   history: list[dict] | None = None) -> list[dict]:
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_input})
    return messages
