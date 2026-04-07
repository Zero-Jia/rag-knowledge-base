from typing import List, Dict, Any, Optional
import logging

from app.core.config import settings
from app.services.retrieval_service import retrieve_chunks
from app.services.keyword_search import bm25_rerank
from app.services.cache_service import get_cache, set_cache, make_cache_key

logger = logging.getLogger("rag.perf")


def _build_search_cache_key(
    *,
    query: str,
    user_id: Optional[int] = None,
    mode: str = "hybrid",
    top_k: int = settings.TOP_K,
) -> str:
    q = (query or "").strip()
    raw = f"user={user_id}|mode={mode}|topk={top_k}|q={q}"
    return make_cache_key("search", raw)


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _normalize(values: List[float]) -> List[float]:
    """
    Min-Max 归一化到 [0, 1]
    """
    if not values:
        return []

    min_v = min(values)
    max_v = max(values)

    if max_v == min_v:
        return [1.0 for _ in values]

    return [(v - min_v) / (max_v - min_v) for v in values]


def hybrid_retrieve(
    query: str,
    top_k: int = settings.TOP_K,
    *,
    user_id: Optional[int] = None,
    mode: str = "hybrid",
) -> List[Dict[str, Any]]:
    """
    Hybrid Search + Cache (cache failure won't break search)

    修改后逻辑：
    1. 先做向量召回，拿到候选 chunks
    2. 使用 BM25 对候选集整体打分
    3. 将向量分数和 BM25 分数归一化后融合
    4. 输出 score / final_score 为最终融合分数（越大越好）

    说明：
    - retrieve_chunks 返回的原始 score 通常是向量 distance，越小越相似
    - 输出中的 vector_score 保留原始向量分数
    - 输出中的 bm25_score 为 BM25 原始分数
    - 输出中的 score / final_score 为融合后的最终分数
    """
    q = (query or "").strip()
    if not q:
        return []

    cache_key = _build_search_cache_key(query=q, user_id=user_id, mode=mode, top_k=top_k)

    # 0) 查缓存（失败也不影响主流程）
    cached = None
    try:
        cached = get_cache(cache_key)
    except Exception as e:
        logger.warning(f"search cache_get_failed | key={cache_key} | err={e}")

    if cached is not None:
        logger.info(f"search cache_hit | key={cache_key} | q_len={len(q)} | top_k={top_k}")
        return cached

    logger.info(f"search cache_miss | key={cache_key} | q_len={len(q)} | top_k={top_k}")

    # 1) 先扩大候选集
    candidate_k = max(top_k * settings.RECALL_MULTIPLIER, top_k)
    vector_results = retrieve_chunks(q, candidate_k) or []

    if not vector_results:
        return []

    # 2) 对候选集整体做 BM25 打分
    try:
        reranked_candidates = bm25_rerank(q, vector_results)
    except Exception as e:
        logger.warning(f"bm25_rerank_failed | err={e}")
        reranked_candidates = []
        for item in vector_results:
            copied = dict(item)
            copied["keyword_score"] = 0.0
            reranked_candidates.append(copied)

    # 3) 处理向量分数（原始 score 通常是 distance，越小越好）
    raw_vector_scores: List[float] = []
    for item in reranked_candidates:
        raw_distance = _safe_float(item.get("score"), 1e9)
        item["vector_score"] = raw_distance

        # 转成“越大越好”的 dense 分数
        dense_score = 1.0 / (1.0 + max(raw_distance, 0.0))
        raw_vector_scores.append(dense_score)

    norm_vector_scores = _normalize(raw_vector_scores)

    # 4) 处理 BM25 分数
    raw_bm25_scores: List[float] = []
    for item in reranked_candidates:
        bm25_score = _safe_float(item.get("keyword_score"), 0.0)
        item["bm25_score"] = bm25_score
        raw_bm25_scores.append(bm25_score)

    norm_bm25_scores = _normalize(raw_bm25_scores)

    # 5) 融合分数
    final_results: List[Dict[str, Any]] = []
    for item, v_score, b_score in zip(reranked_candidates, norm_vector_scores, norm_bm25_scores):
        result = dict(item)

        final_score = 0.7 * v_score + 0.3 * b_score

        # 保留归一化后的分数，方便调试和面试解释
        result["normalized_vector_score"] = float(v_score)
        result["normalized_bm25_score"] = float(b_score)

        # 输出最终融合分数
        result["final_score"] = float(final_score)
        result["score"] = float(final_score)

        final_results.append(result)

    # 6) 排序并截断
    final_results.sort(key=lambda x: _safe_float(x.get("score"), 0.0), reverse=True)
    results = final_results[:top_k]

    # 7) 写缓存（失败也不影响主流程）
    try:
        set_cache(cache_key, results)
    except Exception as e:
        logger.warning(f"search cache_set_failed | key={cache_key} | err={e}")

    return results