"""Speech-to-text — a pluggable seam, not a hardcoded cloud dependency.

The /stt endpoint hands raw audio bytes here. Default backend is local faster-whisper
(install the optional extra: `pip install -e .[stt]`), which keeps audio on-device and
works offline — a good fit for Hebrew input on a desktop app. If the backend is disabled
or the package isn't installed, transcribe() returns a clear, actionable error instead of
guessing.

To use a different backend (e.g. a hosted Whisper-compatible endpoint), implement another
branch in transcribe() keyed on stt.backend in config/default.yaml.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from core.security.secrets import load_config


@dataclass
class Transcript:
    text: str
    language: str | None = None
    backend: str = ""


_model_cache: dict = {}


def _cfg() -> dict:
    return (load_config().get("stt", {}) or {})


def transcribe(audio_bytes: bytes, *, filename: str = "audio.webm") -> Transcript:
    cfg = _cfg()
    backend = cfg.get("backend", "local")
    if backend == "disabled":
        raise RuntimeError("STT is disabled (config: stt.backend).")
    if backend == "local":
        return _transcribe_local(audio_bytes, filename, cfg)
    raise RuntimeError(f"unknown stt.backend '{backend}'")


def _transcribe_local(audio_bytes: bytes, filename: str, cfg: dict) -> Transcript:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Run `pip install -e .[stt]` "
            "(also requires ffmpeg on PATH)."
        ) from exc

    size = cfg.get("model", "base")
    model = _model_cache.get(size)
    if model is None:
        model = WhisperModel(size, device="cpu", compute_type="int8")
        _model_cache[size] = model

    suffix = Path(filename).suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        segments, info = model.transcribe(
            tmp.name, language=cfg.get("language") or None, vad_filter=True,
        )
        text = "".join(seg.text for seg in segments).strip()

    return Transcript(text=text, language=getattr(info, "language", None), backend="local")
