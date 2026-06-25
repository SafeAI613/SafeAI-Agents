"""The news_writer agent workflow.

Graph: START -> guard_input -> (blocked? END : fetch_news) -> write_bulletin -> END

Same shape as device_guide, but "retrieval" is a live web search (core/tools/web) instead
of a local corpus. The PermissionBroker (network + domain allowlist) is built once at
import from agent.yaml and is the single choke point for the outbound search request.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

import yaml
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from core.agents.news_writer import nodes
from core.runtime.events import Tracer
from core.runtime.orchestrator import traced
from core.runtime.state import AgentState
from core.security.permissions import PermissionBroker
from core.tools.skills import load_skills

_DIR = Path(__file__).parent
_CFG = yaml.safe_load((_DIR / "agent.yaml").read_text(encoding="utf-8"))
_SKILLS_TEXT = load_skills(_DIR, _CFG.get("skills", []))

_WEB = _CFG.get("web", {}) or {}
_BROKER = PermissionBroker(
    domain_allowlist=_WEB.get("domain_allowlist", []),
    allow_network=True,
)


def _route_after_input(state: AgentState) -> str:
    return "END" if state.get("blocked") else "fetch_news"


class NewsWriterAgent:
    name = _CFG["name"]
    config = _CFG

    def __init__(self, mock: bool | None = None):
        self.mock = mock

    def build(self, tracer: Tracer):
        fetch_node = partial(
            nodes.fetch_news,
            broker=_BROKER,
            max_results=_WEB.get("max_results", 6),
            recency=_WEB.get("recency", "w") or None,
            query_suffix=_WEB.get("query_suffix", ""),
            mock=self.mock,
        )
        write_node = partial(
            nodes.write_bulletin,
            model=_CFG["model"],
            max_output_tokens=_CFG["max_output_tokens"],
            budget_tokens=_CFG["budget_tokens"],
            mock=self.mock,
            skills_text=_SKILLS_TEXT,
        )

        g = StateGraph(AgentState)
        g.add_node("guard_input", traced("guard_input", nodes.guard_input, tracer))
        g.add_node("fetch_news", traced("fetch_news", fetch_node, tracer))
        g.add_node("write_bulletin", traced("write_bulletin", write_node, tracer))

        g.add_edge(START, "guard_input")
        g.add_conditional_edges("guard_input", _route_after_input,
                                {"fetch_news": "fetch_news", "END": END})
        g.add_edge("fetch_news", "write_bulletin")
        g.add_edge("write_bulletin", END)

        return g.compile(checkpointer=MemorySaver())


def make_agent(mock: bool | None = None) -> NewsWriterAgent:
    return NewsWriterAgent(mock=mock)
