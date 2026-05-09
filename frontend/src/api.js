const STORAGE_KEY = "pakeconbot_conversation_id";
// Base URL for API calls.
// In production (S3), Vite bakes in VITE_API_URL = "http://<EC2-IP>:8000" at build time.
// Locally, this is empty so relative /api/* paths still work through the Vite dev proxy.
const API_BASE = import.meta.env.VITE_API_URL ?? "";

export const getConversationId = () => sessionStorage.getItem(STORAGE_KEY);

export const setConversationId = (id) => {
  if (id) sessionStorage.setItem(STORAGE_KEY, id);
  else sessionStorage.removeItem(STORAGE_KEY);
};

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg || d).join("; ")
          : res.statusText;
    throw new Error(msg || "Request failed");
  }
  return data;
}

export async function sendMessage(message) {
  const cid = getConversationId();
  const payload = { message };
  if (cid) payload.conversation_id = cid;
  const data = await postJson(`${API_BASE}/api/chat`, payload);
  if (data.conversation_id) setConversationId(data.conversation_id);
  return data;
}

export async function clearConversation() {
  const cid = getConversationId();
  if (cid) await postJson(`${API_BASE}/api/clear`, { conversation_id: cid });
  setConversationId(null);
}



