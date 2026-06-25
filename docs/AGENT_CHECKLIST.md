# צ'קליסט להוספת אג'נט חדש

צ'קליסט מעשי למפתחות שמוסיפות אג'נט למערכת. משקף את **כל השלבים שביצענו בפועל** בהוספת
אג'נט `news_writer` — כולל המהמורות האמיתיות שנתקלנו בהן. למדריך המלא ראו
[CONTRIBUTING.md](../CONTRIBUTING.md); לארכיטקטורה ראו [CLAUDE.md](../CLAUDE.md).

---

## 0. לפני שמתחילים — הבנה

- [ ] קראתי את `CLAUDE.md` (החלטות ארכיטקטורה) ואת `docs/FILE_GUIDE.md` (מפת קבצים).
- [ ] הבנתי שאג'נט = `graph.py` + `agent.yaml` (+ אופציונלית `skills/`, `corpus/`),
      ושאין לוגיקת אג'נט ב-`core/runtime/` — הוא מנוע גנרי.
- [ ] החלטתי מאיזו **תבנית** האג'נט שלי קרוב יותר:
  - Q&A טהור → תבנית `plumber` (`guard_input → generate`).
  - אחזור ידע → תבנית `device_guide` (`guard_input → retrieve → answer`).
  - (דוגמה: `news_writer` הוא תבנית RAG שבה ה"אחזור" הוא חיפוש אינטרנט חי במקום קורפוס.)

## 1. בחירת כלים (tools)

- [ ] בדקתי אם הכלי שאני צריכה כבר ממומש (`core/tools/`): `skills/` ו-`rag/` קיימים;
      `web/` קיים (חיפוש DuckDuckGo); `mcp/ code_exec/ browser/` הם stubs.
- [ ] אם אני צריכה כלי שעוד לא קיים — מימשתי אותו תחת `core/tools/<tool>/` כפונקציית
      פייתון מקומית (ברירת המחדל הארכיטקטונית; MCP רק בקצוות).
- [ ] כלי רשת/קבצים עובר דרך `PermissionBroker` (`core/security/permissions.py`) —
      זו נקודת החנק היחידה ל-allowlist.
- [ ] לכלי יש **מצב mock** וכשל "רך" (מחזיר ריק/קנד במקום לזרוק חריגה) — כדי שהאג'נט
      וה-evals ירוצו גם אופליין/בלי רשת. (כך נבנה `core/tools/web/search.py`.)

## 2. שלד האג'נט

- [ ] יצרתי `core/agents/<name>/` עם: `__init__.py`, `agent.yaml`, `nodes.py`, `graph.py`.
- [ ] `agent.yaml` דקלרטיבי: `name`, `display_name`, `description`, `model`,
      `max_output_tokens`, `budget_tokens`, `tools`, `skills`, `gates`, `guardrails`.
      קונפיג לכלי (למשל `web:` עם `max_results`/`recency`/`domain_allowlist`) — גם כאן, לא בקוד.
- [ ] `nodes.py`: כל node מקבל `state` ומחזיר **עדכון חלקי** בלבד. כל I/O למודל דרך
      `SafeAIProxy`, לעולם לא ישירות ל-provider.
- [ ] `graph.py`: בונה `StateGraph(AgentState)`, עוטף כל node ב-`traced(...)`, מגדיר edges
      ו-conditional routing, ומקמפל עם `MemorySaver()`. חושף `name`, `build(tracer)`,
      ו-factory `make_agent(mock=None)` ברמת המודול.
- [ ] טעינת skills/קורפוס/broker — **פעם אחת בייבוא** (ברמת המודול ב-`graph.py`), לא בכל ריצה.

## 3. state, ידע ורישום

- [ ] אם צריך שדה state חדש — הוספתי אותו ל-`core/runtime/state.py` (`AgentState`).
      (ל-`news_writer` הספיקו השדות הקיימים `retrieved` + `sources`.)
- [ ] ידע תחום → `skills/<skill>/SKILL.md` + רישום תחת `skills:` ב-`agent.yaml`.
      ב-SKILL כללי **ביסוס** מפורשים: לכתוב רק על סמך מה שסופק, ולא להמציא אם אין מקור.
- [ ] רשמתי את ה-factory ב-`core/agents/registry.py` (זו נקודת ההוספה היחידה).

## 4. Evals (חובה)

- [ ] יצרתי `evals/datasets/<name>.yaml` (cases עם `input` + `checks`).
- [ ] יצרתי `evals/suites/<name>.py` (מילון `CHECKS`: שם בדיקה → פונקציה).
- [ ] הפרדתי **בדיקות מבניות** (not_blocked / non_empty / has_sources — עוברות גם ב-mock)
      מ**בדיקות תוכן** (שמשמעותיות רק עם מפתח אמיתי). קונבנציה: ה-provider mock מחזיר טקסט
      קבוע, אז בדיקת תוכן (כמו `cites_source` / `recommends_professional`) תיכשל ב-mock — וזה תקין.

## 5. אימות (כמו שעשינו)

> טיפ: ב-Windows הגדירי `PYTHONIOENCODING=utf-8` כדי שעברית ב-stdout לא תפיל את ה-CLI
> (cp1252 חונק תווי כיווניות). השתמשי ב-Python של ה-venv: `.\.venv\Scripts\python.exe`.

- [ ] `python -m core.cli --list` — האג'נט מופיע ברשימה.
- [ ] `python -m core.cli --agent <name> --mock "..."` — כל ה-nodes עוברים מקצה לקצה.
- [ ] `python -m evals.runner --suite <name> --mock` — הבדיקות המבניות ירוקות.
- [ ] הרצה אמיתית (`OPENROUTER_API_KEY`) — אימות שהכלי החי עובד ושהמודל מחזיר פלט.
- [ ] `pytest` ירוק.

## 6. מהמורות נפוצות (נתקלנו בהן בפועל)

- [ ] **slug מודל לא תקין → 404** מ-OpenRouter. אמתי שה-slug ב-`agent.yaml` קיים: רשימת
      המודלים ב-`https://openrouter.ai/api/v1/models`. (`google/gemini-2.5-flash:free`
      כבר לא קיים; `config/default.yaml` עדיין מצביע עליו.)
- [ ] **429 Too Many Requests** = מכסת ה-`:free` היומית של החשבון נגמרה (כל מודלי free
      חולקים מכסה). פתרונות: לחכות לאיפוס, או מודל בתשלום (עולה כסף — מאשרים מראש).
- [ ] **רשת חסומה לכלי** = שכחתי להוסיף את הדומיין ל-`domain_allowlist` של ה-broker.
- [ ] **ModuleNotFoundError: langgraph** = הרצתי עם Python הגלובלי במקום ה-venv.

## 7. סגירה ו-PR

- [ ] עדכנתי את טבלת האג'נטים ב-`README.md`.
- [ ] עדכנתי תיעוד רלוונטי אם הוספתי שכבה חדשה (למשל כלי `web/` — `CLAUDE.md §11`,
      `FILE_GUIDE.md`).
- [ ] הרצתי `ruff check . && ruff format .` (אם dev-deps מותקנות) ו-`pytest`.
- [ ] תיאור PR: מה האג'נט עושה, אילו כלים, ואיך ה-eval מכסה אותו.
- [ ] **האג'נט "מוכן" רק כשהוא עובר את ה-eval suite שלו.**
