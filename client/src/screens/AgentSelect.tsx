interface Props {
  agents: string[];
  userEmail: string;
  onSelect: (agent: string) => void;
  onLogout: () => void;
}

const AGENT_DESCRIPTIONS: Record<string, string> = {
  plumber: "יועץ אינסטלציה ישראלי — שואל שאלות הבהרה ונותן הנחיות מעשיות",
  device_guide: "מדריך מכשירים — עונה על שאלות מתוך מדריכי הפעלה מקומיים",
};

export function AgentSelect({ agents, userEmail, onSelect, onLogout }: Props) {
  return (
    <div className="agent-select-screen">
      <div className="agent-select-header">
        <h1 className="agent-select-title">AI Agents Desktop</h1>
        <p className="agent-select-subtitle">בחר/י אג'נט להתחלת שיחה</p>
        <div className="agent-select-user">
          <span className="user-email">{userEmail}</span>
          <button className="logout-btn" onClick={onLogout}>יציאה</button>
        </div>
      </div>

      <div className="agent-cards">
        {agents.length === 0 && (
          <div className="agent-loading">טוען אג'נטים...</div>
        )}
        {agents.map((agent) => (
          <button key={agent} className="agent-card" onClick={() => onSelect(agent)}>
            <div className="agent-card-icon">{agentIcon(agent)}</div>
            <div className="agent-card-body">
              <div className="agent-card-name">{agent}</div>
              <div className="agent-card-desc">
                {AGENT_DESCRIPTIONS[agent] ?? "אג'נט AI"}
              </div>
            </div>
            <span className="agent-card-arrow">←</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function agentIcon(name: string) {
  if (name.includes("plumber")) return "🔧";
  if (name.includes("device")) return "📖";
  return "🤖";
}
