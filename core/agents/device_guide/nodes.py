"""Node functions for the device-guide agent.

Flow: guard_input -> retrieve (RAG) -> answer. The answer is grounded strictly in the
chunks retrieved from the local corpus; all model I/O goes through the SafeAI proxy.
"""

from __future__ import annotations

from core.guardrails import policies
from core.guardrails.safeai_proxy import SafeAIProxy
from core.memory.short_term import build_messages
from core.providers.openrouter import BudgetExceeded, OpenRouterProvider
from core.runtime.state import AgentState
from core.tools.rag import LexicalIndex

SYSTEM_PROMPT = (
    "אתה עוזר שמסביר שימוש במכשירי חשמל ביתיים, על בסיס קטעי מדריך שמסופקים לך. "
    "ענה בעברית תקנית וברורה. השתמש אך ורק במידע מהקטעים שצורפו, ציין מאיזה דגם/מדריך "
    "המידע נלקח, ואם התשובה אינה בקטעים — אמור זאת ובקש את היצרן והדגם המדויקים. "
    "אל תמציא צעדים או קודי תקלה."
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


def retrieve(state: AgentState, *, index: LexicalIndex, top_k: int) -> dict:
    """RAG step: find the most relevant manual chunks for the user's question."""
    hits = index.search(state["user_input"], k=top_k)
    if not hits:
        return {"retrieved": "", "sources": []}
    blocks, sources = [], []
    for chunk, _score in hits:
        sources.append(chunk.doc)
        blocks.append(f"[מתוך: {chunk.doc}]\n{chunk.text}")
    return {"retrieved": "\n\n---\n\n".join(blocks), "sources": sorted(set(sources))}


def answer(state: AgentState, *, model: str, max_output_tokens: int,
           budget_tokens: int, mock: bool | None, skills_text: str = "") -> dict:
    """Produce a grounded answer from the retrieved chunks, via the guardrails proxy."""
    provider = OpenRouterProvider(model=model, max_output_tokens=max_output_tokens,
                                  budget_tokens=budget_tokens, mock=mock)
    proxy = SafeAIProxy(provider)

    ctx = state.get("retrieved", "")
    user = state["user_input"]
    if ctx:
        augmented = (f"שאלת המשתמש:\n{user}\n\n"
                     f"קטעים מהמדריכים (השתמש רק במידע מהם):\n{ctx}")
    else:
        augmented = (f"שאלת המשתמש:\n{user}\n\n"
                     "(לא נמצאו קטעים רלוונטיים במאגר המדריכים.)")

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
