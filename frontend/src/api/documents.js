import { API_BASE, apiFetch, clearToken, getToken } from "./client";

export async function uploadDocument(file) {
  const token = getToken();
  const formData = new FormData();
  formData.append("file", file);

  const resp = await fetch(`${API_BASE}/documents/upload`, {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });

  if (resp.status === 401 || resp.status === 403) {
    clearToken();
    const text = await resp.text().catch(() => "");
    throw new Error(text || "Unauthorized. Please login again.");
  }

  const data = await resp.json().catch(() => null);
  if (!resp.ok || data?.success === false) {
    const detail = data?.error?.message || data?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : detail
          ? JSON.stringify(detail)
          : `Upload failed (${resp.status})`
    );
  }

  return data?.data ?? data;
}

export async function listDocuments() {
  return apiFetch("/documents", { method: "GET" });
}

export async function getDocumentStatus(documentId) {
  return apiFetch(`/documents/${encodeURIComponent(documentId)}/status`, {
    method: "GET",
  });
}

export async function deleteDocument(id) {
  return apiFetch(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" });
}
