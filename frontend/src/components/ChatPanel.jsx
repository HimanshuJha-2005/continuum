import React, { useState } from "react";

export default function ChatPanel() {
  const [messages, setMessages] = useState([]);

  return (
    <div style={{ flex: 1, padding: 16, borderRight: "1px solid #ddd", display: "flex", flexDirection: "column" }}>
      <h2 style={{ marginTop: 0 }}>Continuum</h2>
      <div style={{ flex: 1, overflowY: "auto" }}>
        {messages.length === 0 && (
          <p style={{ color: "#888" }}>Chat goes here — Day 2.</p>
        )}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          style={{ flex: 1, padding: 8 }}
          placeholder="Ask Continuum…"
          disabled
        />
        <button disabled>Send</button>
      </div>
    </div>
  );
}
