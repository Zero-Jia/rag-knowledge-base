export const API_BASE =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

export function getToken() {
  return (
    sessionStorage.getItem("access_token") ||
    localStorage.getItem("access_token")
  );
}

export function clearToken() {
  sessionStorage.removeItem("access_token");
  localStorage.removeItem("access_token");
}

function normalizeError(payload, status) {
  if (!payload) return `Request failed (${status})`;

  const detail = payload?.error?.message || payload?.error || payload?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || JSON.stringify(item)).join("; ");
  }
  if (typeof detail === "object") return JSON.stringify(detail);
  return detail || `Request failed (${status})`;
}

export async function apiFetch(path, options = {}) {
  const token = getToken();
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

  const text = await resp.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = text || null;
  }

  if (resp.status === 401 || resp.status === 403) {
    clearToken();
    throw new Error(normalizeError(payload, resp.status) || "Unauthorized");
  }

  if (payload && typeof payload === "object" && "success" in payload) {
    if (!resp.ok || payload.success === false) {
      throw new Error(normalizeError(payload, resp.status));
    }
    return payload.data;
  }

  if (!resp.ok) {
    throw new Error(normalizeError(payload, resp.status));
  }

  return payload;
}
