import { useState } from "react";
import { Chat } from "./Chat";
import { McpPanel } from "../components/McpPanel";
import { FilesPanel } from "../components/FilesPanel";
import "../workbench.css";

interface Props {
  token: string;
  onBack: () => void;
}

type Tab = "chat" | "mcp" | "files";

/** The tool-using agent's home: chat plus side tools (MCP servers, workspace files).
 *  Audio input lives inside Chat, so it's available here too. */
export function Workbench({ token, onBack }: Props) {
  const [tab, setTab] = useState<Tab>("chat");

  return (
    <div className="workbench">
      <nav className="wb-tabs">
        <button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>
          שיחה
        </button>
        <button className={tab === "mcp" ? "active" : ""} onClick={() => setTab("mcp")}>
          MCP
        </button>
        <button className={tab === "files" ? "active" : ""} onClick={() => setTab("files")}>
          קבצים
        </button>
      </nav>

      <div className="wb-body">
        {/* Chat stays mounted so its conversation/WS survive tab switches. */}
        <div style={{ display: tab === "chat" ? "flex" : "none", flexDirection: "column", height: "100%" }}>
          <Chat agent="workbench" token={token} onBack={onBack} />
        </div>
        {tab === "mcp" && <McpPanel token={token} />}
        {tab === "files" && <FilesPanel token={token} />}
      </div>
    </div>
  );
}
