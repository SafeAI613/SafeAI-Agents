#!/usr/bin/env bash
# macOS/Linux equivalent of build-sidecar.ps1.
# Prereqs: pip install -e . && pip install pyinstaller
set -euo pipefail

triple=$(rustc -Vv | grep "host:" | cut -d' ' -f2)
echo "Target triple: $triple"

bin_dir="apps/desktop/src-tauri/binaries"
mkdir -p "$bin_dir"

pyinstaller --onefile --name agents-core \
    --hidden-import=uvicorn.logging \
    --hidden-import=uvicorn.protocols.http.h11_impl \
    --hidden-import=uvicorn.protocols.websockets.websockets_impl \
    --hidden-import=uvicorn.lifespan.on \
    --collect-all langgraph \
    --collect-all mcp \
    core/server/__main__.py

cp "dist/agents-core" "$bin_dir/agents-core-$triple"
echo "Sidecar ready: $bin_dir/agents-core-$triple"
