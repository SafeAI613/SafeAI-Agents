"""Generic run engine.

The orchestrator is agent-agnostic: it wraps every node with tracing and runs any
agent's compiled graph, returning the final state plus the collected trace. No
agent-specific logic lives here — adding a new agent never touches this file.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from core.runtime.events import Tracer
from core.runtime.state import AgentState


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
              on_event: Callable[[dict], None] | None = None) -> dict[str, Any]:
    """Run an agent end-to-end.

    `agent` exposes `.name` and `.build(tracer) -> compiled graph`.
    Returns the final state with `trace` attached.
    """
    tracer = Tracer()
    if on_event:
        tracer.on_event(on_event)

    graph = agent.build(tracer)
    thread_id = str(uuid.uuid4())

    initial: AgentState = {
        "user_input": user_input,
        "agent_name": agent.name,
        "messages": [],
        "usage": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        "blocked": False,
    }

    final = graph.invoke(initial, config={"configurable": {"thread_id": thread_id}})
    final["trace"] = tracer.events
    return dict(final)
