from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from app.core.config import settings
from app.exceptions import AppError
from app.services.retrieval_service import retrieve_chunks
from app.services.cache_service import get_cache, set_cache, make_cache_key  # ✅ 新增

logger = logging.getLogger("rag.perf")


def search_chunks(db: Session, user_id: int, query: str, top_k: int) -> Dict[str, Any]:
    q = (query or "").strip()
    if not q:
        raise AppError(code="EMPTY_QUERY", message="Query cannot be empty", status_code=400)

    if top_k < settings.TOP_K_MIN or top_k > settings.TOP_K_MAX:
        raise AppError(
            code="INVALID_TOP_K",
            message=f"top_k must be between {settings.TOP_K_MIN} and {settings.TOP_K_MAX}",
            status_code=400,
        )

    # ✅ Day25：缓存 key（区分用户 + query + top_k + 检索模式）
    # 你这个函数是纯向量 retrieve_chunks，所以 mode 我标记为 vector
    raw = f"v=vector_v2_hierarchical|user={user_id}|mode=vector|topk={top_k}|q={q}"
    cache_key = make_cache_key("search", raw)

    # ✅ 1) 查缓存
    cached = get_cache(cache_key)
    if cached is not None:
        logger.info(f"search cache_hit | user_id={user_id} | key={cache_key} | q_len={len(q)} | top_k={top_k}")
        return cached

    logger.info(f"search cache_miss | user_id={user_id} | key={cache_key} | q_len={len(q)} | top_k={top_k}")

    # ✅ 2) 未命中：正常检索
    chunks = retrieve_chunks(q, top_k)

    # ✅ 统一列表协议：items/total
    payload = {
        "query": q,
        "items": chunks,
        "total": len(chunks),
    }

    # ✅ 3) 写缓存（TTL 在 cache_service 中 set_cache 默认 600s）
    set_cache(cache_key, payload)

    return payload
