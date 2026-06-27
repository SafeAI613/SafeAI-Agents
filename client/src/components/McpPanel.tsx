import { useEffect, useState } from "react";
import {
  getMcpServers, mcpConnect, getMcpTools, mcpCall,
  type McpServer, type McpTool,
} from "../apiTools";

interface Props {
  token: string;
}

/** MCP control panel: connect servers, inspect their tools, and test-call one. */
export function McpPanel({ token }: Props) {
  const [servers, setServers] = useState<McpServer[]>([]);
  const [tools, setTools] = useState<McpTool[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<McpTool | null>(null);
  const [argsText, setArgsText] = useState("{}");
  const [callResult, setCallResult] = useState<string | null>(null);

  async function refresh() {
    try {
      setServers(await getMcpServers(token));
      setTools(await getMcpTools(token));
    } catch (e) {
      setError(e instanceof Error ? e.message : "שגיאה");
    }
  }

  useEffect(() => { refresh(); }, []);

  async function toggle(s: McpServer) {
    setBusy(s.name);
    setError(null);
    try {
      await mcpConnect(token, s.name, s.connected ? "disconnect" : "connect");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "שגיאה");
    } finally {
      setBusy(null);
    }
  }

  async function runTool() {
    if (!selected) return;
    setCallResult(null);
    setError(null);
    let args: Record<string, unknown>;
    try {
      args = JSON.parse(argsText || "{}");
    } catch {
      setError("ה-JSON של הארגומנטים לא תקין");
      return;
    }
    try {
      setBusy("call");
      setCallResult(await mcpCall(token, selected.id, args));
    } catch (e) {
      setError(e instanceof Error ? e.message : "הקריאה נכשלה");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="panel mcp-panel" dir="rtl">
      {error && <div className="error-banner">{error}</div>}

      <section>
        <h3>שרתי MCP</h3>
        {servers.length === 0 && <p className="muted">אין שרתים מוגדרים (infra/mcp-servers/servers.yaml).</p>}
        <ul className="server-list">
          {servers.map((s) => (
            <li key={s.name} className="server-row">
              <span className={`dot ${s.connected ? "on" : "off"}`} />
              <span className="server-name">{s.name}</span>
              <span className="server-meta">{s.transport}</span>
              <button
                className="mini-btn"
                disabled={busy === s.name}
                onClick={() => toggle(s)}
              >
                {busy === s.name ? "…" : s.connected ? "נתק" : "התחבר"}
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3>כלים זמינים ({tools.length})</h3>
        <ul className="tool-list">
          {tools.map((t) => (
            <li
              key={t.id}
              className={`tool-row ${selected?.id === t.id ? "active" : ""}`}
              onClick={() => { setSelected(t); setCallResult(null); }}
            >
              <code>{t.id}</code>
              <span className="tool-desc">{t.description}</span>
            </li>
          ))}
        </ul>
      </section>

      {selected && (
        <section className="tool-tester">
          <h3>בדיקת כלי: <code>{selected.id}</code></h3>
          <label className="muted">ארגומנטים (JSON)</label>
          <textarea
            className="args-box"
            value={argsText}
            onChange={(e) => setArgsText(e.target.value)}
            rows={4}
            spellCheck={false}
          />
          <button className="mini-btn" disabled={busy === "call"} onClick={runTool}>
            {busy === "call" ? "מריץ…" : "הרץ"}
          </button>
          {callResult !== null && <pre className="call-result">{callResult}</pre>}
        </section>
      )}
    </div>
  );
}
