import { useEffect, useState } from "react";
import { fetchAgents } from "./api";
import { Login } from "./screens/Login";
import { AgentSelect } from "./screens/AgentSelect";
import { Chat } from "./screens/Chat";
import "./App.css";

const TOKEN_KEY = "auth_token";
const EMAIL_KEY = "auth_email";

export default function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [userEmail, setUserEmail] = useState<string | null>(() => localStorage.getItem(EMAIL_KEY));
  const [agents, setAgents] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  function handleAuth(newToken: string, email: string) {
    localStorage.setItem(TOKEN_KEY, newToken);
    localStorage.setItem(EMAIL_KEY, email);
    setToken(newToken);
    setUserEmail(email);
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMAIL_KEY);
    setToken(null);
    setUserEmail(null);
    setAgents([]);
    setSelectedAgent(null);
  }

  useEffect(() => {
    if (!token) return;
    fetchAgents(token)
      .then(setAgents)
      .catch(() => {
        setError("לא ניתן להתחבר לשרת. האם הוא רץ? (uvicorn core.server.app:app)");
      });
  }, [token]);

  if (!token) {
    return (
      <div className="app" dir="rtl">
        <Login onAuth={handleAuth} />
      </div>
    );
  }

  return (
    <div className="app" dir="rtl">
      {error && <div className="error-banner">{error}</div>}
      {selectedAgent === null ? (
        <AgentSelect
          agents={agents}
          userEmail={userEmail ?? ""}
          onSelect={setSelectedAgent}
          onLogout={handleLogout}
        />
      ) : (
        <Chat agent={selectedAgent} token={token} onBack={() => setSelectedAgent(null)} />
      )}
    </div>
  );
}
