# overlay — desktop + MCP + הרצת קוד + קלט קבצים/שמע

זהו **overlay**: פרסי את התוכן מעל הריפו הקיים (אותם נתיבים). קבצים חדשים נוספים, וכמה
קבצים קיימים מוחלפים בגרסה תואמת-לאחור. רשימת הקבצים שמוחלפים:

```
core/providers/openrouter.py    + complete_with_tools()  (complete() נשמר זהה)
core/security/permissions.py    + command_allowlist / fs_roots / code-exec  (API ישן נשמר)
core/runtime/state.py           + tool_calls / attachments  (שדות אופציונליים)
core/agents/registry.py         + רישום אג'נט workbench
core/server/app.py              + endpoints: /mcp/* /code/run /files/* /stt
config/default.yaml             + mcp / code_exec / files / stt
pyproject.toml                  + mcp, python-multipart, extras: [stt] [desktop]
client/src/types.ts             + ToolCallRecord, tool_calls
client/src/App.tsx              + ניתוב workbench -> מסך Workbench
client/src/screens/Chat.tsx     + מיקרופון בפוטר + חילוץ tool_calls
client/src/components/ChatMessage.tsx  + הצגת ToolLog
client/package.json             + @tauri-apps/api, @tauri-apps/plugin-shell, @tauri-apps/cli
```

קבצים חדשים לגמרי: כל `core/tools/mcp/*`, `core/tools/code_exec/*`, `core/tools/stt.py`,
`core/agents/workbench/*`, `core/server/__main__.py`, כל `apps/desktop/*`,
`infra/sandbox/*`, `infra/mcp-servers/servers.yaml`, וברכיבי הלקוח
`apiTools.ts`, `AudioInput/McpPanel/FilesPanel/ToolLog`, `screens/Workbench.tsx`,
`workbench.css`.

## הפעלה מהירה (dev)

```powershell
pip install -e .                          # כולל mcp
npm --prefix client install
# טרמינל 1 — הליבה:
uvicorn core.server.app:app --reload
# טרמינל 2 — הלקוח:
npm --prefix client run dev
```

בחרי את האג'נט **workbench** כדי לקבל לשוניות שיחה / MCP / קבצים. המיקרופון בפוטר השיחה
עובד לכל האג'נטים.

## דסקטופ (Tauri)

ראי `apps/desktop/README.md`. בקצרה: `pip install -e .[desktop]` →
`.\apps\desktop\scripts\build-sidecar.ps1` → `cd apps/desktop && cargo tauri dev`.

## להפעיל יכולות

- **MCP**: ערכי `infra/mcp-servers/servers.yaml` (ה-`filesystem` דורש Node + `MCP_FS_ROOT`).
- **הרצת קוד**: `docker build -t ai-agents-sandbox:latest infra/sandbox` ואז
  `config/default.yaml` → `code_exec.enabled: true`.
- **שמע**: `pip install -e .[stt]` (+ ffmpeg).
