# Build the Python core into a single self-contained binary and place it where Tauri
# expects the sidecar (src-tauri/binaries/agents-core-<target-triple>.exe).
#
# Prereqs (in the project venv):  pip install -e .   ;   pip install pyinstaller
# Run from the repo root:          .\apps\desktop\scripts\build-sidecar.ps1

$ErrorActionPreference = "Stop"

# Resolve the Rust target triple (e.g. x86_64-pc-windows-msvc).
$triple = (rustc -Vv | Select-String "host:").ToString().Split(" ")[1]
Write-Host "Target triple: $triple"

$binDir = "apps/desktop/src-tauri/binaries"
New-Item -ItemType Directory -Force -Path $binDir | Out-Null

# One-file build of the FastAPI entrypoint. hidden-imports cover dynamic uvicorn/langgraph bits.
pyinstaller --onefile --name agents-core `
    --hidden-import=uvicorn.logging `
    --hidden-import=uvicorn.protocols.http.h11_impl `
    --hidden-import=uvicorn.protocols.websockets.websockets_impl `
    --hidden-import=uvicorn.lifespan.on `
    --collect-all langgraph `
    --collect-all mcp `
    core/server/__main__.py

$src = "dist/agents-core.exe"
$dst = "$binDir/agents-core-$triple.exe"
Copy-Item $src $dst -Force
Write-Host "Sidecar ready: $dst"
