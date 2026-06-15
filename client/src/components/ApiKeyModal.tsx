import { useState } from "react";
import { saveApiKey } from "../api";

interface Props {
  token: string;
  onDone: (masked: string | null) => void;
}

export function ApiKeyModal({ token, onDone }: Props) {
  const [key, setKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { masked } = await saveApiKey(token, key.trim());
      setKey("");
      onDone(masked);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "שגיאה בשמירת המפתח");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-card">
        <h2 className="modal-title">מפתח OpenRouter</h2>
        <p className="modal-desc">
          המפתח נשלח פעם אחת ונשמר ב-keychain של מערכת ההפעלה.
          הוא לא נשמר בדפדפן ולא עובר בכל בקשה.
        </p>

        <form onSubmit={handleSubmit} className="modal-form">
          <input
            type="password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            className="login-input"
            placeholder="sk-or-..."
            autoFocus
            autoComplete="off"
            dir="ltr"
          />

          {error && <div className="login-error">{error}</div>}

          <div className="modal-actions">
            <button type="submit" className="login-btn" disabled={!key.trim() || loading}>
              {loading ? "שומר..." : "שמור מפתח"}
            </button>
            <button type="button" className="skip-btn" onClick={() => onDone(null)}>
              דלג (מצב Mock)
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
