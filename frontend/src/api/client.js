const API_BASE = "http://127.0.0.1:8000";

export async function apiFetch(path, options = {}) {
  const token = localStorage.getItem("access_token");

  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  // 某些接口可能返回空 body，这里做下保护
  let payload = null;
  const text = await resp.text();
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = null;
  }

  // ✅ 兼容你 Day19/20 的统一返回：{success,data,error}
  if (payload && typeof payload === "object" && "success" in payload) {
    if (!resp.ok || payload.success === false) {
      const msg =
        payload?.error?.message ||
        payload?.error ||
        `Request failed (${resp.status})`;
      throw new Error(msg);
    }
    return payload.data;
  }

  // ✅ 如果你的 /auth/login 不是统一封装（直接返回 token），也能工作
  if (!resp.ok) {
    throw new Error(`Request failed (${resp.status})`);
  }
  return payload;
}
