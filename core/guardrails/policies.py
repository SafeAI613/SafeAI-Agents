"""Local input/output policies.

These are lightweight, deterministic checks that run on every turn regardless of whether
the external SafeAI gateway is wired in. They are the floor, not the ceiling: SafeAI
provides the real moderation. Keep these cheap and explainable.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_INPUT_CHARS = 4000
MAX_OUTPUT_CHARS = 8000


@dataclass
class PolicyResult:
    ok: bool
    reason: str = ""


def check_input(text: str) -> PolicyResult:
    if not text or not text.strip():
        return PolicyResult(False, "empty input")
    if len(text) > MAX_INPUT_CHARS:
        return PolicyResult(False, f"input exceeds {MAX_INPUT_CHARS} chars")
    return PolicyResult(True)


def check_output(text: str) -> PolicyResult:
    if not text or not text.strip():
        return PolicyResult(False, "empty output")
    if len(text) > MAX_OUTPUT_CHARS:
        return PolicyResult(False, f"output exceeds {MAX_OUTPUT_CHARS} chars")
    return PolicyResult(True)
