import { apiFetch } from "./client";

function getSearchPath(mode) {
  if (mode === "hybrid") return "/search/hybrid";
  if (mode === "rerank") return "/search/rerank";
  return "/search";
}

export async function search(query, mode = "vector", topK = 5) {
  const resp = await apiFetch(getSearchPath(mode), {
    method: "POST",
    body: JSON.stringify({ query, top_k: Number(topK) || 5 }),
  });

  const items =
    resp?.data?.items ??
    resp?.data?.results ??
    resp?.items ??
    resp?.results ??
    [];

  return (items || []).map((item) => ({
    ...item,
    score: typeof item.score === "string" ? Number(item.score) : item.score,
  }));
}
