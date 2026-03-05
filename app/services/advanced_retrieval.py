# app/services/advanced_retrieval.py
from __future__ import annotations

from typing import List, Dict, Any, Optional
import logging

from app.core.config import settings
from app.services.hybrid_retrieval import hybrid_retrieve
from app.services.rerank_service import RerankService
from app.services.cache_service import get_cache, set_cache, make_cache_key

logger = logging.getLogger("rag.perf")


def _build_adv_search_cache_key(
    *,
    query: str,
    user_id: Optional[int] = None,
    mode: str = "hybrid_rerank",
    top_k: int = settings.TOP_K,
    recall_multiplier: int = settings.RECALL_MULTIPLIER,
) -> str:
    q = (query or "").strip()
    raw = f"user={user_id}|mode={mode}|topk={top_k}|rm={recall_multiplier}|q={q}"
    return make_cache_key("search", raw)


def retrieve_with_rerank(
    query: str,
    top_k: int = settings.TOP_K,
    recall_multiplier: int = settings.RECALL_MULTIPLIER,
    *,
    user_id: Optional[int] = None,
    mode: str = "hybrid_rerank",
) -> List[Dict[str, Any]]:
    """
    两阶段检索 + rerank + Redis cache

    修改后逻辑：
      score = rerank_score
    """
    q = (query or "").strip()
    if not q:
        return []

    # 0) 查缓存
    cache_key = _build_adv_search_cache_key(
        query=q,
        user_id=user_id,
        mode=mode,
        top_k=top_k,
        recall_multiplier=recall_multiplier,
    )

    cached = get_cache(cache_key)
    if cached is not None:
        logger.info(f"adv_search cache_hit | key={cache_key} | q_len={len(q)} | top_k={top_k}")
        return cached

    logger.info(f"adv_search cache_miss | key={cache_key} | q_len={len(q)} | top_k={top_k}")

    # 1) hybrid 召回更多候选
    recall_k = max(top_k * recall_multiplier, top_k)
    candidates = hybrid_retrieve(q, recall_k, user_id=user_id, mode="hybrid")

    # 2) rerank 精排
    reranker = RerankService()
    reranked = reranker.rerank(q, candidates)

# ⭐ 用 rerank_score 覆盖 score，并删除 rerank_score 字段
    for r in reranked:
        if "rerank_score" in r:
            r["score"] = float(r["rerank_score"])
            del r["rerank_score"]

    # 按 rerank score 排序
    reranked.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)

    # 3) 取 top_k
    results = reranked[:top_k]

    # 4) 写缓存
    set_cache(cache_key, results)

    return results