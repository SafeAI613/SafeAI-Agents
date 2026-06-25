"""CLI runner — the fastest way to run an agent end-to-end and watch the pipeline.

Usage (PowerShell / bash):
    python -m core.cli --agent plumber "יש לי נזילה מתחת לכיור, מה לבדוק קודם?"
    python -m core.cli --agent plumber --mock "סתימה בכיור"     # no API key needed
    python -m core.cli --list

It prints the step inspector (each node + timing), then the answer and token usage.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from core.agents.registry import get_agent, list_agents
from core.runtime.orchestrator import run_agent
from core.security.api_keys import clear_key, resolve_openrouter_key, store_key

from dotenv import load_dotenv
load_dotenv(override=True)

    
def _print_event(ev: dict) -> None:
    if ev["type"] == "node_start":
        print(f"  ▶ {ev['node']} ...", flush=True)
    elif ev["type"] == "node_end":
        status = "ok" if ev["ok"] else f"ERROR: {ev['error']}"
        print(f"  ✔ {ev['node']}  ({ev['duration_ms']} ms)  [{status}]", flush=True)

def chat_loop(agent_name: str, mock: bool | None, *, api_key: str | None = None) -> int:
    """Multi-turn conversation loop. History is held here and passed into each turn,
    so the agent can ask clarifying questions and then answer based on the replies."""
    agent = get_agent(agent_name, mock=mock)
    history: list[dict] = []
    print(f"=== chat with agent: {agent.name} ===")
    print("מצב שיחה. הקלידי 'יציאה' (או exit / Ctrl+C) לסיום.\n")

    while True:
        try:
            user = input("את/ה> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user in {"יציאה", "exit", "quit", "q"}:
            break

        final = run_agent(agent, user, history=history, api_key=api_key)
        answer = final.get("final_answer", "(no answer)")
        print(f"\אייג'נט> {answer}\n")

        if final.get("blocked"):
            print(f"[blocked] {final.get('block_reason')}\n")
            continue

        # accumulate the turn so the next turn has full context
        history.append({"role": "user", "content": user})
        history.append({"role": "assistant", "content": answer})

    print("סיום שיחה.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run an AI agent.")
    p.add_argument("question", nargs="?", help="the user input")
    p.add_argument("--agent", default="plumber")
    p.add_argument("--mock", action="store_true", help="force mock provider (no API key)")
    p.add_argument("--chat", action="store_true", help="interactive multi-turn chat loop")
    p.add_argument("--list", action="store_true", help="list available agents")
    p.add_argument("--api-key", help="OpenRouter API key for this run only (not stored)")
    p.add_argument("--set-key", action="store_true", help="save OpenRouter key to OS keychain")
    p.add_argument("--clear-key", action="store_true", help="remove stored key from OS keychain")
    args = p.parse_args(argv)

    if args.set_key:
        key = getpass.getpass("OpenRouter API key: ").strip()
        if not key:
            print("לא הוזן מפתח.")
            return 1
        store_key(key)
        print("המפתח נשמר ב-keychain.")
        return 0

    if args.clear_key:
        clear_key()
        print("המפתח נמחק מה-keychain.")
        return 0

    if args.list:
        print("Available agents:", ", ".join(list_agents()))
        return 0

    mock = True if args.mock else None
    if mock is None and not resolve_openrouter_key():
        print("ℹ️  OPENROUTER_API_KEY not set — running in MOCK mode.\n")

    if args.chat:
        return chat_loop(args.agent, mock, api_key=args.api_key)

    if not args.question:
        p.error("a question is required (or use --chat / --list)")

    agent = get_agent(args.agent, mock=mock)

    print(f"=== running agent: {agent.name} ===")
    print("--- step inspector ---")
    final = run_agent(agent, args.question, api_key=args.api_key, on_event=_print_event)

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
