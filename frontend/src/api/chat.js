import { API_BASE, apiFetch, clearToken, getToken } from "./client";

export async function streamChat(question) {
  return streamAgentChat({ question });
}

export async function streamAgentChat({
  question,
  sessionId = null,
  chatHistory = [],
  topK = 5,
  rerankTopN = 3,
  rerankScoreThreshold = 0.1,
  signal,
}) {
  const token = getToken();

  const resp = await fetch(`${API_BASE}/chat/agent/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      question,
      session_id: sessionId,
      chat_history: chatHistory,
      top_k: topK,
      rerank_top_n: rerankTopN,
      rerank_score_threshold: rerankScoreThreshold,
    }),
    signal,
  });

  if (resp.status === 401 || resp.status === 403) {
    clearToken();
    const text = await resp.text().catch(() => "");
    throw new Error(text || "Unauthorized. Please login again.");
  }

  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(text || `HTTP ${resp.status}`);
  }

  if (!resp.body) throw new Error("No stream body");
  return resp.body.getReader();
}

export async function listAgentSessions() {
  const data = await apiFetch("/chat/agent/sessions", { method: "GET" });
  return Array.isArray(data) ? data : data?.items || [];
}

export async function getAgentSessionMessages(sessionId, includeTrace = true) {
  const qs = new URLSearchParams({ include_trace: String(includeTrace) });
  const data = await apiFetch(
    `/chat/agent/sessions/${encodeURIComponent(sessionId)}/messages?${qs}`,
    { method: "GET" }
  );
  return Array.isArray(data) ? data : data?.items || [];
}
