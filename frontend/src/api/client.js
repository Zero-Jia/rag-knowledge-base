// ✅ 先读 Vite 环境变量（docker compose 会注入）
// 本地开发没配时，默认回退到 127.0.0.1
const API_BASE =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

export async function apiFetch(path, options = {}) {
  // ✅ 改为 sessionStorage
  const token = sessionStorage.getItem("access_token");

  const headers = {
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;

  if (!isFormData && !("Content-Type" in headers)) {
    headers["Content-Type"] = "application/json";
  }

  const normPath = path.startsWith("/") ? path : `/${path}`;

  const resp = await fetch(`${API_BASE}${normPath}`, {
    ...options,
    headers,
  });

  let payload = null;
  const text = await resp.text();
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = null;
  }

  if (payload && typeof payload === "object" && "success" in payload) {
    if (!resp.ok || payload.success === false) {
      const msg =
        payload?.error?.message ||
        payload?.error ||
        payload?.detail ||
        `Request failed (${resp.status})`;
      throw new Error(msg);
    }
    return payload.data;
  }

  if (!resp.ok) {
    throw new Error(`Request failed (${resp.status})`);
  }
  return payload;
}