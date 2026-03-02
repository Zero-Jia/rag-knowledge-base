const BASE_URL = "http://127.0.0.1:8000";

export async function streamChat(question) {
  const token = localStorage.getItem("access_token");

  const resp = await fetch(`${BASE_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ question }),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(text || `HTTP ${resp.status}`);
  }

  if (!resp.body) throw new Error("No stream body");

  return resp.body.getReader();
}