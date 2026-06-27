import { useState } from "react";
import type { ToolCallRecord } from "../types";

interface Props {
  calls: ToolCallRecord[];
}

/** Collapsible log of the tool calls the workbench agent made during a turn. */
export function ToolLog({ calls }: Props) {
  const [open, setOpen] = useState(false);
  if (!calls || calls.length === 0) return null;

  return (
    <div className="tool-log">
      <button className="tool-log-toggle" onClick={() => setOpen(!open)}>
        {open ? "▾" : "▸"} כלים שהופעלו ({calls.length})
      </button>
      {open && (
        <ul className="tool-log-list">
          {calls.map((c, i) => (
            <li key={i} className={`tool-log-row ${c.ok ? "ok" : "fail"}`}>
              <div className="tool-log-head">
                <span className={`dot ${c.ok ? "on" : "off"}`} />
                <code>{c.tool}</code>
              </div>
              {Object.keys(c.arguments || {}).length > 0 && (
                <pre className="tool-log-args">{JSON.stringify(c.arguments, null, 2)}</pre>
              )}
              <pre className="tool-log-result">{c.result}</pre>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
