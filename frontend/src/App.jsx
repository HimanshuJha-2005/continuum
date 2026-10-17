import React, { useCallback, useEffect, useState } from "react";
import ChatPanel from "./components/ChatPanel.jsx";
import TracePanel from "./components/TracePanel.jsx";
import { getHealth, getMemory, getSubgraph, sendChat } from "./api.js";

function now() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function App() {
  const [userId, setUserId] = useState("alice");
  const [messages, setMessages] = useState([]);
  const [steps, setSteps] = useState([]);
  const [elements, setElements] = useState({ nodes: [], edges: [] });
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState("down");
  const [stats, setStats] = useState(null);

  const loadStats = useCallback(async () => {
    try {
      const m = await getMemory(userId);
      setStats({
        sessions: m.sessions.length,
        facts: m.facts.length,
        preferences: Object.keys(m.preferences).length,
        procedures: m.procedures.length,
        state: Object.keys(m.shared_state).length,
      });
    } catch {
      setStats(null);
    }
  }, [userId]);

  useEffect(() => {
    let alive = true;
    const poll = async () => {
      try {
        const h = await getHealth();
        if (alive) setHealth(h.falkordb === "up" ? "up" : "down");
      } catch {
        if (alive) setHealth("down");
      }
    };
    poll();
    const t = setInterval(poll, 20000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const handleSend = useCallback(
    async (message, agent) => {
      setMessages((m) => [...m, { role: "user", text: message, time: now() }]);
      setBusy(true);
      try {
        const started = Date.now();
        const res = await sendChat(userId, message, agent);
        const elapsed = ((Date.now() - started) / 1000).toFixed(1);
        const reply = res.answer ?? res.findings ?? "(no response)";
        const meta = [];
        if (res.extracted && res.extracted.facts !== undefined) {
          meta.push(`${res.extracted.facts} facts extracted`);
        }
        meta.push(`${elapsed}s`);
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            text: reply,
            time: now(),
            meta,
            agent: agent === "scout" ? "Scout" : "Scribe",
          },
        ]);
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
        loadStats();
      } catch (e) {
        setMessages((m) => [
          ...m,
          { role: "error", text: String(e.message || e), time: now() },
        ]);
      } finally {
        setBusy(false);
      }
    },
    [userId, loadStats]
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
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <line x1="5" y1="6" x2="17" y2="11" stroke="#c7d2fe" strokeWidth="1.5" />
            <line x1="5" y1="6" x2="8" y2="17" stroke="#c7d2fe" strokeWidth="1.5" />
            <line x1="17" y1="11" x2="8" y2="17" stroke="#c7d2fe" strokeWidth="1.5" />
            <circle cx="5" cy="6" r="3" fill="#4f46e5" />
            <circle cx="17" cy="11" r="2.5" fill="#2563eb" />
            <circle cx="8" cy="17" r="2.5" fill="#059669" />
          </svg>
          <h1>Continuum</h1>
          <span className="tag">graph memory with explainable recall</span>
        </div>
        <div className="topbar-right">
          <span className={`health ${health}`}>
            <span className="dot" />
            {health === "up" ? "FalkorDB connected" : "FalkorDB offline"}
          </span>
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
        </div>
      </header>
      <div className="panels">
        <ChatPanel
          userId={userId}
          messages={messages}
          busy={busy}
          onSend={handleSend}
        />
        <TracePanel steps={steps} elements={elements} stats={stats} />
      </div>
    </div>
  );
}
