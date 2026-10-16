import React, { useCallback, useState } from "react";
import ChatPanel from "./components/ChatPanel.jsx";
import TracePanel from "./components/TracePanel.jsx";
import { getSubgraph, sendChat } from "./api.js";

export default function App() {
  const [userId, setUserId] = useState("alice");
  const [messages, setMessages] = useState([]);
  const [steps, setSteps] = useState([]);
  const [elements, setElements] = useState({ nodes: [], edges: [] });
  const [busy, setBusy] = useState(false);

  const handleSend = useCallback(
    async (message, agent) => {
      setMessages((m) => [...m, { role: "user", text: message }]);
      setBusy(true);
      try {
        const res = await sendChat(userId, message, agent);
        const reply =
          res.answer ?? res.findings ?? "(no response)";
        setMessages((m) => [...m, { role: "assistant", text: reply }]);
        setSteps(res.trace?.steps ?? []);
        const ids = [
          ...new Set(res.trace?.steps?.flatMap((s) => s.node_ids) ?? []),
        ];
        if (ids.length) {
          const sg = await getSubgraph(userId, ids);
          setElements({ nodes: sg.nodes, edges: sg.edges });
        } else {
          setElements({ nodes: [], edges: [] });
        }
      } catch (e) {
        setMessages((m) => [...m, { role: "error", text: String(e) }]);
      } finally {
        setBusy(false);
      }
    },
    [userId]
  );

  const switchUser = (id) => {
    setUserId(id);
    setMessages([]);
    setSteps([]);
    setElements({ nodes: [], edges: [] });
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <h1>Continuum</h1>
          <span>graph memory with explainable recall</span>
        </div>
        <div className="segmented">
          <button
            className={userId === "alice" ? "active" : ""}
            onClick={() => switchUser("alice")}
          >
            Alice
          </button>
          <button
            className={userId === "bob" ? "active" : ""}
            onClick={() => switchUser("bob")}
          >
            Bob
          </button>
        </div>
      </header>
      <div className="panels">
        <ChatPanel
          userId={userId}
          messages={messages}
          busy={busy}
          onSend={handleSend}
        />
        <TracePanel steps={steps} elements={elements} />
      </div>
    </div>
  );
}
