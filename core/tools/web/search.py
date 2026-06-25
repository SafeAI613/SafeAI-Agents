"""Lexical web search tool (DuckDuckGo).

This is the simple httpx-based web search anticipated in CLAUDE.md §11: a local tool
(plain Python function) that hits DuckDuckGo's HTML endpoint and returns structured
results. No browser, no API key, no extra dependency beyond httpx.

Design notes that match the rest of the codebase:
  * Every outbound request is authorized through a `PermissionBroker` (the single choke
    point for the domain allowlist) — exactly like the provider goes through the proxy.
  * A `mock` mode returns canned results with no network call, so the agent and its evals
    run offline / without flaky network (mirrors OpenRouterProvider's mock).
  * Failures fail *soft*: a transport error or an empty page returns `[]` rather than
    raising, so a search hiccup degrades the bulletin instead of bricking the agent.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx

from core.security.permissions import PermissionBroker

# DuckDuckGo's no-JS HTML endpoint. `df` is the time filter (d=day, w=week, m=month).
_DDG_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}

# anchor + snippet blocks in the returned HTML
_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
    re.DOTALL,
)
_SNIPPET_RE = re.compile(
    r'<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>', re.DOTALL
)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def _clean(raw: str) -> str:
    """Strip HTML tags + unescape entities + collapse whitespace."""
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub("", raw))).strip()


def _unwrap(href: str) -> str:
    """DDG wraps result links as //duckduckgo.com/l/?uddg=<encoded>. Unwrap to the real URL."""
    if "uddg=" in href:
        qs = parse_qs(urlparse(href).query)
        if qs.get("uddg"):
            return qs["uddg"][0]
    return href


def web_search(
    query: str,
    *,
    broker: PermissionBroker,
    max_results: int = 6,
    recency: str | None = "w",
    mock: bool | None = None,
) -> list[SearchResult]:
    """Search the web and return up to `max_results` results.

    `recency`: DuckDuckGo time filter — 'd' (day), 'w' (week), 'm' (month), or None.
    `broker`:  authorizes the request domain before any network call is made.
    `mock`:    when True, return canned results without touching the network.
    """
    if mock:
        return _mock_results(query, max_results)

    broker.authorize_url(_DDG_URL)

    data = {"q": query}
    if recency:
        data["df"] = recency

    try:
        with httpx.Client(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
            resp = client.post(_DDG_URL, data=data)
            resp.raise_for_status()
            page = resp.text
    except Exception:
        return []  # fail soft — the agent reports "could not fetch news"

    snippets = _SNIPPET_RE.findall(page)
    results: list[SearchResult] = []
    for i, m in enumerate(_RESULT_RE.finditer(page)):
        title = _clean(m.group("title"))
        url = _unwrap(html.unescape(m.group("href")))
        snippet = _clean(snippets[i]) if i < len(snippets) else ""
        if title and url:
            results.append(SearchResult(title=title, url=url, snippet=snippet))
        if len(results) >= max_results:
            break
    return results


def _mock_results(query: str, max_results: int) -> list[SearchResult]:
    """Canned results so the agent + evals run offline (mirrors the provider's mock)."""
    base = [
        SearchResult(
            title="[MOCK] Anthropic מציגה את Claude Opus 4.8",
            url="https://example.com/news/claude-opus-4-8",
            snippet="הדגם החדש משפר ביצועים במשימות סוכן ובכתיבת קוד; זמין דרך ה-API.",
        ),
        SearchResult(
            title="[MOCK] מודל קוד-פתוח חדש עוקף benchmarks",
            url="https://example.com/news/open-model",
            snippet="שוחרר מודל משקלים-פתוחים שמתחרה בדגמים מסחריים במבחני הסקה.",
        ),
        SearchResult(
            title="[MOCK] רגולציית AI: עדכון רגולטורי השבוע",
            url="https://example.com/news/ai-regulation",
            snippet="רשויות פרסמו טיוטת הנחיות חדשות לשקיפות מודלים גנרטיביים.",
        ),
    ]
    note = SearchResult(
        title=f"[MOCK] תוצאות הדגמה עבור: {query[:60]}",
        url="https://example.com/mock",
        snippet="זו תוצאת mock — ללא גישת רשת. להפעלת חיפוש אמיתי הרץ בלי --mock.",
    )
    return ([note] + base)[:max_results]
