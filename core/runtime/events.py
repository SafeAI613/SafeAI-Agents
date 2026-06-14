"""Per-node tracing.

The runtime wraps every node so that each step emits a start and an end event with
timing. Events are plain dicts (JSON-serializable) so they can be streamed to the UI
over WebSocket and exported to LangSmith / OpenTelemetry later.

This module deliberately has no LangGraph dependency: it is a generic event sink.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tracer:
    """Collects node events for a single agent run."""

    events: list[dict] = field(default_factory=list)
    _listeners: list[Callable[[dict], None]] = field(default_factory=list)

    def on_event(self, listener: Callable[[dict], None]) -> None:
        """Register a callback (e.g. the WS streamer) for live events."""
        self._listeners.append(listener)

    def emit(self, event: dict) -> None:
        self.events.append(event)
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:  # a broken listener must never break a run
                pass

    def node_start(self, node: str) -> float:
        ts = time.perf_counter()
        self.emit({"type": "node_start", "node": node, "t": time.time()})
        return ts

    def node_end(self, node: str, started: float, *, ok: bool = True,
                 error: str | None = None, info: dict[str, Any] | None = None) -> None:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        self.emit({
            "type": "node_end",
            "node": node,
            "ok": ok,
            "duration_ms": duration_ms,
            "error": error,
            "info": info or {},
            "t": time.time(),
        })
