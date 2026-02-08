const API_BASE = "http://127.0.0.1:8000";

export async function apiFetch(path, options = {}) {
  const token = localStorage.getItem("access_token");

  // 先合并外部 headers + token
  const headers = {
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  // ✅ 只有在非 FormData 的情况下才默认加 JSON Content-Type
  const isFormData =
    typeof FormData !== "undefined" && options.body instanceof FormData;

  if (!isFormData && !("Content-Type" in headers)) {
    headers["Content-Type"] = "application/json";
  }

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
        payload?.detail ||
        `Request failed (${resp.status})`;
      throw new Error(msg);
    }
    return payload.data;
  }

  // ✅ 兼容非统一封装接口（比如 /auth/login 直接返回 token）
  if (!resp.ok) {
    throw new Error(`Request failed (${resp.status})`);
  }
  return payload;
}
