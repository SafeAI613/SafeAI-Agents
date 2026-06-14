"""Smoke test: the plumber pipeline runs end-to-end in mock mode and is traced."""

from core.agents.registry import get_agent
from core.runtime.orchestrator import run_agent


def test_plumber_runs_mock():
    agent = get_agent("plumber", mock=True)
    final = run_agent(agent, "יש נזילה מתחת לכיור, מה לבדוק?")
    assert final.get("final_answer")
    assert final.get("blocked") is False
    # every node emitted start + end
    nodes = {e["node"] for e in final["trace"]}
    assert {"guard_input", "generate"} <= nodes


def test_empty_input_blocked():
    agent = get_agent("plumber", mock=True)
    final = run_agent(agent, "   ")
    assert final.get("blocked") is True
