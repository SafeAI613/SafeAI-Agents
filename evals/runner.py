"""Eval runner.

Runs an agent against its dataset and scores each case against its declared checks.
CI-friendly: exits non-zero if any case fails (so it can gate a merge).

Usage:
    python -m evals.runner --suite plumber
    python -m evals.runner --suite plumber --mock     # structural checks only
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

import yaml

from core.agents.registry import get_agent
from core.runtime.orchestrator import run_agent
from core.security.secrets import get_secret

_ROOT = Path(__file__).resolve().parent


def _load_dataset(suite: str) -> list[dict]:
    path = _ROOT / "datasets" / f"{suite}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data.get("cases", [])


def _load_checks(suite: str) -> dict:
    mod = importlib.import_module(f"evals.suites.{suite}")
    return mod.CHECKS


def run_suite(suite: str, mock: bool | None) -> bool:
    cases = _load_dataset(suite)
    checks = _load_checks(suite)

    total = 0
    passed = 0
    print(f"=== eval suite: {suite} ({'mock' if mock else 'real'}) ===\n")

    for case in cases:
        agent = get_agent(suite, mock=mock)
        final = run_agent(agent, case["input"])
        print(f"[{case['id']}] {case['input'][:50]}")
        case_ok = True
        for key, expected in case.get("checks", {}).items():
            if key not in checks:
                print(f"    ? unknown check '{key}' — skipped")
                continue
            total += 1
            ok, detail = checks[key](final, expected)
            passed += int(ok)
            case_ok &= ok
            print(f"    {'PASS' if ok else 'FAIL'}  {key}: {detail}")
        print(f"  -> {'OK' if case_ok else 'CASE FAILED'}\n")

    print(f"=== {passed}/{total} checks passed ===")
    return passed == total


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run agent evals.")
    p.add_argument("--suite", default="plumber")
    p.add_argument("--mock", action="store_true")
    args = p.parse_args(argv)

    mock = True if args.mock else None
    if mock is None and not get_secret("OPENROUTER_API_KEY"):
        print("ℹ️  OPENROUTER_API_KEY not set — running evals in MOCK mode "
              "(content checks will not be meaningful).\n")
        mock = True

    ok = run_suite(args.suite, mock)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
