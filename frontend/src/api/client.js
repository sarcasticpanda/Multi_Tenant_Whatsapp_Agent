const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function get(path) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "ngrok-skip-browser-warning": "true" },
  });
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "true",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

export const api = {
  getTenants: () => get("/api/tenants"),
  getSessions: (tenantId) => get(`/api/tenants/${tenantId}/sessions`),
  getMessages: (sessionId) => get(`/api/sessions/${sessionId}/messages`),
  getStats: (tenantId) => get(`/api/tenants/${tenantId}/stats`),
  broadcast: (payload) => post("/api/broadcast", payload),
};
