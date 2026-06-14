"""CLI runner — the fastest way to run an agent end-to-end and watch the pipeline.

Usage (PowerShell / bash):
    python -m core.cli --agent plumber "יש לי נזילה מתחת לכיור, מה לבדוק קודם?"
    python -m core.cli --agent plumber --mock "סתימה בכיור"     # no API key needed
    python -m core.cli --list

It prints the step inspector (each node + timing), then the answer and token usage.
"""

from __future__ import annotations

import argparse
import sys

from core.agents.registry import get_agent, list_agents
from core.runtime.orchestrator import run_agent
from core.security.secrets import get_secret


def _print_event(ev: dict) -> None:
    if ev["type"] == "node_start":
        print(f"  ▶ {ev['node']} ...", flush=True)
    elif ev["type"] == "node_end":
        status = "ok" if ev["ok"] else f"ERROR: {ev['error']}"
        print(f"  ✔ {ev['node']}  ({ev['duration_ms']} ms)  [{status}]", flush=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run an AI agent.")
    p.add_argument("question", nargs="?", help="the user input")
    p.add_argument("--agent", default="plumber")
    p.add_argument("--mock", action="store_true", help="force mock provider (no API key)")
    p.add_argument("--list", action="store_true", help="list available agents")
    args = p.parse_args(argv)

    if args.list:
        print("Available agents:", ", ".join(list_agents()))
        return 0

    if not args.question:
        p.error("a question is required (or use --list)")

    mock = True if args.mock else None
    if mock is None and not get_secret("OPENROUTER_API_KEY"):
        print("ℹ️  OPENROUTER_API_KEY not set — running in MOCK mode.\n")

    agent = get_agent(args.agent, mock=mock)

    print(f"=== running agent: {agent.name} ===")
    print("--- step inspector ---")
    final = run_agent(agent, args.question, on_event=_print_event)

    print("\n--- answer ---")
    print(final.get("final_answer", "(no answer)"))

    if final.get("blocked"):
        print(f"\n[blocked] {final.get('block_reason')}")

    usage = final.get("usage", {})
    print(f"\n--- usage ---  in={usage.get('input_tokens', 0)} "
          f"out={usage.get('output_tokens', 0)} tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
