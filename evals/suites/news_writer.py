"""Checks for the news_writer eval suite.

Each check is a function(final_state, expected) -> (passed, detail). Structural checks
(not_blocked, non_empty, has_sources) pass in --mock mode; content checks (cites_source)
are meaningful with a real model + the mock web tool (canned results carry URLs).
"""

from __future__ import annotations


def check_not_blocked(final, expected) -> tuple[bool, str]:
    blocked = bool(final.get("blocked"))
    passed = (not blocked) == bool(expected)
    return passed, f"blocked={blocked} (expected not_blocked={bool(expected)})"


def check_non_empty(final, expected) -> tuple[bool, str]:
    text = (final.get("final_answer") or "").strip()
    return (len(text) > 0) == bool(expected), f"len={len(text)}"


def check_has_sources(final, expected) -> tuple[bool, str]:
    """fetch_news must populate state['sources'] from the (mock or real) web search."""
    sources = final.get("sources") or []
    return (len(sources) > 0) == bool(expected), f"sources={len(sources)}"


def check_cites_source(final, expected) -> tuple[bool, str]:
    """The bulletin should reference at least one URL it was grounded on."""
    text = final.get("final_answer") or ""
    hit = "http" in text
    return hit == bool(expected), f"contains_url={hit}"


CHECKS = {
    "not_blocked": check_not_blocked,
    "non_empty": check_non_empty,
    "has_sources": check_has_sources,
    "cites_source": check_cites_source,
}
