"""Code execution — runs generated code inside an isolated sandbox.

Default and only safe path: a one-shot Docker container built from infra/sandbox/Dockerfile,
with no network, a read-only root, a tmpfs workdir, dropped capabilities, a memory cap and a
wall-clock timeout. The host filesystem is never mounted.

A host-subprocess fallback exists for environments without Docker, but it is OFF by default
and refused by the permission broker unless code_exec.allow_host is explicitly set — running
untrusted, model-generated code on the host is dangerous.

Public API:
    run_code(code, language="python", stdin="", timeout=...) -> ExecResult
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from core.security.permissions import PermissionBroker, PermissionError_
from core.security.secrets import load_config

_IMAGE = "ai-agents-sandbox:latest"
_LANG_CMD = {
    "python": ["python", "-I", "/work/main.py"],
    "bash": ["bash", "/work/main.sh"],
    "node": ["node", "/work/main.js"],
}
_LANG_FILE = {"python": "main.py", "bash": "main.sh", "node": "main.js"}


@dataclass
class ExecResult:
    ok: bool
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    backend: str            # "docker" | "host" | "blocked"


def _cfg() -> dict:
    return (load_config().get("code_exec", {}) or {})


def _broker() -> PermissionBroker:
    c = _cfg()
    return PermissionBroker(allow_code_exec=bool(c.get("enabled", False)))


def docker_available() -> bool:
    return shutil.which("docker") is not None


def run_code(code: str, *, language: str = "python", stdin: str = "",
             timeout: int | None = None) -> ExecResult:
    """Execute `code` in the sandbox. Raises PermissionError_ if exec is disabled."""
    language = language.lower()
    if language not in _LANG_CMD:
        raise ValueError(f"unsupported language '{language}' (have {sorted(_LANG_CMD)})")

    c = _cfg()
    timeout = timeout or int(c.get("timeout_seconds", 20))
    broker = _broker()
    use_host = bool(c.get("allow_host", False)) and not docker_available()

    # broker decides: enabled at all? host allowed?
    broker.allow_code_exec = bool(c.get("enabled", False))
    broker.authorize_code_exec(on_host=use_host)

    if docker_available():
        return _run_docker(code, language, stdin, timeout,
                           mem=str(c.get("memory", "256m")))
    if use_host:
        return _run_host(code, language, stdin, timeout)
    raise PermissionError_(
        "Docker is not available and host execution is disabled. "
        "Install Docker (recommended) or set code_exec.allow_host: true."
    )


def _write_program(workdir: Path, language: str, code: str) -> None:
    (workdir / _LANG_FILE[language]).write_text(code, encoding="utf-8")


def _run_docker(code: str, language: str, stdin: str, timeout: int,
                mem: str) -> ExecResult:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        _write_program(work, language, code)
        cmd = [
            "docker", "run", "--rm", "-i",
            "--network", "none",
            "--memory", mem, "--cpus", "1",
            "--pids-limit", "128",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--read-only",
            "--tmpfs", "/tmp:rw,size=64m",
            "-v", f"{work}:/work:ro",
            "-w", "/work",
            _IMAGE,
            *_LANG_CMD[language],
        ]
        try:
            proc = subprocess.run(
                cmd, input=stdin, capture_output=True, text=True,
                timeout=timeout + 5,    # outer guard; container also self-limits
            )
        except subprocess.TimeoutExpired as exc:
            return ExecResult(False, exc.stdout or "", "execution timed out", -1,
                              True, "docker")
        return ExecResult(proc.returncode == 0, proc.stdout, proc.stderr,
                          proc.returncode, False, "docker")


def _run_host(code: str, language: str, stdin: str, timeout: int) -> ExecResult:
    """Host fallback — NO isolation. Only reached when explicitly allowed in config."""
    interp = {"python": ["python", "-I"], "bash": ["bash"], "node": ["node"]}[language]
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        _write_program(work, language, code)
        try:
            proc = subprocess.run(
                [*interp, str(work / _LANG_FILE[language])],
                input=stdin, capture_output=True, text=True, timeout=timeout, cwd=tmp,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(False, "", "execution timed out", -1, True, "host")
        return ExecResult(proc.returncode == 0, proc.stdout, proc.stderr,
                          proc.returncode, False, "host")
