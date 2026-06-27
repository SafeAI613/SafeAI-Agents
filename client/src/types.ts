export interface NodeEvent {
  node: string;
  status?: "start" | "end";
  type?: string;
  duration_ms?: number;
}

export interface ToolCallRecord {
  tool: string;                          // "server.tool" or "code_exec"
  arguments: Record<string, unknown>;
  result: string;
  ok: boolean;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  trace?: NodeEvent[];
  blocked?: boolean;
  tool_calls?: ToolCallRecord[];
}

export interface AgentInfo {
  name: string;
}
