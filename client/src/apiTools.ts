// API layer for the tool surfaces: MCP, code execution, workspace files, and speech-to-text.
// The base URL is the local core sidecar (same in dev and when bundled by Tauri).

const BASE = "http://localhost:8000";

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { detail?: string }).detail ?? "שגיאה");
  return data as T;
}

// ── MCP ───────────────────────────────────────────────────────────────────────

export interface McpServer {
  name: string;
  transport: string;
  enabled: boolean;
  connected: boolean;
}

export interface McpTool {
  id: string;          // "server.tool"
  server: string;
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

export async function getMcpServers(token: string): Promise<McpServer[]> {
  const res = await fetch(`${BASE}/mcp/servers`, { headers: authHeaders(token) });
  const data = await jsonOrThrow<{ servers: McpServer[] }>(res);
  return data.servers;
}

export async function mcpConnect(
  token: string, name: string, action: "connect" | "disconnect"
): Promise<void> {
  const res = await fetch(`${BASE}/mcp/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ name, action }),
  });
  await jsonOrThrow(res);
}

export async function getMcpTools(token: string, server?: string): Promise<McpTool[]> {
  const q = server ? `?server=${encodeURIComponent(server)}` : "";
  const res = await fetch(`${BASE}/mcp/tools${q}`, { headers: authHeaders(token) });
  const data = await jsonOrThrow<{ tools: McpTool[] }>(res);
  return data.tools;
}

export async function mcpCall(
  token: string, tool: string, args: Record<string, unknown>
): Promise<string> {
  const res = await fetch(`${BASE}/mcp/call`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ tool, arguments: args }),
  });
  const data = await jsonOrThrow<{ result: string }>(res);
  return data.result;
}

// ── code execution ────────────────────────────────────────────────────────────

export interface CodeResult {
  ok: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  timed_out: boolean;
  backend: string;
}

export async function runCode(
  token: string, code: string, language = "python", stdin = ""
): Promise<CodeResult> {
  const res = await fetch(`${BASE}/code/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ code, language, stdin }),
  });
  return jsonOrThrow<CodeResult>(res);
}

// ── workspace files ────────────────────────────────────────────────────────────

export interface FileEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size: number | null;
}

export async function listFiles(token: string, path = ""): Promise<FileEntry[]> {
  const res = await fetch(`${BASE}/files?path=${encodeURIComponent(path)}`, {
    headers: authHeaders(token),
  });
  const data = await jsonOrThrow<{ items: FileEntry[] }>(res);
  return data.items;
}

export async function readFile(token: string, path: string): Promise<string> {
  const res = await fetch(`${BASE}/files/read?path=${encodeURIComponent(path)}`, {
    headers: authHeaders(token),
  });
  const data = await jsonOrThrow<{ content: string }>(res);
  return data.content;
}

export async function writeFile(token: string, path: string, content: string): Promise<void> {
  const res = await fetch(`${BASE}/files/write`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ path, content }),
  });
  await jsonOrThrow(res);
}

export async function uploadFile(token: string, file: File, path = ""): Promise<FileEntry> {
  const form = new FormData();
  form.append("file", file);
  form.append("path", path);
  const res = await fetch(`${BASE}/files/upload`, {
    method: "POST", headers: authHeaders(token), body: form,
  });
  return jsonOrThrow<FileEntry>(res);
}

// ── speech-to-text ──────────────────────────────────────────────────────────────

export async function transcribeAudio(token: string, blob: Blob): Promise<string> {
  const form = new FormData();
  form.append("file", blob, "audio.webm");
  const res = await fetch(`${BASE}/stt`, {
    method: "POST", headers: authHeaders(token), body: form,
  });
  const data = await jsonOrThrow<{ text: string }>(res);
  return data.text;
}
