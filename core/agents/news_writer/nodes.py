"""Node functions for the news_writer agent.

Flow: guard_input -> fetch_news (web tool) -> write_bulletin. Structurally this mirrors
the device_guide RAG agent, but the "retrieval" is a live web search instead of a local
corpus: fetch_news fills state["retrieved"] + state["sources"], and write_bulletin is
grounded strictly on those results. All model I/O goes through the SafeAI proxy.
"""

from __future__ import annotations

from core.guardrails import policies
from core.guardrails.safeai_proxy import SafeAIProxy
from core.memory.short_term import build_messages
from core.providers.openrouter import BudgetExceeded, OpenRouterProvider
from core.runtime.state import AgentState
from core.security.permissions import PermissionBroker
from core.tools.web import web_search

SYSTEM_PROMPT = (
    "אתה כתב טכנולוגיה שמנסח הודעות חדשותיות בעברית על חידושים בתחום ה-AI. "
    "אתה כותב אך ורק על סמך תוצאות החיפוש שמצורפות לך, מציין מקור לכל ידיעה, "
    "ואם לא סופקו תוצאות — אומר זאת בכנות ולא ממציא חדשות."
)


def _system_prompt(skills_text: str) -> str:
    return SYSTEM_PROMPT + ("\n\n" + skills_text if skills_text else "")


def guard_input(state: AgentState) -> dict:
    res = policies.check_input(state.get("user_input", ""))
    if not res.ok:
        return {
            "blocked": True,
            "block_reason": res.reason,
            "final_answer": "לא ניתן לעבד את הבקשה (הקלט לא תקין). נסי לנסח מחדש.",
        }
    return {"blocked": False}


def fetch_news(state: AgentState, *, broker: PermissionBroker, max_results: int,
               recency: str | None, query_suffix: str, mock: bool | None) -> dict:
    """Web-search step: pull fresh AI items for the user's topic."""
    topic = state["user_input"].strip()
    query = f"{topic} {query_suffix}".strip()

    results = web_search(query, broker=broker, max_results=max_results,
                         recency=recency, mock=mock)
    if not results:
        return {"retrieved": "", "sources": []}

    blocks, sources = [], []
    for i, r in enumerate(results, start=1):
        sources.append(r.url)
        blocks.append(f"[{i}] {r.title}\n{r.snippet}\nמקור: {r.url}")
    return {"retrieved": "\n\n".join(blocks), "sources": sources}


def write_bulletin(state: AgentState, *, model: str, max_output_tokens: int,
                   budget_tokens: int, mock: bool | None, skills_text: str = "") -> dict:
    """Compose the news bulletin grounded in the fetched results, via the guardrails proxy."""
    provider = OpenRouterProvider(model=model, max_output_tokens=max_output_tokens,
                                  budget_tokens=budget_tokens, mock=mock)
    proxy = SafeAIProxy(provider)

    topic = state["user_input"].strip()
    ctx = state.get("retrieved", "")
    if ctx:
        augmented = (
            f"נושא ההודעה: {topic}\n\n"
            f"תוצאות חיפוש (כתוב רק על סמך אלו, וצטט מקור לכל ידיעה):\n{ctx}"
        )
    else:
        augmented = (
            f"נושא ההודעה: {topic}\n\n"
            "(החיפוש לא החזיר תוצאות. אמור למשתמש בכנות שלא נמצאו ידיעות עדכניות "
            "ושכדאי לנסות שוב או לחדד את הנושא — אל תמציא חדשות.)"
        )

    messages = build_messages(_system_prompt(skills_text), augmented, state.get("history"))
    used = state.get("usage", {}).get("input_tokens", 0) + \
        state.get("usage", {}).get("output_tokens", 0)

    try:
        result = proxy.complete(messages, used_tokens=used)
    except BudgetExceeded as exc:
        return {"blocked": True, "block_reason": str(exc),
                "final_answer": "הבקשה חרגה מתקציב הטוקנים שהוגדר לאג'נט."}

    usage = dict(state.get("usage", {}))
    if result.completion:
        usage["input_tokens"] = usage.get("input_tokens", 0) + result.completion.input_tokens
        usage["output_tokens"] = usage.get("output_tokens", 0) + result.completion.output_tokens

    if result.blocked:
        return {"blocked": True, "block_reason": result.reason,
                "final_answer": "התשובה נחסמה על ידי שכבת ה-guardrails.", "usage": usage}

    return {"draft_answer": result.text, "final_answer": result.text, "usage": usage}
