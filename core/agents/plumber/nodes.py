"""Node functions for the plumber agent.

Each node takes the running state and returns a *partial* update. Nodes stay small;
all model I/O goes through the SafeAI guardrails proxy, never the provider directly.
"""

from __future__ import annotations

from core.guardrails import policies
from core.guardrails.safeai_proxy import SafeAIProxy
from core.memory.short_term import build_messages
from core.providers.openrouter import BudgetExceeded, OpenRouterProvider
from core.runtime.state import AgentState

SYSTEM_PROMPT = (
    "אתה יועץ אינסטלציה מנוסה לבתים בישראל. ענה בעברית תקנית, ברורה ומעשית. "
    "אם חסרים פרטים על מקור הנזילה, סוג הברז, או הצנרת — פתח בשאלות הבהרה ממוקדות "
    "ורק אז תן הנחיות מותנות. כשמדובר בגז/חשמל/עבודה מורכבת — המלץ לפנות לבעל מקצוע. "
    "אל תמציא מידע ואל תשתמש במונחים שאינם קיימים; אם אינך בטוח, אמור זאת."
)


def _system_prompt(skills_text: str) -> str:
    if skills_text:
        return SYSTEM_PROMPT + "\n\n" + skills_text
    return SYSTEM_PROMPT


def guard_input(state: AgentState) -> dict:
    """Input guardrail as an explicit, traceable step."""
    res = policies.check_input(state.get("user_input", ""))
    if not res.ok:
        return {
            "blocked": True,
            "block_reason": res.reason,
            "final_answer": "לא ניתן לעבד את הבקשה (הקלט לא תקין). נסי לנסח מחדש.",
        }
    return {"blocked": False}


def generate(state: AgentState, *, model: str, max_output_tokens: int,
             budget_tokens: int, mock: bool | None, skills_text: str = "") -> dict:
    """Call the model through the SafeAI guardrails proxy and produce the answer."""
    provider = OpenRouterProvider(
        model=model,
        max_output_tokens=max_output_tokens,
        budget_tokens=budget_tokens,
        mock=mock,
    )
    proxy = SafeAIProxy(provider)

    messages = build_messages(_system_prompt(skills_text), state["user_input"],
                              state.get("history"))
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
        return {
            "blocked": True,
            "block_reason": result.reason,
            "final_answer": "התשובה נחסמה על ידי שכבת ה-guardrails.",
            "usage": usage,
        }

    return {
        "draft_answer": result.text,
        "final_answer": result.text,
        "usage": usage,
    }