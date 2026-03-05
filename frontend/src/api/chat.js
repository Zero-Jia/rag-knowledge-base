// frontend/src/api/chat.js

// ✅ 统一用 Vite 环境变量（docker compose 会注入）
// 本地开发没配时，默认回退到 127.0.0.1
const API_BASE =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

function getToken() {
  // ✅ 先 sessionStorage，再兼容旧 localStorage（防止历史残留）
  return (
    sessionStorage.getItem("access_token") ||
    localStorage.getItem("access_token")
  );
}

export async function streamChat(question) {
  const token = getToken();

  const resp = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ question }),
  });

  // ✅ 401/403 给出更明确的提示
  if (resp.status === 401 || resp.status === 403) {
    // 可选：清理无效 token，避免一直失败
    sessionStorage.removeItem("access_token");
    localStorage.removeItem("access_token");

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