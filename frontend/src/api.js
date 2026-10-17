const BASE = "";

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    let detail = `request failed: ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export function sendChat(userId, message, agent = "scribe") {
  return request("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, message, agent }),
  });
}

export function getSubgraph(userId, nodeIds) {
  const ids = nodeIds.join(",");
  return request(
    `/memory/subgraph?user_id=${encodeURIComponent(userId)}&node_ids=${ids}`
  );
}

export function getMemory(userId) {
  return request(`/memory?user_id=${encodeURIComponent(userId)}`);
}

export function getAgents(userId) {
  return request(`/agents?user_id=${encodeURIComponent(userId)}`);
}

export function getHealth() {
  return request("/health");
}
