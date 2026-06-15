"""Generic run engine.

The orchestrator is agent-agnostic: it wraps every node with tracing and runs any
agent's compiled graph, returning the final state plus the collected trace. No
agent-specific logic lives here — adding a new agent never touches this file.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any, Callable

from core.runtime.events import Tracer
from core.runtime.state import AgentState

# Nodes read this to stream tokens without needing signature changes.
on_token_var: ContextVar[Callable[[str], None] | None] = ContextVar("on_token", default=None)


def traced(node_name: str, fn: Callable[[AgentState], dict], tracer: Tracer):
    """Wrap a node function so it emits start/end + timing events."""

    def wrapper(state: AgentState) -> dict:
        started = tracer.node_start(node_name)
        try:
            update = fn(state) or {}
            tracer.node_end(node_name, started, ok=True,
                            info={"keys": list(update.keys())})
            return update
        except Exception as exc:  # surface the failure in the trace, then re-raise
            tracer.node_end(node_name, started, ok=False, error=str(exc))
            raise

    return wrapper


def run_agent(agent, user_input: str, *,
              history: list[dict] | None = None,
              api_key: str | None = None,
              on_event: Callable[[dict], None] | None = None,
              on_token: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Run an agent end-to-end.

    `agent` exposes `.name` and `.build(tracer) -> compiled graph`.
    Returns the final state with `trace` attached.
    """
    from core.security.api_keys import set_request_key
    if api_key is not None:
        set_request_key(api_key)

    tracer = Tracer()
    if on_event:
        tracer.on_event(on_event)

    token = on_token_var.set(on_token)
    try:
        return _invoke(agent, user_input, history, tracer)
    finally:
        on_token_var.reset(token)


def _invoke(agent, user_input: str, history, tracer: Tracer) -> dict[str, Any]:
    graph = agent.build(tracer)
    thread_id = str(uuid.uuid4())

    initial: AgentState = {
        "user_input": user_input,
        "agent_name": agent.name,
        "messages": [],
        "history": history or [],
        "usage": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        "blocked": False,
    }

    final = graph.invoke(initial, config={"configurable": {"thread_id": thread_id}})
    final["trace"] = tracer.events
    return dict(final)
