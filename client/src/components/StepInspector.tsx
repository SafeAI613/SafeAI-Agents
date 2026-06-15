import type { NodeEvent } from "../types";

interface Props {
  trace: NodeEvent[];
  loading?: boolean;
  liveNode?: string;
}

export function StepInspector({ trace, loading, liveNode }: Props) {
  if (!loading && trace.length === 0) return null;

  return (
    <div className="step-inspector">
      <div className="step-inspector-title">צעדים</div>
      {trace.map((ev, i) => (
        <div key={i} className="step-row">
          <span className={`step-dot ${ev.status}`} />
          <span className="step-name">{ev.node}</span>
          {ev.duration_ms !== undefined && (
            <span className="step-time">{ev.duration_ms}ms</span>
          )}
        </div>
      ))}
      {loading && liveNode && (
        <div className="step-row live">
          <span className="step-dot pulse" />
          <span className="step-name">{liveNode}</span>
        </div>
      )}
    </div>
  );
}
