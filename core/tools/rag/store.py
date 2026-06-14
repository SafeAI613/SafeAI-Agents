"""Local RAG store — lexical retrieval (BM25), pure Python, no dependencies.

This is the minimal, offline, Netfree-proof starting point: ingest a small corpus of
manuals, split into chunks, and retrieve the most relevant chunks for a query using
BM25. The retrieval function is intentionally isolated — later you can swap BM25 for
vector embeddings without touching the agent.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

# matches Latin, Hebrew, and digit runs as tokens
_TOKEN = re.compile(r"[A-Za-z\u0590-\u05FF0-9]+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def chunk_text(text: str, max_chars: int = 700) -> list[str]:
    """Split on blank lines into paragraphs, then merge paragraphs up to max_chars.
    Keeps manual sections intact rather than cutting mid-sentence."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in paras:
        if cur and len(cur) + len(p) + 2 > max_chars:
            chunks.append(cur)
            cur = p
        else:
            cur = (cur + "\n\n" + p) if cur else p
    if cur:
        chunks.append(cur)
    return chunks


@dataclass
class Chunk:
    doc: str
    text: str
    tokens: list[str] = field(default_factory=list)


def load_corpus(corpus_dir: str | Path) -> list[Chunk]:
    """Load .md/.txt files from a directory into tokenized chunks."""
    chunks: list[Chunk] = []
    for path in sorted(Path(corpus_dir).glob("*")):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8")
        for c in chunk_text(text):
            chunks.append(Chunk(doc=path.stem, text=c, tokens=tokenize(c)))
    return chunks


class LexicalIndex:
    """BM25 index over chunks."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.N = len(chunks)
        self.df: dict[str, int] = {}
        self.doc_len: list[int] = []
        for c in chunks:
            self.doc_len.append(len(c.tokens))
            for t in set(c.tokens):
                self.df[t] = self.df.get(t, 0) + 1
        self.avgdl = (sum(self.doc_len) / self.N) if self.N else 0.0

    def _idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1 + (self.N - n + 0.5) / (n + 0.5))

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        q = set(tokenize(query))
        scored: list[tuple[float, int]] = []
        for i, c in enumerate(self.chunks):
            tf: dict[str, int] = {}
            for t in c.tokens:
                tf[t] = tf.get(t, 0) + 1
            dl = self.doc_len[i] or 1
            score = 0.0
            for t in q:
                if t not in tf:
                    continue
                idf = self._idf(t)
                num = tf[t] * (self.k1 + 1)
                den = tf[t] + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                score += idf * num / den
            if score > 0:
                scored.append((score, i))
        scored.sort(reverse=True)
        return [(self.chunks[i], s) for s, i in scored[:k]]
