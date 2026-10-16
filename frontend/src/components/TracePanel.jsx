import React, { useEffect, useRef } from "react";
import cytoscape from "cytoscape";

const STYLE = [
  {
    selector: "node",
    style: {
      label: "data(label)",
      "font-size": 10,
      color: "#111827",
      "text-valign": "bottom",
      "text-margin-y": 4,
      width: 22,
      height: 22,
      "background-color": "#9ca3af",
      "text-outline-width": 0,
    },
  },
  { selector: 'node[type = "Fact"]', style: { "background-color": "#2563eb" } },
  { selector: 'node[type = "Turn"]', style: { "background-color": "#6b7280" } },
  {
    selector: 'node[type = "Preference"]',
    style: { "background-color": "#059669" },
  },
  { selector: 'node[type = "Entity"]', style: { "background-color": "#d97706" } },
  { selector: 'node[type = "Session"]', style: { "background-color": "#7c3aed" } },
  { selector: 'node[type = "User"]', style: { "background-color": "#111827" } },
  {
    selector: "edge",
    style: {
      width: 1.5,
      "line-color": "#c5cad3",
      "target-arrow-color": "#c5cad3",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      label: "data(type)",
      "font-size": 8,
      color: "#9ca3af",
      "text-rotation": "autorotate",
    },
  },
];

export default function TracePanel({ steps, elements }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;
    cyRef.current?.destroy();
    const cy = cytoscape({
      container: containerRef.current,
      elements: [...elements.nodes, ...elements.edges],
      style: STYLE,
      layout: { name: "cose", animate: false, padding: 30 },
      userZooming: true,
      userPanning: true,
      wheelSensitivity: 0.2,
    });
    cyRef.current = cy;
    return () => cy.destroy();
  }, [elements]);

  return (
    <section className="panel trace-panel">
      <div className="panel-head">
        <span>Memory trace</span>
        <span className="legend">
          <span className="fact">fact</span>
          <span className="turn">turn</span>
          <span className="pref">preference</span>
          <span className="entity">entity</span>
        </span>
      </div>
      <div className="canvas" ref={containerRef} />
      <div className="steps">
        {steps.length === 0 && (
          <p className="empty">Queries that fetched this answer appear here.</p>
        )}
        {steps.map((s, i) => (
          <details key={i} className="step">
            <summary>
              <span className={`badge ${s.role}`}>{s.role}</span>
              {s.node_ids.length} nodes, {s.edge_ids.length} edges
            </summary>
            <pre>{s.cypher.trim()}</pre>
          </details>
        ))}
      </div>
    </section>
  );
}
