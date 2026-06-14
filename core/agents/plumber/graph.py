"""The plumber agent workflow.

Graph: START -> guard_input -> (blocked? END : generate) -> END

This is the reference end-to-end agent. It exercises every architectural layer the
runtime provides — workflow, tracing, guardrails, provider, budget, state — without
needing any tools. New agents follow the same shape: own graph.py + agent.yaml.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

import yaml
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from core.agents.plumber import nodes
from core.runtime.events import Tracer
from core.runtime.orchestrator import traced
from core.runtime.state import AgentState
from core.tools.skills import load_skills

_CFG = yaml.safe_load((Path(__file__).parent / "agent.yaml").read_text(encoding="utf-8"))
_SKILLS_TEXT = load_skills(Path(__file__).parent, _CFG.get("skills", []))


def _route_after_input(state: AgentState) -> str:
    return "END" if state.get("blocked") else "generate"


class PlumberAgent:
    name = _CFG["name"]
    config = _CFG

    def __init__(self, mock: bool | None = None):
        self.mock = mock

    def build(self, tracer: Tracer):
        generate_node = partial(
            nodes.generate,
            model=_CFG["model"],
            max_output_tokens=_CFG["max_output_tokens"],
            budget_tokens=_CFG["budget_tokens"],
            mock=self.mock,
            skills_text=_SKILLS_TEXT,
        )

        g = StateGraph(AgentState)
        g.add_node("guard_input", traced("guard_input", nodes.guard_input, tracer))
        g.add_node("generate", traced("generate", generate_node, tracer))

        g.add_edge(START, "guard_input")
        g.add_conditional_edges("guard_input", _route_after_input,
                                {"generate": "generate", "END": END})
        g.add_edge("generate", END)

        return g.compile(checkpointer=MemorySaver())


def make_agent(mock: bool | None = None) -> PlumberAgent:
    return PlumberAgent(mock=mock)