# CONTRIBUTING — הוספת אג'נטים

מדריך למתכנתים שתורמים אג'נטים חדשים. קראו קודם את `docs/FILE_GUIDE.md` (מפת קבצים)
ואת `CLAUDE.md` (החלטות ארכיטקטורה). מסמך זה מתמקד ב**איך מוסיפים אג'נט נכון**.

---

## עקרונות שלא מתפשרים עליהם

1. **אג'נט = `graph.py` + `agent.yaml`** (+ אופציונלית `skills/`, `corpus/`).
   אין לוגיקת אג'נט ב-`core/runtime/` — הוא מנוע גנרי. אל תיגעו בו.
2. **כל I/O למודל עובר דרך `SafeAIProxy`.** לעולם לא קוראים ל-provider ישירות מתוך node.
3. **config over code.** model, budgets, tools, skills — ב-`agent.yaml`, לא בקוד.
4. **טולס מקומיים כברירת מחדל.** MCP/embeddings/browser רק אם האג'נט באמת זקוק להם.
5. **secrets מ-env בלבד** (`core/security/secrets.py`, `.env`). אף פעם לא בקוד או ב-YAML.
   משתני סביבה נדרשים: `OPENROUTER_API_KEY`, `MONGODB_URI`, `JWT_SECRET`.
6. **אג'נט מוכן רק כשהוא עובר eval suite משלו.**

---

## אנטומיה של אג'נט

```
core/agents/<name>/
  __init__.py
  agent.yaml        קונפיג דקלרטיבי
  graph.py          מגדיר את ה-LangGraph workflow + class האג'נט
  nodes.py          פונקציות השלבים (כל אחת: state -> partial update)
  skills/<skill>/SKILL.md   (אופציונלי) ידע תחום שמוזרק ל-prompt
  corpus/                    (אופציונלי, לאג'נטי RAG) קובצי md/txt/pdf
```

### חוזה ה-class (ב-`graph.py`)
האג'נט חייב לחשוף:
- `name: str` — מזהה ייחודי (תואם ל-`name` ב-agent.yaml).
- `build(tracer) -> compiled_graph` — בונה ומקמפל את הגרף (עם `MemorySaver`).
- factory `make_agent(mock=None)` ברמת המודול.

ה-`registry` קורא ל-`make_agent(mock=...)`, ו-`run_agent` קורא ל-`.name` ו-`.build()`.

---

## צ'ק-ליסט להוספת אג'נט

1. צרו `core/agents/<name>/` עם `__init__.py`, `agent.yaml`, `graph.py`, `nodes.py`.
2. אם צריך שדה state חדש — הוסיפו אותו ל-`core/runtime/state.py` (`AgentState`).
3. רשמו factory ב-`core/agents/registry.py`.
4. ידע תחום? הוסיפו `skills/<skill>/SKILL.md` ורשמו ב-`agent.yaml` תחת `skills:`.
5. אחזור? השתמשו ב-`core/tools/rag` + תיקיית `corpus/`.
6. הוסיפו `evals/suites/<name>.py` + `evals/datasets/<name>.yaml`.
7. הריצו: `python -m core.cli --agent <name> "..."`, `python -m evals.runner --suite <name>`, `pytest`.
   לבדיקת endpoints: `uvicorn core.server.app:app --reload` (דורש `.env` עם `MONGODB_URI` ו-`JWT_SECRET`).
8. ודאו שה-eval עובר לפני פתיחת PR.

---

## דוגמה מלאה: אג'נט `echo` מינימלי

הקטן ביותר שאפשר — מדגים את החוזה. גרף: `guard_input → respond`.

**`core/agents/echo/agent.yaml`**
```yaml
name: echo
display_name: "הד"
description: "אג'נט הדגמה מינימלי."
model: "openrouter/free"
max_output_tokens: 300
budget_tokens: 1000
tools: []
skills: []
gates: []
guardrails:
  input: true
  output: true
```

**`core/agents/echo/nodes.py`**
```python
from __future__ import annotations

from core.guardrails import policies
from core.guardrails.safeai_proxy import SafeAIProxy
from core.memory.short_term import build_messages
from core.providers.openrouter import OpenRouterProvider
from core.runtime.state import AgentState

SYSTEM_PROMPT = "אתה עוזר תמציתי. ענה במשפט אחד בעברית."


def guard_input(state: AgentState) -> dict:
    res = policies.check_input(state.get("user_input", ""))
    if not res.ok:
        return {"blocked": True, "block_reason": res.reason,
                "final_answer": "קלט לא תקין."}
    return {"blocked": False}


def respond(state: AgentState, *, model: str, max_output_tokens: int,
            budget_tokens: int, mock: bool | None) -> dict:
    provider = OpenRouterProvider(model=model, max_output_tokens=max_output_tokens,
                                  budget_tokens=budget_tokens, mock=mock)
    proxy = SafeAIProxy(provider)
    messages = build_messages(SYSTEM_PROMPT, state["user_input"], state.get("history"))
    result = proxy.complete(messages)
    if result.blocked:
        return {"blocked": True, "block_reason": result.reason,
                "final_answer": "נחסם על ידי guardrails."}
    return {"final_answer": result.text}
```

