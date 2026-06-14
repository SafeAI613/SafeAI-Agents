"""Observability exporter — STUB.

The in-run Tracer (core/runtime/events.py) already collects per-node timing. This module
is the seam to export those events to LangSmith / OpenTelemetry. No-op for now.
"""

from __future__ import annotations


def export(trace: list[dict]) -> None:  # pragma: no cover - stub
    """Export a completed run's trace to an external backend. Wire LangSmith/OTel here."""
    return None
