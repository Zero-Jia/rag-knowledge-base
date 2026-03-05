import { apiFetch } from "./client";

// ✅ 统一使用 Vite 环境变量（docker compose 会注入）
// 本地没配时默认回退到 127.0.0.1
const API_BASE =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

function getToken() {
  // ✅ 优先 sessionStorage，再兼容 localStorage（历史代码）
  return (
    sessionStorage.getItem("access_token") ||
    localStorage.getItem("access_token")
  );
}

function clearToken() {
  sessionStorage.removeItem("access_token");
  localStorage.removeItem("access_token");
}

export async function uploadDocument(file) {
  const token = getToken();

  const formData = new FormData();
  formData.append("file", file);

  const resp = await fetch(`${API_BASE}/documents/upload`, {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      // ⚠️ 不要手动写 Content-Type，浏览器会自动带 boundary
    },
    body: formData,
  });

  // ✅ 401/403 更明确：通常是 token 失效/过期/后端重启导致验签失败
  if (resp.status === 401 || resp.status === 403) {
    clearToken();
    const text = await resp.text().catch(() => "");
    throw new Error(text || "Unauthorized. Please login again.");
  }

  // 你的后端统一返回 APIResponse（json）
  const data = await resp.json().catch(() => null);

  if (!resp.ok || data?.success === false) {
    const msg =
      data?.error?.message ||
      (Array.isArray(data?.detail) ? data.detail?.[0]?.msg : data?.detail) ||
      `Upload failed (${resp.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }

  return data?.data ?? data;
}

export async function listDocuments() {
  return apiFetch("/documents", { method: "GET" });
}

export async function deleteDocument(id) {
  return apiFetch(`/documents/${id}`, { method: "DELETE" });
}