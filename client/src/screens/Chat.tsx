import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { runAgentWS } from "../api";
import { ChatMessage } from "../components/ChatMessage";
import { StepInspector } from "../components/StepInspector";
import { AudioInput } from "../components/AudioInput";
import type { Message, NodeEvent, ToolCallRecord } from "../types";

interface Props {
  agent: string;
  token: string;
  onBack: () => void;
}

export function Chat({ agent, token, onBack }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [liveTrace, setLiveTrace] = useState<NodeEvent[]>([]);
  const [liveNode, setLiveNode] = useState<string | undefined>();
  const [streamingText, setStreamingText] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  function send() {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setLoading(true);
    setLiveTrace([]);
    setLiveNode(undefined);
    setStreamingText("");

    setMessages((prev) => [...prev, { role: "user", content: q }]);

    const collectedTrace: NodeEvent[] = [];
    let streamed = "";

    wsRef.current = runAgentWS(
      agent,
      q,
      token,
      (msg: { kind: string; data: unknown }) => {
        if (msg.kind === "event") {
          const ev = msg.data as NodeEvent;
          collectedTrace.push(ev);
          setLiveTrace([...collectedTrace]);
          // tracer emits {type:'node_start'|'node_end', node}; derive the live node label
          if (ev.type === "node_start" || ev.status === "start") setLiveNode(ev.node);
          else setLiveNode(undefined);
        } else if (msg.kind === "token") {
          streamed += msg.data as string;
          setStreamingText(streamed);
          bottomRef.current?.scrollIntoView({ behavior: "smooth" });
        } else if (msg.kind === "result") {
          const data = msg.data as Record<string, unknown>;
          const answer =
            (data.final_answer as string) ||
            (data.draft_answer as string) ||
            streamed ||
            "לא התקבלה תשובה";
          const sources = data.sources as string[] | undefined;
          const blocked = data.blocked as boolean | undefined;
          const toolCalls = data.tool_calls as ToolCallRecord[] | undefined;
          setStreamingText("");
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: answer,
              sources,
              trace: [...collectedTrace],
              blocked,
              tool_calls: toolCalls,
            },
          ]);
          setLiveTrace([]);
          setLiveNode(undefined);
          setLoading(false);
          setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
        }
      },
      () => setLoading(false),
      () => setLoading(false)
    );
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  function onTranscript(text: string) {
    setInput((prev) => (prev ? prev + " " + text : text));
  }

  return (
    <>
      <header className="header">
        <button className="back-btn" onClick={onBack} disabled={loading}>
          → חזרה
        </button>
        <span className="header-title">{agent}</span>
        <button
          className="clear-btn"
          onClick={() => { setMessages([]); setStreamingText(""); }}
          disabled={loading}
        >
          נקה
        </button>
      </header>

      <main className="chat-area">
        {messages.length === 0 && !loading && (
          <div className="empty-state">שאל/י שאלה ←</div>
        )}
        {messages.map((msg, i) => (
          <ChatMessage key={i} msg={msg} />
        ))}
        {loading && (
          <div className="message assistant">
            <div className="bubble loading-bubble">
              <StepInspector trace={liveTrace} loading liveNode={liveNode} />
              {streamingText ? (
                <div className="md streaming">
                  <ReactMarkdown children={streamingText} />
                  <span className="cursor">▍</span>
                </div>
              ) : liveTrace.length === 0 && (
                <span className="dots">מעבד...</span>
              )}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </main>

      <footer className="input-area">
        <AudioInput token={token} disabled={loading} onTranscript={onTranscript} />
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="כתוב/י שאלה… (Enter לשליחה, Shift+Enter לשורה חדשה)"
          disabled={loading}
          rows={2}
          className="input-box"
        />
        <button onClick={send} disabled={loading || !input.trim()} className="send-btn">
          {loading ? "⏳" : "שלח"}
        </button>
      </footer>
    </>
  );
}
