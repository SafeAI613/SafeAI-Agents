# AI Agents Desktop — Tauri shell

Turns the existing FastAPI core (`core/`) + React client (`client/`) into a desktop app.
The Python core runs as a **sidecar**: Tauri spawns it on launch and kills it on exit. The
UI talks to it over `http://localhost:8000` (same as in dev), so no Tauri-specific
networking is needed in the React code.

```
apps/desktop/
  src-tauri/
    tauri.conf.json        # points frontendDist at ../../client, externalBin: binaries/agents-core
    capabilities/default.json
    Cargo.toml  build.rs
    src/main.rs            # spawns + kills the agents-core sidecar
    binaries/              # agents-core-<target-triple>[.exe]  (produced by the build script)
  scripts/
    build-sidecar.ps1 / .sh   # PyInstaller -> binaries/agents-core-<triple>
```

## Prerequisites

- Rust + the Tauri CLI v2 (`npm i -g @tauri-apps/cli` or `cargo install tauri-cli`)
- Node 18+ (for the client) and Python 3.10+ (for the core)
- For code execution: Docker (`docker build -t ai-agents-sandbox:latest infra/sandbox`)
- For voice input: `pip install -e .[stt]` and `ffmpeg` on PATH

## Develop (hot reload)

Tauri runs the client's Vite dev server and the core itself in dev. From the repo root:

```powershell
pip install -e .                     # core, incl. mcp
npm --prefix client install
cd apps/desktop
cargo tauri dev
```

In dev, `cargo tauri dev` starts the Vite server (per `beforeDevCommand`). The **core**
sidecar only exists once you've built it (next section); until then, run it manually in a
second terminal: `uvicorn core.server.app:app --reload`.

## Build the sidecar + the app

```powershell
pip install -e .[desktop]            # adds pyinstaller
.\apps\desktop\scripts\build-sidecar.ps1   # -> src-tauri/binaries/agents-core-<triple>.exe
cd apps/desktop
cargo tauri build
```

`build-sidecar.ps1` runs PyInstaller `--onefile` over `core/server/__main__.py`, resolves
the Rust target triple, and copies the binary to the name Tauri expects.

## What the desktop build wires up

- **MCP** — servers from `infra/mcp-servers/servers.yaml`; manage them in the Workbench → MCP tab.
- **Code execution** — Docker sandbox; enable with `code_exec.enabled: true` in `config/default.yaml`.
- **Files** — workspace browser (Workbench → קבצים), scoped to `files.workspace`.
- **Voice input** — mic button in the chat footer → `/stt` (local faster-whisper by default).
