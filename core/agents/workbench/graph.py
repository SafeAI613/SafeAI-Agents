"""The workbench agent workflow — the tool-using reference agent.

Graph: START -> guard_input -> (blocked? END : agent_loop) -> END

Same shape as the other agents (own graph.py + agent.yaml). The difference is the
agent_loop node, which runs a tool-calling loop over the connected MCP tools plus the
code-exec sandbox. MCP servers marked enabled: true in infra/mcp-servers/servers.yaml are
connected once at import.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path

import yaml
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from core.agents.workbench import nodes
from core.runtime.events import Tracer
from core.runtime.orchestrator import traced
from core.runtime.state import AgentState
from core.tools.mcp import autoconnect
from core.tools.skills import load_skills

_DIR = Path(__file__).parent
_CFG = yaml.safe_load((_DIR / "agent.yaml").read_text(encoding="utf-8"))
_SKILLS_TEXT = load_skills(_DIR, _CFG.get("skills", []))

# Connect enabled MCP servers once. Failures are reported per-server, never fatal.
_MCP_STATUS = autoconnect()


def _route_after_input(state: AgentState) -> str:
    return "END" if state.get("blocked") else "agent_loop"


class WorkbenchAgent:
    name = _CFG["name"]
    config = _CFG
    mcp_status = _MCP_STATUS

    def __init__(self, mock: bool | None = None):
        self.mock = mock

    def build(self, tracer: Tracer):
        loop_node = partial(
            nodes.agent_loop,
            model=_CFG["model"],
            max_output_tokens=_CFG["max_output_tokens"],
            budget_tokens=_CFG["budget_tokens"],
            mock=self.mock,
            skills_text=_SKILLS_TEXT,
            tracer=tracer,
            max_iters=_CFG.get("max_tool_iters", 6),
        )

        g = StateGraph(AgentState)
        g.add_node("guard_input", traced("guard_input", nodes.guard_input, tracer))
        g.add_node("agent_loop", traced("agent_loop", loop_node, tracer))

        g.add_edge(START, "guard_input")
        g.add_conditional_edges("guard_input", _route_after_input,
                                {"agent_loop": "agent_loop", "END": END})
        g.add_edge("agent_loop", END)

        return g.compile(checkpointer=MemorySaver())


def make_agent(mock: bool | None = None) -> WorkbenchAgent:
    return WorkbenchAgent(mock=mock)
