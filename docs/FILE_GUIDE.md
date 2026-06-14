# FILE_GUIDE — מפת הקבצים החשובים

מסמך התמצאות לפרויקט. עבור כל קובץ: מה תפקידו, ומתי תיגעי בו. מסומן **[ממומש]** /
**[stub]** כדי שתדעי מה עובד ומה שמור לעתיד.

---

## נקודות כניסה

### `core/cli.py` [ממומש]
הדרך להריץ אג'נט. תומך בשאלה בודדת, ב-`--chat` (לולאה רב-תורית), וב-`--list`.
מדפיס step-inspector (node + timing), תשובה, וספירת טוקנים.
**תיגעי בו** כדי לשנות חוויית ההרצה ב-CLI.

### `core/server/app.py` [ממומש]
FastAPI sidecar — ה-seam שאליו יתחבר ה-UI (Tauri). Endpoints: `GET /agents`,
`POST /run`, `WS /ws/run` (stream של אירועי nodes בזמן אמת).
**תיגעי בו** כשתחברי UI או תוסיפי endpoints.

### `core/__init__.py` [ממומש] — חשוב לסביבה שלך
רץ אוטומטית בכל ייבוא של החבילה ומגדיר TLS לעבודה מאחורי נטפרי (truststore → cert store
של Windows; fallback שמרכך את בדיקת ה-keyUsage). כיבוי: AGENTS_NO_TLS_FIX=1.
**בדרך כלל לא תיגעי בו** — הוא פשוט גורם לרשת לעבוד מאחורי המסנן.

---

## הליבה הגנרית — `core/runtime/` [ממומש]

מנוע שמריץ כל אג'נט. **אג'נט-אגנוסטי — אין כאן לוגיקה ספציפית לאג'נט.**

- `orchestrator.py` — `run_agent(agent, user_input, history=...)` מריץ את הגרף, עוטף כל
  node ב-tracing, ומחזיר את ה-state הסופי + ה-trace. `traced()` הוא העוטף.
- `state.py` — סכמת ה-state המשותפת (`AgentState`). שדות עיקריים: user_input,
  messages, history (רב-תורי), draft_answer, final_answer, blocked,
  retrieved+sources (ל-RAG), usage, trace.
  **תיגעי בו** כשאג'נט חדש צריך שדה state חדש.
- `events.py` — `Tracer` שאוסף אירועי node (start/end + timing). מזין את ה-inspector
  ואת ה-WS.

---

## האג'נטים — `core/agents/`

### `registry.py` [ממומש] — כאן מוסיפים אג'נט
ממפה שם → factory. ה-CLI/השרת/ה-evals מגלים אג'נטים רק דרך הקובץ הזה.

### דפוס האג'נט: `<agent>/graph.py` + `nodes.py` + `agent.yaml`
- `agent.yaml` — קונפיג דקלרטיבי: model, max_output_tokens, budget_tokens,
  tools, skills, guardrails. **הוספת/שינוי אג'נט = עריכת YAML, לא הרצת קוד.**
- `graph.py` — בונה את ה-LangGraph workflow (nodes, edges, conditional routing,
  checkpointer). טוען skills/קורפוס פעם אחת בייבוא.
- `nodes.py` — פונקציות השלבים. כל node מקבל state ומחזיר עדכון חלקי. כל I/O למודל
  עובר דרך SafeAIProxy, לעולם לא ישירות ל-provider.

### `plumber/` [ממומש] — אג'נט ייחוס (Q&A)
גרף: guard_input → generate. משתמש בסקיל israeli-plumbing. הכי פשוט — בלי כלים.

### `device_guide/` [ממומש] — אג'נט RAG
גרף: guard_input → retrieve → answer. retrieve מאחזר מהקורפוס המקומי, answer
מבסס את התשובה על הקטעים שאוחזרו.
- `corpus/` — **קובצי המדריכים** (md/txt/pdf). כרגע שני מדריכי דוגמה. **החליפי בשלך.**
- `skills/device-manuals/SKILL.md` — מורה לאג'נט לבסס על המקורות בלבד, לצטט מקור, ולבקש
  דגם אם חסר.

---

## הכלים — `core/tools/`

### `skills/` [ממומש]
load_skills(agent_dir, names) טוען SKILL.md מ-`<agent>/skills/<name>/` ומזריק ל-prompt.
דומה ל-RAG ברעיון (הזרקת טקסט ל-context), אבל סטטי וידוע מראש.

