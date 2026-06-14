"""Skills loader.

A Skill is a folder containing a SKILL.md with domain instructions/procedure that the
agent loads into its context (Anthropic-style Skills). Skills live under
    <agent_dir>/skills/<name>/SKILL.md
The loader is generic: any agent passes its own directory + the skill names from its
agent.yaml. Returns the concatenated skill text to inject into the system prompt.
"""

from __future__ import annotations

from pathlib import Path


def load_skills(base_dir: str | Path, names: list[str] | None) -> str:
    if not names:
        return ""
    chunks: list[str] = []
    for name in names:
        md = Path(base_dir) / "skills" / name / "SKILL.md"
        if md.exists():
            chunks.append(md.read_text(encoding="utf-8").strip())
    return "\n\n".join(chunks)