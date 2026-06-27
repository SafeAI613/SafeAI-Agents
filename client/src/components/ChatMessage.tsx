import ReactMarkdown from "react-markdown";
import type { Message } from "../types";
import { StepInspector } from "./StepInspector";
import { ToolLog } from "./ToolLog";

interface Props {
  msg: Message;
}

export function ChatMessage({ msg }: Props) {
  return (
    <div className={`message ${msg.role}`}>
      <div className="bubble">
        {msg.blocked ? (
          <span className="blocked-label">⛔ הבקשה נחסמה על ידי guardrails</span>
        ) : (
          <div className="md"><ReactMarkdown children={msg.content ?? ""} /></div>
        )}
      </div>
      {msg.tool_calls && msg.tool_calls.length > 0 && (
        <ToolLog calls={msg.tool_calls} />
      )}
      {msg.sources && msg.sources.length > 0 && (
        <div className="sources">
          <span className="sources-label">מקורות: </span>
          {msg.sources.join(", ")}
        </div>
      )}
      {msg.trace && msg.trace.length > 0 && (
        <StepInspector trace={msg.trace} />
      )}
    </div>
  );
}
