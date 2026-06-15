# AI Agents Desktop — Client

ממשק React (Vite + TypeScript) המתחבר לשרת ה-FastAPI המקומי.

## מסכים

| מסך | קובץ | תיאור |
|-----|------|--------|
| Login | `src/screens/Login.tsx` | הרשמה/כניסה עם אימייל וסיסמה. JWT נשמר ב-localStorage |
| AgentSelect | `src/screens/AgentSelect.tsx` | בחירת אג'נט מרשימה, הצגת אימייל + כפתור יציאה |
| Chat | `src/screens/Chat.tsx` | שיחה עם אג'נט דרך WebSocket עם streaming ו-StepInspector |

## Flow

```
Login (JWT) → AgentSelect → Chat
     ↑                         |
     └─── יציאה (logout) ──────┘
```

## API

כל הקריאות לשרת מרוכזות ב-`src/api.ts`:

| פונקציה | Endpoint | הערות |
|---------|----------|-------|
| `login(email, password)` | `POST /auth/login` | מחזיר `{ access_token, email }` |
| `register(email, password)` | `POST /auth/register` | מחזיר `{ access_token, email }` |
| `fetchAgents(token)` | `GET /agents` | דורש JWT ב-Authorization header |
| `runAgentWS(agent, q, token, ...)` | `WS /ws/run?token=...` | JWT כ-query param (מגבלת WebSocket) |

## הרצה מקומית

```bash
npm install
npm run dev     # http://localhost:5173
```

> השרת חייב לרוץ ב-`http://localhost:8000` — ראה הוראות ב-README הראשי.

## משתני סביבה

אין משתני סביבה בצד ה-client — כל הקונפיג נמצא ב-`src/api.ts` (BASE_URL).
לשינוי כתובת השרת, ערוך את `const BASE` בקובץ זה.
