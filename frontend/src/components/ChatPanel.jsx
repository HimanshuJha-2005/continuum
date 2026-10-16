import React, { useEffect, useRef, useState } from "react";

export default function ChatPanel({ userId, messages, busy, onSend }) {
  const [text, setText] = useState("");
  const [agent, setAgent] = useState("scribe");
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const submit = (e) => {
    e.preventDefault();
    const message = text.trim();
    if (!message || busy) return;
    setText("");
    onSend(message, agent);
  };

  return (
    <section className="panel chat-panel">
      <div className="panel-head">
        <span>Chat as {userId}</span>
        <span className="segmented">
          <button
            type="button"
            className={agent === "scribe" ? "active" : ""}
            onClick={() => setAgent("scribe")}
          >
            Scribe
          </button>
          <button
            type="button"
            className={agent === "scout" ? "active" : ""}
            onClick={() => setAgent("scout")}
          >
            Scout
          </button>
        </span>
      </div>
      <div className="messages">
        {messages.length === 0 && (
          <p className="empty">
            Ask something from an earlier session — the trace on the right shows
            the memory it touched.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.text}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <form className="composer" onSubmit={submit}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask Continuum…"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !text.trim()}>
          {busy ? "Thinking" : "Send"}
        </button>
      </form>
    </section>
  );
}
