import React, { useEffect, useRef, useState } from "react";

const SUGGESTIONS = {
  alice: [
    "What language do I prefer for new projects?",
    "What stack did we pick for Continuum?",
    "Summarize what we discussed in earlier sessions",
  ],
  bob: ["What language do I prefer?", "Where do I deploy?"],
};

export default function ChatPanel({ userId, messages, busy, onSend }) {
  const [text, setText] = useState("");
  const [agent, setAgent] = useState("scribe");
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

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
        <span>
          Chat as {userId}
          <span className="sub">
            · isolated memory graph
          </span>
        </span>
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
          <div className="empty-state">
            <h3>This memory belongs to {userId} alone</h3>
            <p>
              Each user gets an isolated graph inside one FalkorDB instance.
              Ask a question — the trace on the right shows exactly which
              memory the answer came from.
            </p>
            <div className="chips">
              {SUGGESTIONS[userId].map((s) => (
                <button key={s} disabled={busy} onClick={() => onSend(s, agent)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg-wrap ${m.role}`}>
            <div className="msg-meta">
              <span>{m.agent || (m.role === "user" ? userId : "")}</span>
              <span>{m.time}</span>
              {m.meta?.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
            <div className={`msg ${m.role}`}>{m.text}</div>
          </div>
        ))}
        {busy && (
          <div className="msg-wrap assistant">
            <div className="msg-meta">
              <span>{agent === "scout" ? "Scout" : "Scribe"}</span>
            </div>
            <div className="msg assistant typing">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
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
