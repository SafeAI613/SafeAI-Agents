const BASE = "http://localhost:8000";
const WS_BASE = "ws://localhost:8000";

// ── auth ──────────────────────────────────────────────────────────────────────

export interface AuthResponse {
  access_token: string;
  token_type: string;
  email: string;
}

async function authRequest(path: string, email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "שגיאה");
  return data as AuthResponse;
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return authRequest("/auth/login", email, password);
}

export function register(email: string, password: string): Promise<AuthResponse> {
  return authRequest("/auth/register", email, password);
}

// ── agents ────────────────────────────────────────────────────────────────────

export async function fetchAgents(token: string): Promise<string[]> {
  const res = await fetch(`${BASE}/agents`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  return data.agents as string[];
}

// ── api key (stored server-side in OS keychain) ───────────────────────────────

export interface KeyStatus {
  set: boolean;
  masked: string | null;
}

export async function saveApiKey(token: string, key: string): Promise<{ masked: string }> {
  const res = await fetch(`${BASE}/auth/key`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ key }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "שגיאה בשמירת המפתח");
  return data as { masked: string };
}

export async function fetchKeyStatus(token: string): Promise<KeyStatus> {
  const res = await fetch(`${BASE}/auth/key`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return (await res.json()) as KeyStatus;
}

export async function deleteApiKey(token: string): Promise<void> {
  await fetch(`${BASE}/auth/key`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

// ── streaming run ─────────────────────────────────────────────────────────────

export type StreamCallback = (event: { kind: string; data: unknown }) => void;

export function runAgentWS(
  agent: string,
  question: string,
  token: string,
  onMessage: StreamCallback,
  onDone: () => void,
  onError: (e: Event) => void
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/ws/run?token=${encodeURIComponent(token)}`);
  ws.onopen = () => ws.send(JSON.stringify({ agent, question }));
  ws.onmessage = (e) => onMessage(JSON.parse(e.data));
  ws.onclose = () => onDone();
  ws.onerror = onError;
  return ws;
}
