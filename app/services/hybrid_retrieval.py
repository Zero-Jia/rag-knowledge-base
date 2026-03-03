# app/services/hybrid_retrieval.py

from typing import List, Dict, Any, Optional
import logging

from app.core.config import settings
from app.services.retrieval_service import retrieve_chunks
from app.services.keyword_search import keyword_score
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


def hybrid_retrieve(
    query: str,
    top_k: int = settings.TOP_K,
    *,
    user_id: Optional[int] = None,
    mode: str = "hybrid",
) -> List[Dict[str, Any]]:
    """
    Hybrid Search + Cache (cache failure won't break search)
    """
    q = (query or "").strip()
    if not q:
        return []

    cache_key = _build_search_cache_key(query=q, user_id=user_id, mode=mode, top_k=top_k)

    # ✅ 0) 查缓存（失败也不影响主流程）
    cached = None
    try:
        cached = get_cache(cache_key)
    except Exception as e:
        logger.warning(f"search cache_get_failed | key={cache_key} | err={e}")

    if cached is not None:
        logger.info(f"search cache_hit | key={cache_key} | q_len={len(q)} | top_k={top_k}")
        return cached

    logger.info(f"search cache_miss | key={cache_key} | q_len={len(q)} | top_k={top_k}")

    # 1) 候选集拉大
    candidate_k = max(top_k * settings.RECALL_MULTIPLIER, top_k)
    vector_results = retrieve_chunks(q, candidate_k) or []

    for r in vector_results:
        text = str(r.get("text", "") or "")

        # ✅ keyword_score 兜底（不允许抛异常）
        try:
            # 你项目里 keyword_score 的参数顺序若相反，就改成 keyword_score(text, q)
            kw = _safe_float(keyword_score(q, text), 0.0)
        except Exception as e:
            logger.warning(f"keyword_score_failed | err={e}")
            kw = 0.0
        r["keyword_score"] = kw

        # ✅ dense 分数兜底：你的 retrieve_chunks 返回字段叫 score
        # 你之前把 score 当 distance 做倒数，这里仍保留，但保证不会崩
        score_val = _safe_float(r.get("score"), 0.0)

        # 如果 score 很小/为0，倒数会很大，做个下限保护
        dense_part = 1.0 / (max(score_val, 1e-6))

        r["final_score"] = dense_part * 0.7 + kw * 0.3

    vector_results.sort(key=lambda x: _safe_float(x.get("final_score"), 0.0), reverse=True)
    results = vector_results[:top_k]

    # ✅ 4) 写缓存（失败也不影响主流程）
    try:
        set_cache(cache_key, results)
    except Exception as e:
        logger.warning(f"search cache_set_failed | key={cache_key} | err={e}")

    return results
