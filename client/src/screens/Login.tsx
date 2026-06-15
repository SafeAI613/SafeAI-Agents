import { useState } from "react";
import { login, register } from "../api";

interface Props {
  onAuth: (token: string, email: string) => void;
}

export function Login({ onAuth }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const fn = mode === "login" ? login : register;
      const { access_token, email: userEmail } = await fn(email, password);
      onAuth(access_token, userEmail);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "שגיאה לא ידועה");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <h1 className="login-title">AI Agents Desktop</h1>

        <div className="login-tabs">
          <button
            className={`login-tab ${mode === "login" ? "active" : ""}`}
            onClick={() => { setMode("login"); setError(null); }}
          >
            התחברות
          </button>
          <button
            className={`login-tab ${mode === "register" ? "active" : ""}`}
            onClick={() => { setMode("register"); setError(null); }}
          >
            הרשמה
          </button>
        </div>

        <form onSubmit={submit} className="login-form">
          <label className="login-label">
            אימייל
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="login-input"
              placeholder="user@example.com"
              required
              autoFocus
            />
          </label>

          <label className="login-label">
            סיסמה
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="login-input"
              placeholder="לפחות 6 תווים"
              required
              minLength={6}
            />
          </label>

          {error && <div className="login-error">{error}</div>}

          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? "⏳ מתחבר..." : mode === "login" ? "כניסה" : "צור חשבון"}
          </button>
        </form>
      </div>
    </div>
  );
}
