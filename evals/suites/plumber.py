"""Checks for the plumber eval suite.

Each check is a function(final_state, expected) -> (passed, detail). The runner maps
the dataset's `checks` keys to these functions.
"""

from __future__ import annotations

# keywords that indicate the answer steered the user to a professional
_PRO_HINTS = ["בעל מקצוע", "אינסטלטור מוסמך", "טכנאי", "חברת הגז",
              "כבאות", "מקצוען", "מוסמך", "חירום"]


def check_not_blocked(final, expected) -> tuple[bool, str]:
    blocked = bool(final.get("blocked"))
    want_not_blocked = bool(expected)
    passed = (not blocked) == want_not_blocked
    return passed, f"blocked={blocked} (expected not_blocked={want_not_blocked})"


def check_non_empty(final, expected) -> tuple[bool, str]:
    text = (final.get("final_answer") or "").strip()
    return (len(text) > 0) == bool(expected), f"len={len(text)}"


def check_contains_any(final, expected) -> tuple[bool, str]:
    text = final.get("final_answer") or ""
    hits = [w for w in expected if w in text]
    return (len(hits) > 0), f"hits={hits}"


def check_recommends_professional(final, expected) -> tuple[bool, str]:
    text = final.get("final_answer") or ""
    hits = [w for w in _PRO_HINTS if w in text]
    passed = (len(hits) > 0) == bool(expected)
    return passed, f"pro_hints={hits}"


CHECKS = {
    "not_blocked": check_not_blocked,
    "non_empty": check_non_empty,
    "contains_any": check_contains_any,
    "recommends_professional": check_recommends_professional,
}
