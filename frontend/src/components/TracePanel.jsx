import React, { useEffect, useRef, useState } from "react";
import cytoscape from "cytoscape";

const STYLE = [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "font-size": 10,
      "font-weight": 500,
      "font-family": "-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
      color: "#334155",
      "text-valign": "bottom",
      "text-margin-y": 6,
      "text-outline-width": 3,
      "text-outline-color": "#f8fafc",
      width: 24,
      height: 24,
      "border-width": 2,
      "border-color": "#ffffff",
      "background-color": "#94a3b8",
    },
  },
  { selector: 'node[type = "Fact"]', style: { "background-color": "#2563eb" } },
  {
    selector: 'node[type = "Fact"][?valid_to]',
    style: {
      "background-color": "#ffffff",
      "border-color": "#dc2626",
      color: "#b91c1c",
    },
  },
  {
    selector: 'edge[type = "SUPERSEDES"]',
    style: {
      width: 2,
      "line-style": "dashed",
      "line-color": "#dc2626",
      "target-arrow-color": "#dc2626",
      color: "#b91c1c",
    },
  },
  { selector: 'node[type = "Turn"]', style: { "background-color": "#64748b" } },
  {
    selector: 'node[type = "Preference"]',
    style: { "background-color": "#059669" },
  },
  { selector: 'node[type = "Entity"]', style: { "background-color": "#d97706" } },
  { selector: 'node[type = "Session"]', style: { "background-color": "#7c3aed" } },
  { selector: 'node[type = "User"]', style: { "background-color": "#111827" } },
  { selector: 'node[type = "Agent"]', style: { "background-color": "#4f46e5" } },
  {
    selector: "node:selected",
    style: { "border-width": 3, "border-color": "#4f46e5" },
  },
  {
    selector: "edge",
    style: {
      width: 1.5,
      "line-color": "#cbd5e1",
      "target-arrow-color": "#cbd5e1",
      "target-arrow-shape": "triangle",
      "arrow-scale": 0.8,
      "curve-style": "bezier",
      label: "data(type)",
      "font-size": 7,
      "font-weight": 500,
      color: "#a3adb9",
      "text-outline-width": 3,
      "text-outline-color": "#f8fafc",
      "text-rotation": "autorotate",
    },
  },
];

export default function TracePanel({ steps, elements, stats, handoffs, brainMode, onToggleBrain }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [selected, setSelected] = useState(null);
  const hasGraph = elements.nodes.length > 0;
  const sourceSteps = selected
    ? steps.filter((s) => s.node_ids.includes(selected.id))
    : [];

  useEffect(() => {
    if (!containerRef.current) return;
    cyRef.current?.destroy();
    setSelected(null);
    const cy = cytoscape({
      container: containerRef.current,
      elements: [...elements.nodes, ...elements.edges],
      style: STYLE,
      layout: {
        name: "cose",
        animate: false,
        padding: 50,
        idealEdgeLength: 130,
        nodeRepulsion: 22000,
        componentSpacing: 120,
        minNodeSpacing: 70,
        nodeDimensionsIncludeLabels: true,
      },
    });
    cy.on("tap", "node", (evt) => setSelected(evt.target.data()));
    cy.on("tap", (evt) => {
      if (evt.target === cy) setSelected(null);
    });
    cyRef.current = cy;
    return () => cy.destroy();
  }, [elements]);

  return (
    <section className="panel trace-panel">
      <div className="panel-head">
        <span>
          Memory trace
          <span className="sub">
            {hasGraph
              ? `${elements.nodes.length} nodes · ${elements.edges.length} edges`
              : "live subgraph"}
          </span>
        </span>
        <span className="legend">
          <span className="fact">fact</span>
          <span className="turn">turn</span>
          <span className="pref">preference</span>
          <span className="entity">entity</span>
          <button
            type="button"
            className={`brain-toggle ${brainMode ? "active" : ""}`}
            onClick={onToggleBrain}
          >
            {brainMode ? "answer graph" : "explore full brain"}
          </button>
        </span>
      </div>
      {stats && (
        <div className="stats">
          <span className="stat">
            <b>{stats.sessions}</b> sessions
          </span>
          <span className="stat">
            <b>{stats.facts}</b> facts
          </span>
          <span className="stat">
            <b>{stats.preferences}</b> preferences
          </span>
          <span className="stat">
            <b>{stats.procedures}</b> procedures
          </span>
          <span className="stat">
            <b>{stats.state}</b> shared state
          </span>
          <span className="stat">
            <b>{stats.handoffs}</b> handoffs
          </span>
        </div>
      )}
      {handoffs && handoffs.length > 0 && (
        <div className="handoffs">
          {handoffs.map((h, i) => (
            <div key={i} className="handoff-line">
              <span className="handoff-route">
                {h.from} → {h.to}
              </span>
              <span className="handoff-summary">{h.summary}</span>
            </div>
          ))}
        </div>
      )}
      <div className="canvas-wrap">
        <div className="canvas" ref={containerRef} />
        {!hasGraph && (
          <div className="canvas-empty">
            {brainMode
              ? "This user's full memory graph will render here."
              : "The nodes and edges this answer touched will render here."}
          </div>
        )}
      </div>
      {selected && (
        <div className="node-drawer">
          <div className="node-drawer-head">
            <span className={`node-type ${String(selected.type).toLowerCase()}`}>
              {selected.type}
            </span>
            <span className="node-title">{selected.label}</span>
            <button
              type="button"
              className="node-close"
              onClick={() => setSelected(null)}
            >
              close
            </button>
          </div>
          <dl className="node-props">
            {Object.entries(selected.props || {}).map(([k, v]) => (
              <div key={k} className="node-prop">
                <dt>{k}</dt>
                <dd>
                  {typeof v === "object" && v !== null
                    ? JSON.stringify(v)
                    : String(v)}
                </dd>
              </div>
            ))}
          </dl>
          <p className="node-source-title">Fetched by</p>
          {sourceSteps.map((s, i) => (
            <details key={i} className="step">
              <summary>
                <span className={`badge ${s.role}`}>{s.role}</span>
                <span className="count">show cypher</span>
              </summary>
              <pre>{s.cypher.trim()}</pre>
            </details>
          ))}
          {sourceSteps.length === 0 && (
            <p className="node-source-note">
              Neighbor node — expanded from a traced node.
            </p>
          )}
        </div>
      )}
      <div className="steps">
        <p className="steps-title">
          {brainMode
            ? "Last answer's queries (full brain is browse-only)"
            : "Queries that fetched this answer"}
        </p>
        {steps.length === 0 && (
          <p className="canvas-empty" style={{ position: "static" }}>
            None yet.
          </p>
        )}
        {steps.map((s, i) => (
          <details key={i} className="step">
            <summary>
              <span className={`badge ${s.role}`}>{s.role}</span>
              <span>{s.node_ids.length} nodes</span>
              <span className="count">
                {s.edge_ids.length > 0 ? `${s.edge_ids.length} edges · ` : ""}show cypher
              </span>
            </summary>
            <pre>{s.cypher.trim()}</pre>
          </details>
        ))}
      </div>
    </section>
  );
}
