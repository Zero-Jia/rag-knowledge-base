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

    ✅ 修改点：
    - 输出中的 score 改为 final_score（融合分数，越大越好）
    - 保留 vector_score 记录原始向量分数（通常是 distance / 越小越好）
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

        # ✅ 原始向量分数（通常是 distance：越小越好）
        vector_score = _safe_float(r.get("score"), 0.0)
        r["vector_score"] = vector_score

        # ✅ dense 分数：把 distance 转成“越大越好”
        dense_part = 1.0 / (max(vector_score, 1e-6))

        # ✅ 融合分数（越大越好）
        final_score = dense_part * 0.7 + kw * 0.3

        # ✅ 关键：把输出 score 改成 final_score
        r["score"] = final_score

        # 可选：保留 final_score 字段（你想只用 score 也行）
        r["final_score"] = final_score

    # ✅ 现在直接按 score（也就是 final_score）排序
    vector_results.sort(key=lambda x: _safe_float(x.get("score"), 0.0), reverse=True)
    results = vector_results[:top_k]

    # ✅ 4) 写缓存（失败也不影响主流程）
    try:
        set_cache(cache_key, results)
    except Exception as e:
        logger.warning(f"search cache_set_failed | key={cache_key} | err={e}")

    return results