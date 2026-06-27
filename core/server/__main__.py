"""Entrypoint for the bundled core sidecar.

Run directly (`python -m core.server`) or as the PyInstaller-built binary the Tauri shell
launches. Binds to localhost only — the desktop UI is the sole client.
"""

from __future__ import annotations

import os

import uvicorn

from core.server.app import app


def main() -> None:
    host = os.environ.get("CORE_HOST", "127.0.0.1")
    port = int(os.environ.get("CORE_PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
