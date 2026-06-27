"""Code execution sandbox.

runner.py — run_code(code, language, stdin, timeout) -> ExecResult.
Runs ONLY inside the Docker sandbox (infra/sandbox/Dockerfile) by default: no network,
read-only root, tmpfs workdir, dropped caps, memory + time caps. Authorized through the
permission broker; host execution is opt-in and discouraged.
"""

from core.tools.code_exec.runner import ExecResult, docker_available, run_code

__all__ = ["ExecResult", "run_code", "docker_available"]
