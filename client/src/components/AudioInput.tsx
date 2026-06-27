import { useRef, useState } from "react";
import { transcribeAudio } from "../apiTools";

interface Props {
  token: string;
  disabled?: boolean;
  onTranscript: (text: string) => void;
}

type Status = "idle" | "recording" | "transcribing" | "error";

/**
 * Mic button: hold-free toggle recording with MediaRecorder, then POST the audio to /stt.
 * The transcript is handed back to the parent (which drops it into the chat input), so
 * voice input works for every agent, not just the workbench.
 */
export function AudioInput({ token, disabled, onTranscript }: Props) {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  async function start() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setStatus("transcribing");
        try {
          const text = await transcribeAudio(token, blob);
          if (text) onTranscript(text);
          setStatus("idle");
        } catch (e) {
          setError(e instanceof Error ? e.message : "תמלול נכשל");
          setStatus("error");
        }
      };
      recorder.start();
      recorderRef.current = recorder;
      setStatus("recording");
    } catch {
      setError("אין גישה למיקרופון");
      setStatus("error");
    }
  }

  function stop() {
    recorderRef.current?.stop();
  }

  const label =
    status === "recording" ? "■" :
    status === "transcribing" ? "…" : "🎤";

  return (
    <div className="audio-input" title={error ?? "קלט קולי"}>
      <button
        type="button"
        className={`mic-btn ${status}`}
        disabled={disabled || status === "transcribing"}
        onClick={status === "recording" ? stop : start}
        aria-label="הקלטה קולית"
      >
        {label}
      </button>
      {status === "recording" && <span className="mic-hint">מקליט… לחצי לעצירה</span>}
      {error && <span className="mic-error">{error}</span>}
    </div>
  );
}
