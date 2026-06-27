"""Node functions for the workbench agent.

This is the tool-using reference agent. Flow:

    guard_input -> (blocked? END : agent_loop) -> END

`agent_loop` runs a bounded tool-calling loop:
    model turn -> if it requests tool calls, execute them (MCP tools or code-exec),
    feed results back, repeat -> until the model answers with no tool call, or max_iters.

Every tool call is:
  * executed through the permission broker (MCP connect-time gating; code-exec switch),
  * emitted as a trace step (tracer.node_start/node_end) so it shows up live in the
    StepInspector exactly like a graph node,
  * recorded in state['tool_calls'] for the UI's tool log.

Output is run through local output policies (same contract as SafeAIProxy). Tool turns
themselves are not yet wrapped by SafeAIProxy — that's a clean future extension.
"""

from __future__ import annotations

import json

from core.guardrails import policies
from core.memory.short_term import build_messages
from core.providers.openrouter import BudgetExceeded, OpenRouterProvider
from core.runtime.events import Tracer
from core.runtime.state import AgentState
from core.tools.code_exec import run_code
from core.tools.mcp import get_manager, tool_id_from_openai_name, tools_as_openai_schema

SYSTEM_PROMPT = (
    "אתה עוזר-על שמריץ משימות במחשב של המשתמש. ענה בעברית תקנית וברורה. "
    "יש לך כלים: כלי MCP מחוברים (קבצים, ועוד) וכלי הרצת קוד בארגז-חול. "
    "השתמש בכלים כשצריך מידע עדכני, גישה לקבצים, או חישוב/הרצה — אל תמציא תוצאות. "
    "כשסיימת, החזר תשובה סופית מסכמת בעברית. אל תחשוף מפתחות או נתיבים רגישים."
)

# Built-in (non-MCP) local tool: run code in the sandbox.
CODE_EXEC_TOOL = {
    "type": "function",
    "function": {
        "name": "code_exec",
        "description": "הרצת קטע קוד בארגז-חול מבודד (ללא רשת). מחזיר stdout/stderr.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "הקוד להרצה"},
                "language": {"type": "string", "enum": ["python", "bash", "node"],
                             "default": "python"},
                "stdin": {"type": "string", "default": ""},
            },
            "required": ["code"],
        },
    },
}

_PREVIEW = 800   # chars of a tool result kept for the UI log


def _system_prompt(skills_text: str) -> str:
    return SYSTEM_PROMPT + ("\n\n" + skills_text if skills_text else "")


def guard_input(state: AgentState) -> dict:
    res = policies.check_input(state.get("user_input", ""))
    if not res.ok:
        return {"blocked": True, "block_reason": res.reason,
                "final_answer": "לא ניתן לעבד את הבקשה (הקלט לא תקין). נסי לנסח מחדש."}
    return {"blocked": False}


def _available_tools() -> list[dict]:
    return tools_as_openai_schema() + [CODE_EXEC_TOOL]


def _execute_tool(name: str, args: dict) -> tuple[str, bool]:
    """Run one tool call. Returns (result_text, ok). Errors are returned, not raised,
    so the model can see and recover from them."""
    try:
        if name == "code_exec":
            res = run_code(args.get("code", ""),
                           language=args.get("language", "python"),
                           stdin=args.get("stdin", ""))
            body = res.stdout or ""
            if res.stderr:
                body += ("\n[stderr]\n" + res.stderr)
            tag = "" if res.ok else f"[exit {res.exit_code}{' timeout' if res.timed_out else ''}] "
            return (tag + body).strip() or "(no output)", res.ok
        tool_id = tool_id_from_openai_name(name)
        out = get_manager().call_tool(tool_id, args)
        return out or "(empty result)", not out.startswith("[tool error]")
    except Exception as exc:
        return f"[error] {exc}", False


def agent_loop(state: AgentState, *, model: str, max_output_tokens: int,
               budget_tokens: int, mock: bool | None, skills_text: str,
               tracer: Tracer, max_iters: int = 6) -> dict:
    provider = OpenRouterProvider(model=model, max_output_tokens=max_output_tokens,
                                  budget_tokens=budget_tokens, mock=mock)
    tools = _available_tools()
    messages = build_messages(_system_prompt(skills_text), state["user_input"],
                              state.get("history"))
    print("### messages", messages)

    used = (state.get("usage", {}).get("input_tokens", 0)
            + state.get("usage", {}).get("output_tokens", 0))
    usage = dict(state.get("usage", {}))
    tool_log: list[dict] = list(state.get("tool_calls", []) or [])
    final_text = ""

    for _ in range(max_iters):
        try:
            turn = provider.complete_with_tools(messages, tools, used_tokens=used)
            print("### turn", turn)
        except BudgetExceeded as exc:
            return {"blocked": True, "block_reason": str(exc),
                    "final_answer": "הבקשה חרגה מתקציב הטוקנים.", "tool_calls": tool_log}
        except e:
            print("### ", e)
        used += turn.input_tokens + turn.output_tokens
        usage["input_tokens"] = usage.get("input_tokens", 0) + turn.input_tokens
        usage["output_tokens"] = usage.get("output_tokens", 0) + turn.output_tokens

        if not turn.tool_calls:
            final_text = turn.text
            break

        messages.append(turn.raw_message)
        for call in turn.tool_calls:
            step = f"tool:{tool_id_from_openai_name(call.name)}"
            started = tracer.node_start(step)
            result, ok = _execute_tool(call.name, call.arguments)
            tracer.node_end(step, started, ok=ok,
                            info={"args": list(call.arguments.keys())})
            tool_log.append({
                "tool": tool_id_from_openai_name(call.name),
                "arguments": call.arguments,
                "result": result[:_PREVIEW],
                "ok": ok,
            })
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    else:
        final_text = final_text or "הגעתי למספר הצעדים המרבי בלי תשובה סופית."

    out = policies.check_output(final_text or "")
    if not out.ok:
        return {"blocked": True, "block_reason": out.reason,
                "final_answer": "התשובה נחסמה על ידי שכבת ה-guardrails.",
                "tool_calls": tool_log, "usage": usage}

    return {"draft_answer": final_text, "final_answer": final_text,
            "tool_calls": tool_log, "usage": usage}
