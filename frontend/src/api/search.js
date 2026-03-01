import { apiFetch } from "./client";

function getSearchPath(mode) {
  if (mode === "hybrid") return "/search/hybrid";
  if (mode === "rerank") return "/search/rerank";
  return "/search";
}

export async function search(query, mode = "semantic", topK = 5) {
  const resp = await apiFetch(getSearchPath(mode), {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK }),
  });

  console.log("apiFetch resp:", resp);

  // ✅ 兼容：items / results + 是否被 apiFetch 解包
  const items =
    resp?.data?.items ??
    resp?.data?.results ??
    resp?.items ??
    resp?.results ??
    [];

  console.log("final items:", items, "length:", items.length);

  return (items || []).map((it) => ({
    ...it,
    score: typeof it.score === "string" ? Number(it.score) : it.score,
  }));
}