const BASE = "";

export async function sendChat(userId, message) {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, message }),
  });
  if (!res.ok) throw new Error(`chat failed: ${res.status}`);
  return res.json();
}

export async function getTrace(userId, turnId) {
  const res = await fetch(`${BASE}/trace/${userId}/${turnId}`);
  if (!res.ok) throw new Error(`trace failed: ${res.status}`);
  return res.json();
}

export async function getHealth() {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}
