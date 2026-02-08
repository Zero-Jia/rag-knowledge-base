import { apiFetch } from "./client";

const BASE_URL = "http://127.0.0.1:8000";

export async function uploadDocument(file) {
  const token = localStorage.getItem("access_token");

  const formData = new FormData();
  // ✅ 字段名必须叫 file（和后端 UploadFile = File(...) 对应）
  formData.append("file", file);

  const resp = await fetch(`${BASE_URL}/documents/upload`, {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      // ✅ 不要手动写 Content-Type，让浏览器自动生成 multipart boundary
    },
    body: formData, // ✅ 关键：这里必须是 formData（实例），不是 FormData（大写）
  });

  const data = await resp.json().catch(() => null);

  if (!resp.ok || data?.success === false) {
    const msg =
      data?.error?.message ||
      (Array.isArray(data?.detail) ? data.detail?.[0]?.msg : data?.detail) ||
      "Upload failed";
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }

  return data?.data ?? data;
}

export async function listDocuments() {
  // 期待返回：{ items: [...] }（来自统一响应 data）
  return apiFetch("/documents", { method: "GET" });
}