### `rag/store.py` [ממומש]
לב ה-RAG: chunk_text (פיצול לפי פסקאות), load_corpus (טוען md/txt/**pdf**),
extract_pdf_text (pypdf), ו-LexicalIndex (אחזור BM25, פייתון טהור).
**תיגעי בו** כדי: לשנות chunking, להוסיף פורמטים, או — בעתיד — להחליף LexicalIndex
באינדקס embeddings סמנטי (בלי לגעת באג'נט).

### `mcp/`, `code_exec/`, `browser/` [stub]
מתועדים אך לא ממומשים. כל אחד יתחבר כשיהיה אג'נט שזקוק לו.
(החלטת ארכיטקטורה: טולס מקומיים כברירת מחדל; MCP רק בקצוות — צריכת שרת קיים, בידוד
יכולת מסוכנת, או חשיפת יכולת לשימוש חוזר.)

---

## Guardrails — `core/guardrails/` [ממומש]
- `safeai_proxy.py` — **כל I/O למודל עובר כאן.** עוטף את ה-provider, מריץ קלט ופלט דרך
  policies מקומיים, ויש hook ל-gateway של SafeAI (כבוי כברירת מחדל; מפעילים ב-config).
- `policies.py` — בדיקות מקומיות זולות (קלט/פלט ריק, אורך).

## Provider — `core/providers/openrouter.py` [ממומש]
ה-client היחיד למודל. תומך budget cap (BudgetExceeded) ומצב mock (נופל אליו אם אין
מפתח). **הערה:** ה-mock נשאר לנוחות הרצה ללא מפתח; אם הוא מפריע אפשר להסירו.

## Memory — `core/memory/short_term.py` [ממומש]
build_messages(system, user_input, history) — בונה את רשימת ההודעות כולל היסטוריה
רב-תורית. (long-term/semantic memory — עתידי.)

## Security — `core/security/` [ממומש בסיסי]
- `permissions.py` — PermissionBroker עם domain allowlist ו-authorize_url/fs. ייכנס
  לפעולה כשיהיה כלי רשת/קבצים (למשל חיפוש אינטרנט).
- `secrets.py` — קריאת מפתחות מ-env + טעינת config/default.yaml.

## Observability — `core/observability/tracing.py` [stub]
ה-Tracer כבר אוסף timing; הקובץ הזה הוא ה-seam לייצוא ל-LangSmith/OTel (no-op כרגע).

---

## Evals — `evals/` [ממומש]
- `runner.py` — מריץ אג'נט מול dataset, מנקד מול checks. תומך **תרחישים רב-תוריים**
  (turns) שנושאים היסטוריה, ובדיקות per-turn. CI-friendly (exit code).
- `suites/<agent>.py` — פונקציות הבדיקה לאותו אג'נט.
- `datasets/<agent>.yaml` — קלטים + checks.

---

## קונפיג ותלויות

- `config/default.yaml` — provider, budgets, toggle ל-SafeAI, domain allowlist.
- `pyproject.toml` — תלויות (langgraph, httpx, pydantic, pyyaml, fastapi, uvicorn,
  python-dotenv, truststore, pypdf). התקנה: pip install -e .
- `.env.example` — תבנית למפתח.
- `CLAUDE.md` — המסמך המייסד; מתאר את הארכיטקטורה המלאה והעקרונות (כולל שכבות שעוד לא
  מומשו). שימי לב: נכתב כתכנון-יעד, אז חלקים ממנו עדיין stubs בקוד.

---

## הוספת אג'נט חדש (צ'ק-ליסט)

1. צרי `core/agents/<name>/` עם graph.py, nodes.py, agent.yaml.
2. הגדירי state נדרש (הוסיפי שדות ל-runtime/state.py אם צריך).
3. רשמי factory ב-core/agents/registry.py.
4. אם צריך ידע תחום → הוסיפי skills/<name>/SKILL.md ורשמי ב-agent.yaml.
5. אם צריך אחזור → השתמשי ב-tools/rag + תיקיית corpus/.
6. הוסיפי evals/suites/<name>.py + evals/datasets/<name>.yaml.
7. האג'נט "מוכן" כשהוא עובר את ה-eval suite שלו.

## הזרימה מקצה לקצה (לזכור)
cli/server → run_agent (orchestrator) → graph של האג'נט → nodes → SafeAIProxy →
OpenRouter, כשה-Tracer אוסף timing בכל שלב וה-state נושא את התוצאה.