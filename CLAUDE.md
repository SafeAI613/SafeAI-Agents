# CLAUDE.md

> מסמך הכוונה לאג'נט שעובד ב-repo הזה. משקף את **המצב הנוכחי בפועל** (לא תכנון-יעד).
> מסומן [ממומש] / [stub] כדי שתדע מה עובד ומה שמור לעתיד.

---

## 1. מה זה הפרויקט

מערכת סוכני AI כתוכנת desktop. כל אג'נט הוא **workflow מפורש** (LangGraph) עם שליטה על כל
שלב, עובר דרך **guardrails**, ומשתמש בכלים בסגנון Anthropic. ספק המודל: **OpenRouter**.

ארכיטקטורה: ליבת **Python** (FastAPI sidecar) שאליה יתחבר UI (Tauri) בעתיד. כרגע מריצים
דרך ה-CLI; השרת קיים כ-seam ל-UI. כל תעבורת המודל עוברת דרך guardrails לפני/אחרי.

## 2. מצב נוכחי — מה ממומש

- שני אג'נטים עובדים על אותו שלד:
  - `plumber` [ממומש] — Q&A, יועץ אינסטלציה ישראלי, כלי: Skill בלבד.
  - `device_guide` [ממומש] — RAG מעל קורפוס מקומי (md/txt/pdf), כלים: RAG + Skill.
- תשתית [ממומש]: orchestrator גנרי, tracing per-node, state משותף, לולאת שיחה רב-תורית,
  budget cap, guardrails (policies מקומיים + hook ל-SafeAI), eval harness (כולל רב-תורי).
- כלים: `skills/` [ממומש], `rag/` [ממומש]. `mcp/`, `code_exec/`, `browser/` [stub].
- אימות משתמשים [ממומש]: `core/auth/` — register/login, JWT, MongoDB Atlas, סטטיסטיקות.
- UI React [ממומש חלקי]: מסך Login + AgentSelect + Chat, מחובר לשרת דרך JWT.

## 3. החלטות ארכיטקטורה (מחייבות)

| נושא | הכרעה |
|------|--------|
| שפת ליבה | Python |
| orchestration | LangGraph (StateGraph, MemorySaver, conditional edges) |
| ספק | OpenRouter — נותן completions + tool calling בלבד; כל השאר ממומש כאן |
| **כלים** | **טולס מקומיים (פונקציות פייתון) כברירת מחדל. MCP רק בקצוות:** (א) צריכת שרת MCP קיים, (ב) בידוד יכולת מסוכנת, (ג) חשיפת יכולת לשימוש חוזר חוצה-קליינטים (כמו SafeAI) |
| RAG | אחזור לקסיקלי (BM25, פייתון טהור). embeddings סמנטיים = שדרוג עתידי, מחליפים רק את `LexicalIndex` |
| guardrails | כל I/O עובר דרך `SafeAIProxy`; policies מקומיים תמיד, SafeAI אופציונלי דרך config |
| מודל | מוגדר ב-`agent.yaml`. לעברית איכותית עדיף `anthropic/claude-sonnet-4.5` על פני `openrouter/free` |

עיקרון מנחה: **OpenRouter נותן רק טקסט. RAG/Skills/כלים — ממומשים כאן.** ועיקרון מורכבות:
לא מוסיפים שכבה (MCP, embeddings, browser) עד שיש אג'נט שבאמת זקוק לה.

## 4. מבנה ה-repo (בפועל)

```
core/
  __init__.py            תיקון TLS לנטפרי (truststore) — רץ בכל ייבוא
  cli.py                 הרצה: שאלה בודדת + --chat (רב-תורי) + --list
  server/app.py          FastAPI: /auth/register, /auth/login, /agents, /run, /ws/run
  auth/
    mongo.py             חיבור MongoDB Atlas (pymongo, singleton)
    models.py            סכמות Pydantic: UserRegister, UserLogin, TokenResponse
    service.py           register_user, login_user (bcrypt+JWT), record_usage
  agents/
    registry.py          רישום אג'נטים — נקודת ההוספה
    plumber/             graph.py + nodes.py + agent.yaml + skills/israeli-plumbing/
    device_guide/        + corpus/ (md/txt/pdf) + skills/device-manuals/
  runtime/
    orchestrator.py      run_agent + traced() — מנוע גנרי, אג'נט-אגנוסטי
    state.py             AgentState (user_input, history, retrieved, sources, usage, trace...)
    events.py            Tracer (per-node timing)
  tools/
    skills/   [ממומש]    load_skills — מזריק SKILL.md ל-prompt
    rag/      [ממומש]    store.py: chunk_text, load_corpus(md/txt/pdf), extract_pdf_text, LexicalIndex(BM25)
    mcp/ code_exec/ browser/   [stub]
  guardrails/
    safeai_proxy.py      כל I/O למודל עובר כאן (+ hook ל-SafeAI gateway)
    policies.py          בדיקות מקומיות
  memory/short_term.py   build_messages עם היסטוריה רב-תורית
  providers/openrouter.py client + budget cap (+ mock fallback ללא מפתח)
  security/              permissions (broker + allowlist) + secrets
  observability/tracing.py  [stub] seam ל-LangSmith/OTel
evals/                   runner (תומך turns רב-תוריים) + suites/ + datasets/
config/default.yaml      provider, budgets, SafeAI toggle, allowlist
docs/FILE_GUIDE.md       מפת קבצים מפורטת
```

