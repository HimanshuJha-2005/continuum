const BASE = "";

export async function sendChat(userId, message, agent = "scribe") {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, message, agent }),
  });
  if (!res.ok) throw new Error(`chat failed: ${res.status}`);
  return res.json();
}

export async function getSubgraph(userId, nodeIds) {
  const res = await fetch(
    `${BASE}/memory/subgraph?user_id=${encodeURIComponent(userId)}&node_ids=${nodeIds.join(",")}`
  );
  if (!res.ok) throw new Error(`subgraph failed: ${res.status}`);
  return res.json();
}

export async function getAgents(userId) {
  const res = await fetch(`${BASE}/agents?user_id=${encodeURIComponent(userId)}`);
  if (!res.ok) throw new Error(`agents failed: ${res.status}`);
  return res.json();
}

export async function getHealth() {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}
