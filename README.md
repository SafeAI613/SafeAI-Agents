# AI Agents Desktop — vertical slice ראשון (אג'נט "אינסטלטור")

זהו מימוש **מקצה לקצה** של שכבת הליבה של המערכת, עם אג'נט ייחוס אחד — **יועץ אינסטלציה**.
המטרה: לוודא שכל הצנרת הארכיטקטונית עובדת לפני שמוסיפים אג'נטים נוספים.

כל שכבה שהאג'נט הזה נוגע בה **ממומשת ועובדת**:
LangGraph workflow → guardrails → OpenRouter provider (עם budget cap) → state → tracing per-node → evals.
שכבות שהאג'נט הזה לא צריך (browser/RAG/code-exec/MCP/UI) קיימות כ-stubs מתועדים, כדי
שהאג'נטים הבאים פשוט יתחברו לאותו שלד.

> מה שעדיין לא בארגז הזה (במכוון): אפליקציית ה-Tunari/React. השרת (FastAPI) כבר כאן בתור
> ה-seam שה-UI יתחבר אליו. בינתיים ה-CLI הוא הדרך המהירה להריץ ולראות את הצינור עובד.

---

## התקנה (Windows / PowerShell)

```powershell
# מתוך תיקיית הפרויקט
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

(ב-macOS/Linux: `python3 -m venv .venv && source .venv/bin/activate && pip install -e .`)

---

## הרצה — שני מצבים

### 1. מצב MOCK (בלי מפתח, לראות את הצינור מיד)
```powershell
python -m core.cli --agent plumber --mock "יש לי נזילה מתחת לכיור, מה לבדוק קודם?"
```
תקבלי step-inspector (כל node + timing), תשובה לדוגמה, וספירת טוקנים.

### 2. מצב אמיתי (OpenRouter)
```powershell
$env:OPENROUTER_API_KEY = "sk-or-..."          # PowerShell
python -m core.cli --agent plumber "סתימה בכיור באמבטיה, איך לפתוח בלי כימיקלים?"
```
אם המפתח לא מוגדר, המערכת נופלת אוטומטית למצב mock ומודיעה על כך.

רשימת אג'נטים: `python -m core.cli --list`

---

## Evals
```powershell
python -m evals.runner --suite plumber            # עם מפתח אמיתי = בדיקות תוכן אמיתיות
python -m evals.runner --suite plumber --mock     # בדיקות מבניות בלבד
```
שימי לב: במצב mock הבדיקה `recommends_professional` (במקרה הגז) **תיכשל בכוונה** — המוק
מחזיר תשובה קבועה בלי המלצה על בעל מקצוע. זו הוכחה שה-eval באמת בודק תוכן. עם מפתח אמיתי
זה אמור לעבור.

---

## השרת (ל-UI בעתיד)
```powershell
uvicorn core.server.app:app --reload
# GET  /agents        רשימת אג'נטים
# POST /run           {"agent":"plumber","question":"...","mock":true}
# WS   /ws/run        הרצה עם stream חי של אירועי ה-nodes
```

## בדיקות
```powershell
pytest -q
```

---

## מבנה (vertical slice)

```
core/
  cli.py                 # הרצה מיידית
  server/app.py          # FastAPI — seam ל-UI
  agents/
    registry.py          # רישום אג'נטים
    plumber/             # אג'נט הייחוס: graph.py + nodes.py + agent.yaml
  runtime/               # מנוע גנרי: orchestrator, state, events(tracing)
  providers/openrouter.py# client + budget + mock
  guardrails/            # safeai_proxy (+ hook ל-SafeAI) + policies
  memory/short_term.py
  tools/{mcp,rag,code_exec,browser}/   # stubs מתועדים לאג'נטים הבאים
  security/              # permissions (allowlist) + secrets
  observability/         # exporter stub (LangSmith/OTel)
evals/                   # runner + datasets + suites (per-agent)
config/default.yaml      # provider, budgets, SafeAI toggle, allowlist
CLAUDE.md                # המסמך המייסד לאג'נט המפתח
```

## איך מוסיפים אג'נט חדש
1. צרי `core/agents/<name>/` עם `graph.py` + `nodes.py` + `agent.yaml`.
2. רשמי factory ב-`core/agents/registry.py`.
3. הוסיפי `evals/suites/<name>.py` + `evals/datasets/<name>.yaml`.
4. האג'נט "מוכן" רק כשהוא עובר את ה-eval suite שלו.

## חיבור SafeAI
ברירת המחדל: guardrails מקומיים בלבד (רץ מהקופסה). כדי לנתב הכול דרך SafeAI שלך,
ב-`config/default.yaml` הפעילי `guardrails.safeai.enabled: true` וכווני את ה-`url`
לנקודת ה-moderation שלך. את ה-payload/parse התאימי ב-`core/guardrails/safeai_proxy.py`.