## 5. מודל מנטלי

- **אג'נט = `graph.py` + `agent.yaml`** (+ אופציונלית `skills/`, `corpus/`). אין לוגיקת אג'נט ב-runtime.
- **`agent.yaml` דקלרטיבי**: model, max_output_tokens, budget_tokens, tools, skills, guardrails.
- **כל node מחזיר עדכון state חלקי.** כל I/O למודל דרך `SafeAIProxy`, לעולם לא ישירות ל-provider.
- **Skills ו-RAG דומים**: שניהם מזריקים טקסט ל-context. ההבדל: Skill סטטי וידוע מראש; RAG מאחזר דינמית מקורפוס.
- **טולס מקומיים** מספיקים לרוב; MCP רק כשצריך interop/בידוד/שימוש חוזר.

## 6. דפוסי הגרפים הקיימים

- plumber: `START → guard_input → (blocked? END : generate) → END`
- device_guide: `START → guard_input → (blocked? END : retrieve) → answer → END`

## 7. כללי עבודה

- async/Python מודרני, type hints, Pydantic לסכמות.
- כל node פולט אירוע start/end עם timing (מזין inspector + WS).
- UI עתידי: React, RTL (עברית).
- config over code: budgets/models/allowlists ב-YAML, לא בקוד.
- secrets מ-env בלבד (`security/secrets.py`); לעולם לא בקוד.
- כל תעבורת מודל דרך guardrails. אין לעקוף.
- TLS: `core/__init__.py` מטפל בנטפרי דרך truststore. דורש `pip install truststore`.

## 8. הוספת אג'נט חדש

1. `core/agents/<name>/` עם graph.py, nodes.py, agent.yaml.
2. הוסף שדות ל-`runtime/state.py` אם צריך.
3. רשום factory ב-`core/agents/registry.py`.
4. ידע תחום → `skills/<name>/SKILL.md` + רישום ב-agent.yaml.
5. אחזור → `tools/rag` + תיקיית `corpus/`.
6. `evals/suites/<name>.py` + `evals/datasets/<name>.yaml`.
7. האג'נט מוכן כשעובר את ה-eval suite שלו.

## 9. אל תעשה

- אל תקרא ל-OpenRouter מחוץ ל-`SafeAIProxy`.
- אל תוסיף לוגיקת אג'נט ל-`core/runtime` — הוא נשאר גנרי.
- אל תוסיף MCP/embeddings/browser בלי אג'נט שזקוק להם (מורכבות מיותרת).
- אל תקודד מפתחות/מודלים/budgets בקוד.
- אל תיתן ל-RAG agent לענות מחוץ למקורות שאוחזרו (grounding).

## 10. הרצה מהירה

```powershell
pip install -e .            # + pip install pypdf truststore
$env:OPENROUTER_API_KEY="sk-or-..."
$env:MONGODB_URI="mongodb+srv://..."   # MongoDB Atlas
$env:JWT_SECRET="..."                  # מחרוזת אקראית ארוכה
python -m core.cli --list
python -m core.cli --agent device_guide --chat
python -m evals.runner --suite plumber
uvicorn core.server.app:app --reload
# client: cd client && npm run dev
```

## 11. מה לא ממומש (כיוונים פתוחים)

- חיפוש אינטרנט (`tools/web/`) — נדון, מתוכנן כטול httpx פשוט (DuckDuckGo) עם fallback ב-device_guide.
- embeddings סמנטיים ל-RAG; long-term memory; UI (Tauri); ייצוא observability; code_exec/browser/mcp.