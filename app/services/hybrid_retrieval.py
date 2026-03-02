# app/services/hybrid_retrieval.py

from typing import List, Dict, Any, Optional
import logging

from app.services.retrieval_service import retrieve_chunks
from app.services.keyword_search import keyword_score
from app.services.cache_service import get_cache, set_cache, make_cache_key  # ✅ 新增

logger = logging.getLogger("rag.perf")


def _build_search_cache_key(
    *,
    query: str,
    user_id: Optional[int] = None,
    mode: str = "hybrid",
    top_k: int = 5,
) -> str:
    """
    Day25 建议的 key 形式：search:{user_id}:{query}:{mode}
    但生产更稳的做法是 hash key（我们 cache_service.make_cache_key 内部已 hash）
    """
    q = (query or "").strip()
    raw = f"user={user_id}|mode={mode}|topk={top_k}|q={q}"
    return make_cache_key("search", raw)


def hybrid_retrieve(
    query: str,
    top_k: int = 5,
    *,
    user_id: Optional[int] = None,
    mode: str = "hybrid",
) -> List[Dict[str, Any]]:
    """
    Hybrid Search（简化工程版）+ Redis 缓存版（Day25）：
    0) 先查缓存：命中则直接返回
    1) 向量检索拿候选集（top_k * 2）
    2) 对候选集做关键词打分
    3) 融合得分后排序
    4) 写缓存（TTL）
    """
    q = (query or "").strip()
    if not q:
        return []

    # ✅ 0) 查缓存
    cache_key = _build_search_cache_key(query=q, user_id=user_id, mode=mode, top_k=top_k)
    cached = get_cache(cache_key)
    if cached is not None:
        logger.info(f"search cache_hit | key={cache_key} | q_len={len(q)} | top_k={top_k}")
        return cached

    logger.info(f"search cache_miss | key={cache_key} | q_len={len(q)} | top_k={top_k}")

    # 1) 候选集拉大：防止纯向量 top_k 把“精确匹配”的结果漏掉
    candidate_k = max(top_k * 2, top_k)
    vector_results = retrieve_chunks(q, candidate_k)
    # 约定：retrieve_chunks 返回形如：
    # [{"text": "...", "score": <distance or similarity>, ...}, ...]

    for r in vector_results:
        kw = keyword_score(r.get("text", ""), q)
        r["keyword_score"] = kw

        # 下面用 A) distance 写（与你规划一致）：
        dist = float(r.get("score", 0.0))
        dense_part = 1.0 / (dist + 1e-6)

        # 2) 加权融合：0.7 语义 + 0.3 精确
        r["final_score"] = dense_part * 0.7 + kw * 0.3

    vector_results.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
    results = vector_results[:top_k]

    # ✅ 4) 写缓存
    # 注意：results 必须是可 JSON 序列化的 dict/list/str/number
    set_cache(cache_key, results)

    return results