export interface NodeEvent {
  node: string;
  status: "start" | "end";
  duration_ms?: number;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  trace?: NodeEvent[];
  blocked?: boolean;
}

export interface AgentInfo {
  name: string;
}
