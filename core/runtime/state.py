"""Shared state schema for agent workflows.

Every agent runs over a typed state. Nodes return *partial* updates that LangGraph
merges into the running state. Keep the schema flat and JSON-serializable so the UI
step-inspector and the tracing layer can render it directly.
"""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    # --- input ---
    user_input: str            # the raw user question / request
    agent_name: str            # which agent is running

    # --- working fields ---
    messages: list[dict]       # chat history sent to the provider
    history: list[dict]        # prior conversation turns (role/content) for multi-turn
    draft_answer: str          # provider output before output-guardrails
    final_answer: str          # what the user sees

    # --- RAG (used by retrieval agents like device_guide) ---
    retrieved: str             # retrieved context (manual chunks) for grounding
    sources: list[str]         # which documents the context came from


    # --- control / safety ---
    blocked: bool              # set True if a guardrail blocked the turn
    block_reason: str          # human-readable reason

    # --- bookkeeping (filled by the runtime, not by nodes) ---
    usage: dict[str, Any]      # token usage accumulated across provider calls
    trace: list[dict]          # per-node events (start/end/timing)
