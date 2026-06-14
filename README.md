# AI Agents Desktop

מערכת סוכני AI כתוכנת desktop. כל אג'נט הוא **workflow** מפורש (LangGraph) עם שליטה על כל
שלב, עובר דרך **guardrails**, ומשתמש בכלים בסגנון Anthropic (כרגע: **Skills** ו-**RAG**).
ספק המודל: **OpenRouter**.

ארכיטקטורה: ליבת **Python** (FastAPI sidecar) שאליה יתחבר בעתיד UI (Tauri). כרגע מריצים
דרך ה-CLI; השרת קיים כ-seam ל-UI.

## מצב נוכחי

שני אג'נטים עובדים, על אותו שלד:

| אג'נט | סוג | כלים | תיאור |
|-------|-----|------|-------|
| `plumber` | Q&A | Skill | יועץ אינסטלציה ישראלי, עם שאלות הבהרה ובטיחות |
| `device_guide` | RAG | RAG + Skill | מדריך מכשירים מבוסס קורפוס מקומי (md/txt/pdf) |

יכולות קיימות: workflow לכל אג'נט, tracing per-node, guardrails (מקומי + hook ל-SafeAI),
budget cap, לולאת שיחה רב-תורית, ו-eval harness (כולל תרחיש רב-תורי).

נדרש מינימום הגדרה: Python ‎3.10+‎ ומפתח OpenRouter.

## התקנה (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pip install pypdf          # לתמיכת PDF בקורפוס (אם עוד לא הותקן)
```

(macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate && pip install -e .`)

הגדרת מפתח (PowerShell):
```powershell
$env:OPENROUTER_API_KEY = "sk-or-..."
```

## הרצה

```powershell
python -m core.cli --list                                   # רשימת אג'נטים
python -m core.cli --agent plumber "נזילה מתחת לכיור"          # שאלה בודדת
python -m core.cli --agent device_guide --chat               # שיחה רב-תורית
python -m core.cli --agent device_guide "מה המשמעות של קוד תקלה E1?"
```

ה-CLI מדפיס step-inspector (כל node + timing), את התשובה, וספירת טוקנים.

### השרת (ל-UI עתידי)
```powershell
uvicorn core.server.app:app --reload
# GET /agents | POST /run {"agent","question"} | WS /ws/run (stream אירועים)
```

### Evals
```powershell
python -m evals.runner --suite plumber
```

## מבנה הפרויקט (תמצית)

```
core/
  cli.py                 הרצה: שאלה בודדת + --chat
  server/app.py          FastAPI — seam ל-UI
  agents/
    registry.py          רישום אג'נטים (כאן מוסיפים אג'נט חדש)
    plumber/             graph.py + nodes.py + agent.yaml + skills/
    device_guide/        + corpus/  (קובצי המדריכים)
  runtime/               מנוע גנרי: orchestrator, state, events(tracing)
  tools/
    skills/              טעינת SKILL.md  (ממומש)
    rag/                 chunking + BM25 + load_corpus(md/txt/pdf)  (ממומש)
    mcp/ code_exec/ browser/   stubs לעתיד
  guardrails/            safeai_proxy (+ hook ל-SafeAI) + policies
  memory/short_term.py   חלון שיחה (היסטוריה רב-תורית)
  providers/openrouter.py client + budget
  security/              permissions (allowlist) + secrets
config/default.yaml      provider, budgets, SafeAI toggle, allowlist
evals/                   runner + datasets + suites (per-agent)
docs/FILE_GUIDE.md       מפת קבצים מפורטת — קראי אותה כדי להתמצא
CLAUDE.md                המסמך המייסד (מתאר את הארכיטקטורה המלאה)
```

תיעוד מפורט של כל קובץ חשוב: ראי **`docs/FILE_GUIDE.md`**.

## פעולות נפוצות

- **להחליף מודל**: ערכי `model:` ב-`core/agents/<agent>/agent.yaml`
  (לעברית איכותית מומלץ `anthropic/claude-sonnet-4.5` במקום `openrouter/free`).
- **לחבר מדריכים אמיתיים**: שימי קובצי `.pdf`/`.md`/`.txt` ב-
  `core/agents/device_guide/corpus/` (הסירי את קובצי הדוגמה).
- **להוסיף אג'נט**: ראי "הוספת אג'נט" ב-`docs/FILE_GUIDE.md`.
- **להפעיל SafeAI**: ב-`config/default.yaml` → `guardrails.safeai.enabled: true` + `url`.

## נטפרי / proxy שמסנן תעבורה

התיקון מובנה ב-`core/__init__.py` (משתמש ב-truststore — cert store של Windows). אם חסר,
התקיני `pip install truststore`. ראי הסבר מלא בתחתית הקובץ הזה בגרסה הקודמת או ב-FILE_GUIDE.

## מגבלות ידועות

- איכות העברית תלויה במודל; `openrouter/free` חלש יחסית.
- אחזור RAG לקסיקלי (BM25) עיוור-מורפולוגיה בעברית — דירוג לא תמיד מושלם; שדרוג עתידי =
  embeddings סמנטיים (מחליפים רק את `LexicalIndex` ב-`tools/rag/store.py`).
- PDF סרוק דורש OCR (לא נתמך); PDF עברי עלול לצאת הפוך (פתרון: python-bidi).
- חיפוש אינטרנט: עדיין לא ממומש (נדון; מתוכנן כטול `tools/web/` עם fallback ב-device_guide).