**`core/agents/echo/graph.py`**
```python
from __future__ import annotations

from functools import partial
from pathlib import Path

import yaml
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from core.agents.echo import nodes
from core.runtime.events import Tracer
from core.runtime.orchestrator import traced
from core.runtime.state import AgentState

_CFG = yaml.safe_load((Path(__file__).parent / "agent.yaml").read_text(encoding="utf-8"))


def _route(state: AgentState) -> str:
    return "END" if state.get("blocked") else "respond"


class EchoAgent:
    name = _CFG["name"]
    config = _CFG

    def __init__(self, mock: bool | None = None):
        self.mock = mock

    def build(self, tracer: Tracer):
        respond_node = partial(nodes.respond, model=_CFG["model"],
                               max_output_tokens=_CFG["max_output_tokens"],
                               budget_tokens=_CFG["budget_tokens"], mock=self.mock)
        g = StateGraph(AgentState)
        g.add_node("guard_input", traced("guard_input", nodes.guard_input, tracer))
        g.add_node("respond", traced("respond", respond_node, tracer))
        g.add_edge(START, "guard_input")
        g.add_conditional_edges("guard_input", _route,
                                {"respond": "respond", "END": END})
        g.add_edge("respond", END)
        return g.compile(checkpointer=MemorySaver())


def make_agent(mock: bool | None = None) -> EchoAgent:
    return EchoAgent(mock=mock)
```

**רישום ב-`core/agents/registry.py`**
```python
from core.agents.echo.graph import make_agent as make_echo
# ...
_REGISTRY = {
    "plumber": make_plumber,
    "device_guide": make_device_guide,
    "echo": make_echo,
}
```

זהו — `python -m core.cli --agent echo "שלום"` עובד.

לדפוסים מתקדמים יותר ראו אג'נטים קיימים: `plumber` (Skill + שאלות הבהרה),
`device_guide` (RAG: `guard_input → retrieve → answer`, grounding בקורפוס).

---

## כתיבת Skill

Skill הוא `SKILL.md` עם הוראות/ידע תחום שמוזרק ל-system prompt. שימו אותו ב-
`core/agents/<name>/skills/<skill>/SKILL.md` ורשמו את `<skill>` תחת `skills:` ב-agent.yaml.
כתבו אותו כהנחיות ברורות למודל (פרוצדורה, טרמינולוגיה, מתי לבקש פרטים, מתי לסרב).

## אג'נטי RAG

- שימו קובצי `.md`/`.txt`/`.pdf` ב-`corpus/`.
- ב-`graph.py` טענו פעם אחת: `LexicalIndex(load_corpus(corpus_dir))`.
- node `retrieve` ממלא `state["retrieved"]` + `state["sources"]`; node `answer` מבסס
  את התשובה רק על מה שאוחזר (grounding — חובה).
- אל תחליפו ל-embeddings לפני שהאחזור הלקסיקלי באמת מגביל; אם כן — מחליפים רק את
  `LexicalIndex` ב-`core/tools/rag/store.py`, בלי לגעת באג'נט.

---

## Evals (חובה)

כל אג'נט חייב suite. ה-runner תומך גם בתרחישים רב-תוריים (`turns`) שנושאים היסטוריה.

**`evals/datasets/<name>.yaml`** — רשימת `cases`, כל אחד `input` + `checks`
(או `turns` לרב-תורי). **`evals/suites/<name>.py`** — מילון `CHECKS` שממפה שם בדיקה →
פונקציה `(final_state, expected) -> (passed: bool, detail: str)`.

הריצו: `python -m evals.runner --suite <name>`. PR לא מתקבל אם ה-suite נכשל.

---

## קונבנציות קוד

- Python ‎3.10+‎, async/type hints, Pydantic לסכמות.
- nodes קטנים וטהורים ככל האפשר; side effects דרך כלים.
- כל node מחזיר עדכון state חלקי בלבד; מפתחות חייבים להיות מוגדרים ב-`AgentState`.
- בלי מפתחות/מודלים מקודדים. בלי לעקוף guardrails.
- הריצו `ruff check . && ruff format .` ו-`pytest` לפני PR.

## תהליך PR

1. אג'נט + skill (אם יש) + eval suite.
2. `pytest` ו-`evals.runner` ירוקים.
3. עדכנו את הטבלה ב-`README.md` עם האג'נט החדש.
4. תיאור ה-PR: מה האג'נט עושה, אילו כלים, ואיך ה-eval מכסה אותו.


**שאלות לפני PR? פנו ל-support@safeai613.com**
