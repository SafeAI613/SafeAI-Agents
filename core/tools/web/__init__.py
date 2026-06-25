"""Web search tool — simple httpx-based DuckDuckGo search (see CLAUDE.md §11)."""

from core.tools.web.search import SearchResult, web_search

__all__ = ["SearchResult", "web_search"]
