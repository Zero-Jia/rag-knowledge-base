from typing import Any, Dict, Optional

from app.services.cache_service import get_cache, set_cache, make_cache_key
from app.services.semantic_cache_service import (
    find_semantic_cached_answer,
    save_semantic_cache,
)


def build_agent_cache_key(
    *,
    question: str,
    user_id: Optional[int] = None,
    retrieval_mode: str = "agentic",
    top_k: Optional[int] = None,
) -> str:
    """
    构造 Agent 聊天使用的精确缓存 key
    """
    q = (question or "").strip()
    raw = f"user={user_id}|mode={retrieval_mode}|topk={top_k}|q={q}"
    return make_cache_key("agent_chat", raw)


def lookup_exact_cache(
    *,
    question: str,
    user_id: Optional[int] = None,
    retrieval_mode: str = "agentic",
    top_k: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    查询精确缓存
    """
    cache_key = build_agent_cache_key(
        question=question,
        user_id=user_id,
        retrieval_mode=retrieval_mode,
        top_k=top_k,
    )
    return get_cache(cache_key)


def lookup_semantic_cache(
    *,
    question: str,
    user_id: Optional[int] = None,
    retrieval_mode: str = "agentic",
) -> Optional[Dict[str, Any]]:
    """
    查询语义缓存
    """
    return find_semantic_cached_answer(
        question.strip(),
        user_id=user_id,
        retrieval_mode=retrieval_mode,
    )


def save_agent_cache(
    *,
    question: str,
    answer: str,
    chunks: Optional[list] = None,
    user_id: Optional[int] = None,
    retrieval_mode: str = "agentic",
    top_k: Optional[int] = None,
) -> None:
    """
    同时保存：
    1. 精确缓存
    2. 语义缓存
    """
    chunks = chunks or []

    payload = {
        "question": question,
        "answer": answer,
        "chunks": chunks,
        "cache_hit": False,
        "cache_type": "none",
        "semantic_similarity": None,
        "matched_cached_question": None,
    }

    cache_key = build_agent_cache_key(
        question=question,
        user_id=user_id,
        retrieval_mode=retrieval_mode,
        top_k=top_k,
    )
    set_cache(cache_key, payload)

    save_semantic_cache(
        question=question,
        answer=answer,
        user_id=user_id,
        retrieval_mode=retrieval_mode,
    )