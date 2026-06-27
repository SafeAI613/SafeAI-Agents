# Sandbox image for code execution. Minimal, no extra packages, no network at run time.
# Build once:  docker build -t ai-agents-sandbox:latest infra/sandbox
FROM python:3.12-slim

# A non-root user; the container is also run with --read-only + --cap-drop ALL.
RUN useradd --create-home --uid 10001 sandbox \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

USER sandbox
WORKDIR /work

# No ENTRYPOINT: the runner passes the exact command (python -I /work/main.py, etc).
