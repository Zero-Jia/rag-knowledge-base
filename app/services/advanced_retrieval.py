# app/services/advanced_retrieval.py
from __future__ import annotations

from typing import List, Dict, Any, Optional
import logging

from app.core.config import settings
from app.services.hybrid_retrieval import hybrid_retrieve
from app.services.rerank_service import RerankService
from app.services.cache_service import get_cache, set_cache, make_cache_key  # ✅ 新增

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
    标准两阶段 + Redis 缓存（Day25）：
      0) cache：命中直接返回（跳过召回 + rerank）
      1) recall：hybrid 召回 top_k * recall_multiplier 个候选
      2) rerank：cross-encoder 精排
      3) return：取最终 top_k
      4) cache：写入最终 top_k 结果
    """
    q = (query or "").strip()
    if not q:
        return []

    # ✅ 0) 查缓存（缓存最终 top_k 的 rerank 结果）
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

    # 1) 召回更多候选
    recall_k = max(top_k * recall_multiplier, top_k)
    candidates = hybrid_retrieve(q, recall_k, user_id=user_id, mode="hybrid")

    # 2) 精排（只在候选上跑）
    reranker = RerankService()
    reranked = reranker.rerank(q, candidates)

    # 3) 返回最终 top_k
    results = reranked[:top_k]

    # ✅ 4) 写缓存（必须可 JSON 序列化）
    set_cache(cache_key, results)

    return results
