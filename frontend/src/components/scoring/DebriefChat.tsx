import { useEffect, useRef, useState } from "react";
import { scoringApi } from "../../lib/scoringApi";
import type { DebriefMessage } from "../../types/scoring";
import "./scoring.css";

interface Props {
  sessionId: string;
}

export function DebriefChat({ sessionId }: Props) {
  const [messages, setMessages] = useState<DebriefMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scoringApi.getDebriefHistory(sessionId).then(setMessages).catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || sending) return;
    const text = input;
    setInput("");
    setSending(true);
    setMessages((prev) => [...prev, { id: `local-${Date.now()}`, role: "user", content: text, created_at: new Date().toISOString() }]);
    try {
      const reply = await scoringApi.postDebrief(sessionId, text);
      setMessages((prev) => [...prev, reply]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="scoring-debrief">
      <div className="scoring-debrief__messages">
        {messages.map((m) => (
          <div key={m.id} className={`scoring-debrief__message scoring-debrief__message--${m.role}`}>
            {m.content}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="scoring-debrief__input-row">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about your report..."
          disabled={sending}
        />
        <button onClick={send} disabled={sending || !input.trim()}>Send</button>
      </div>
    </div>
  );
}
