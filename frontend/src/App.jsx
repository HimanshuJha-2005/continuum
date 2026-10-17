import React, { useCallback, useEffect, useState } from "react";
import ChatPanel from "./components/ChatPanel.jsx";
import TracePanel from "./components/TracePanel.jsx";
import {
  getAgents,
  getFullGraph,
  getHealth,
  getMemory,
  getSubgraph,
  getSessionTurns,
  sendChat,
} from "./api.js";

function now() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function App() {
  const [userId, setUserId] = useState("alice");
  const [sessionId, setSessionId] = useState("web");
  const [messages, setMessages] = useState([]);
  const [steps, setSteps] = useState([]);
  const [elements, setElements] = useState({ nodes: [], edges: [] });
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState("down");
  const [stats, setStats] = useState(null);
  const [handoffs, setHandoffs] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [brainMode, setBrainMode] = useState(false);

  const loadStats = useCallback(async () => {
    try {
      const [m, a] = await Promise.all([getMemory(userId), getAgents(userId)]);
      setStats({
        sessions: m.sessions.length,
        facts: m.facts.length,
        preferences: Object.keys(m.preferences).length,
        procedures: m.procedures.length,
        state: Object.keys(m.shared_state).length,
        handoffs: a.handoffs.length,
      });
      setSessions(m.sessions);
      setHandoffs(a.handoffs.slice(0, 3));
    } catch {
      setStats(null);
      setSessions([]);
      setHandoffs([]);
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
        const res = await sendChat(userId, message, agent, sessionId);
        const elapsed = ((Date.now() - started) / 1000).toFixed(1);
        const reply = res.answer ?? res.findings ?? "(no response)";
        const meta = [];
        if (res.coordinated) {
          meta.push("consulted Scout");
        }
        if (res.extracted && res.extracted.facts !== undefined && !res.extracted.skipped) {
          meta.push(`${res.extracted.facts} facts extracted`);
          if (res.extracted.preferences) {
            meta.push(`${res.extracted.preferences} preferences learned`);
          }
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
        if (ids.length && !brainMode) {
          const sg = await getSubgraph(userId, ids);
          setElements({ nodes: sg.nodes, edges: sg.edges });
        } else if (!brainMode) {
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
    [userId, sessionId, brainMode, loadStats]
  );

  const switchUser = (id) => {
    setUserId(id);
    setSessionId("web");
    setMessages([]);
    setSteps([]);
    setElements({ nodes: [], edges: [] });
    setBrainMode(false);
  };

  const newSession = () => {
    setSessionId(`s-${Date.now().toString(36)}`);
    setMessages([]);
    setSteps([]);
    setElements({ nodes: [], edges: [] });
  };

  const openSession = async (id) => {
    setSessionId(id);
    setSteps([]);
    setElements({ nodes: [], edges: [] });
    try {
      const res = await getSessionTurns(userId, id);
      setMessages(
        res.turns.map((t) => ({
          role: t.role,
          text: t.content,
          time: new Date(t.ts).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        }))
      );
    } catch {
      setMessages([]);
    }
  };

  const toggleBrain = useCallback(async () => {
    if (brainMode) {
      setBrainMode(false);
      setElements({ nodes: [], edges: [] });
      return;
    }
    try {
      const full = await getFullGraph(userId);
      setElements({ nodes: full.nodes, edges: full.edges });
      setBrainMode(true);
    } catch {
      /* keep current view */
    }
  }, [brainMode, userId]);

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
          sessionId={sessionId}
          sessions={sessions}
          onNewSession={newSession}
          onOpenSession={openSession}
        />
        <TracePanel
          steps={steps}
          elements={elements}
          stats={stats}
          handoffs={handoffs}
          brainMode={brainMode}
          onToggleBrain={toggleBrain}
        />
      </div>
    </div>
  );
}
