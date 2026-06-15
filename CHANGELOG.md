# Changelog

כל השינויים הבולטים בפרויקט מתועדים כאן.
הפורמט מבוסס על [Keep a Changelog](https://keepachangelog.com/),
והגרסאות עוקבות אחר [Semantic Versioning](https://semver.org/).

## [Unreleased]
### Planned
- חיפוש אינטרנט (`tools/web/`) עם fallback ב-device_guide
- embeddings סמנטיים ל-RAG (החלפת `LexicalIndex`)
- ממשק Tauri (עוטף את ה-React client כתוכנת desktop)
- ייצוא observability ל-LangSmith/OpenTelemetry
- מימוש שכבות `mcp/`, `code_exec/`, `browser/`

## [0.2.0] - 2026-06-15
### Added
- אימות משתמשים מלא (`core/auth/`): הרשמה/כניסה עם bcrypt + JWT, מחובר ל-MongoDB Atlas.
- Endpoints חדשים בשרת: `POST /auth/register`, `POST /auth/login`; שאר ה-endpoints מוגנים ב-JWT.
- סטטיסטיקות per-user ב-MongoDB: היסטוריית התחברויות (timestamp + IP) ושימוש באג'נטים.
- ממשק React חלקי: מסך Login (הרשמה/כניסה), AgentSelect עם הצגת משתמש + יציאה, Chat מחובר ל-JWT.
- JWT מועבר ל-WebSocket דרך query param (`/ws/run?token=...`).

### Fixed
- תאימות `passlib` עם `bcrypt>=4.0`: הוספת pin `bcrypt<4.0`.

## [0.1.0] - 2026-06-15
### Added
- ליבת runtime גנרית: orchestrator מבוסס LangGraph, state משותף, tracing per-node.
- אג'נט `plumber` — Q&A יועץ אינסטלציה ישראלי, עם Skill ושאלות הבהרה.
- אג'נט `device_guide` — RAG מעל קורפוס מקומי (md/txt/pdf), אחזור BM25.
- שכבת Skills — טעינת `SKILL.md` והזרקה ל-system prompt.
- כלי RAG — chunking, אחזור לקסיקלי (BM25), וחילוץ טקסט מ-PDF (pypdf).
- שכבת guardrails — `SafeAIProxy` (כל I/O עובר דרכה) + policies מקומיים + hook ל-SafeAI.
- ספק OpenRouter עם תקרת budget (budget cap) לכל הרצה.
- לולאת שיחה רב-תורית ב-CLI (`--chat`) עם היסטוריה.
- Eval harness — בדיקות per-agent, כולל תרחישים רב-תוריים.
- FastAPI server (`/agents`, `/run`, `/ws/run`) כ-seam ל-UI עתידי.
- תיעוד: README, CLAUDE.md, docs/FILE_GUIDE.md, CONTRIBUTING.md.

### Fixed
- תקלת SSL מאחורי proxy שמסנן תעבורה (נטפרי): שימוש ב-truststore (cert store של Windows)
  עם fallback שמרכך את בדיקת ה-keyUsage של Python 3.13.

[Unreleased]: https://example.com/your-repo/compare/v0.1.0...HEAD
[0.1.0]: https://example.com/your-repo/releases/tag/v0.1.0