# Code-exec sandbox

Build the image before using the code-exec tool:

```bash
docker build -t ai-agents-sandbox:latest infra/sandbox
```

The runner (`core/tools/code_exec/runner.py`) starts one ephemeral container per run with:
`--network none --read-only --cap-drop ALL --security-opt no-new-privileges`,
a memory cap, a pids limit, a tmpfs `/tmp`, and the program mounted read-only at `/work`.
The host filesystem is never mounted. Enable execution in `config/default.yaml` →
`code_exec.enabled: true`.
