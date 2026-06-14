"""The device-guide agent workflow.

Graph: START -> guard_input -> (blocked? END : retrieve) -> answer -> END

The corpus is loaded and the lexical index built once at import. Same agent shape as
the plumber: own graph.py + agent.yaml, plus a corpus/ folder and a skill.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

import yaml
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from core.agents.device_guide import nodes
from core.runtime.events import Tracer
from core.runtime.orchestrator import traced
from core.runtime.state import AgentState
from core.tools.rag import LexicalIndex, load_corpus
from core.tools.skills import load_skills

_DIR = Path(__file__).parent
_CFG = yaml.safe_load((_DIR / "agent.yaml").read_text(encoding="utf-8"))
_SKILLS_TEXT = load_skills(_DIR, _CFG.get("skills", []))

_RAG = _CFG.get("rag", {}) or {}
_CORPUS_DIR = _DIR / _RAG.get("corpus_dir", "corpus")
_TOP_K = _RAG.get("top_k", 4)
_INDEX = LexicalIndex(load_corpus(_CORPUS_DIR))


def _route_after_input(state: AgentState) -> str:
    return "END" if state.get("blocked") else "retrieve"


class DeviceGuideAgent:
    name = _CFG["name"]
    config = _CFG

    def __init__(self, mock: bool | None = None):
        self.mock = mock

    def build(self, tracer: Tracer):
        retrieve_node = partial(nodes.retrieve, index=_INDEX, top_k=_TOP_K)
        answer_node = partial(
            nodes.answer,
            model=_CFG["model"],
            max_output_tokens=_CFG["max_output_tokens"],
            budget_tokens=_CFG["budget_tokens"],
            mock=self.mock,
            skills_text=_SKILLS_TEXT,
        )

        g = StateGraph(AgentState)
        g.add_node("guard_input", traced("guard_input", nodes.guard_input, tracer))
        g.add_node("retrieve", traced("retrieve", retrieve_node, tracer))
        g.add_node("answer", traced("answer", answer_node, tracer))

        g.add_edge(START, "guard_input")
        g.add_conditional_edges("guard_input", _route_after_input,
                                {"retrieve": "retrieve", "END": END})
        g.add_edge("retrieve", "answer")
        g.add_edge("answer", END)

        return g.compile(checkpointer=MemorySaver())


def make_agent(mock: bool | None = None) -> DeviceGuideAgent:
    return DeviceGuideAgent(mock=mock)
