import logging
import time
from typing import Dict, Any, Generator, Optional

from app.services.request_context import get_request_id
from app.services.rag_retrieval import rag_retrieve
from app.services.prompt_builder import build_messages
from app.services.llm_service import generate_answer, stream_answer, LLMServiceError
from app.services.cache_service import get_cache, set_cache, make_cache_key
from app.services.semantic_cache_service import (
    find_semantic_cached_answer,
    save_semantic_cache,
)
from app.exceptions import AppError
from app.core.config import settings

logger = logging.getLogger("rag.perf")


def _build_chat_cache_key(
    *,
    question: str,
    user_id: Optional[int] = None,
    retrieval_mode: str = "semantic",
    top_k: Optional[int] = None,
    stream: bool = False,
) -> str:
    q = (question or "").strip()
    raw = f"user={user_id}|mode={retrieval_mode}|topk={top_k}|stream={stream}|q={q}"
    return make_cache_key("chat", raw)


def chat_with_rag(
    question: str,
    *,
    user_id: Optional[int] = None,
    retrieval_mode: str = "semantic",
    top_k: Optional[int] = None,
) -> Dict[str, Any]:
    """
    两级缓存版本：
    1) exact cache (Redis)
    2) semantic cache (Chroma)
    3) 正常 RAG
    """
    rid = get_request_id()
    start = time.time()

    q = (question or "").strip()
    if not q:
        raise AppError(code="EMPTY_QUESTION", message="question cannot be empty", status_code=400)

    cache_key = _build_chat_cache_key(
        question=q,
        user_id=user_id,
        retrieval_mode=retrieval_mode,
        top_k=top_k,
        stream=False,
    )

    # =========================
    # 1) 精确缓存
    # =========================
    cached = get_cache(cache_key)
    if cached is not None:
        elapsed = time.time() - start
        if isinstance(cached, dict):
            cached.setdefault("cache_hit", True)
            cached.setdefault("cache_type", "exact")
            cached.setdefault("semantic_similarity", None)
            cached.setdefault("matched_cached_question", None)

        logger.info(f"chat exact_cache_hit | rid={rid} | key={cache_key} | time={elapsed:.3f}s")
        return cached

    logger.info(f"chat exact_cache_miss | rid={rid} | key={cache_key} | question_len={len(q)}")

    # =========================
    # 2) 语义缓存
    # =========================
    semantic_cached = find_semantic_cached_answer(
        q,
        user_id=user_id,
        retrieval_mode=retrieval_mode,
    )
    if semantic_cached is not None:
        # 语义缓存命中后，也顺手写入精确缓存，方便下次直接 exact hit
        set_cache(cache_key, semantic_cached)

        elapsed = time.time() - start
        logger.info(
            "chat semantic_cache_hit | rid=%s | similarity=%.4f | time=%.3fs",
            rid,
            semantic_cached.get("semantic_similarity") or 0.0,
            elapsed,
        )
        return semantic_cached

    logger.info(f"chat semantic_cache_miss | rid={rid}")

    # =========================
    # 3) 正常 RAG
    # =========================
    try:
        chunks = rag_retrieve(q)
        messages = build_messages(q, chunks)
        answer = generate_answer(messages)

        payload = {
            "question": q,
            "answer": answer,
            "chunks": chunks,
            "cache_hit": False,
            "cache_type": "none",
            "semantic_similarity": None,
            "matched_cached_question": None,
        }

        # exact cache
        set_cache(cache_key, payload)

        # semantic cache
        save_semantic_cache(
            question=q,
            answer=answer,
            user_id=user_id,
            retrieval_mode=retrieval_mode,
        )

        elapsed = time.time() - start
        logger.info(
            f"chat done | rid={rid} | chunks={len(chunks)} | answer_chars={len(answer)} | time={elapsed:.3f}s"
        )
        return payload

    except LLMServiceError as e:
        elapsed = time.time() - start
        logger.error(f"chat llm_fail | rid={rid} | time={elapsed:.3f}s | error={e}")
        raise AppError(
            code="LLM_UPSTREAM_ERROR",
            message="LLM service failed",
            status_code=503,
            details=str(e),
        )

    except AppError:
        raise

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"chat fail | rid={rid} | time={elapsed:.3f}s | error={e}")
        raise AppError(
            code="CHAT_INTERNAL_ERROR",
            message="Internal chat error",
            status_code=500,
            details=str(e),
        )


def stream_chat_with_rag(
    question: str,
    *,
    user_id: Optional[int] = None,
    retrieval_mode: str = "semantic",
    top_k: Optional[int] = None,
    chunk_size: int = settings.CHAT_STREAM_CHUNK_SIZE,
) -> Generator[str, None, None]:
    """
    流式：
    1) 先查 exact cache
    2) 再查 semantic cache
    3) 最后走正常检索 + LLM stream
    """
    rid = get_request_id()
    start = time.time()

    q = (question or "").strip()
    if not q:
        raise AppError(code="EMPTY_QUESTION", message="question cannot be empty", status_code=400)

    cache_key = _build_chat_cache_key(
        question=q,
        user_id=user_id,
        retrieval_mode=retrieval_mode,
        top_k=top_k,
        stream=True,
    )

    # =========================
    # 1) 精确缓存
    # =========================
    cached = get_cache(cache_key)
    if cached is not None and isinstance(cached, dict) and isinstance(cached.get("answer"), str):
        answer_text = cached["answer"]
        elapsed = time.time() - start
        logger.info(
            f"chat stream exact_cache_hit | rid={rid} | key={cache_key} | answer_chars={len(answer_text)} | time={elapsed:.3f}s"
        )

        for i in range(0, len(answer_text), max(1, chunk_size)):
            yield answer_text[i: i + chunk_size]
        return

    logger.info(f"chat stream exact_cache_miss | rid={rid} | key={cache_key} | question_len={len(q)}")

    # =========================
    # 2) 语义缓存
    # =========================
    semantic_cached = find_semantic_cached_answer(
        q,
        user_id=user_id,
        retrieval_mode=retrieval_mode,
    )
    if semantic_cached is not None and isinstance(semantic_cached.get("answer"), str):
        answer_text = semantic_cached["answer"]

        # 同样写一份 exact cache，提升下次命中速度
        set_cache(
            cache_key,
            {
                "question": q,
                "answer": answer_text,
                "chunks": [],
                "cache_hit": True,
                "cache_type": "semantic",
                "semantic_similarity": semantic_cached.get("semantic_similarity"),
                "matched_cached_question": semantic_cached.get("matched_cached_question"),
            },
        )

        elapsed = time.time() - start
        logger.info(
            "chat stream semantic_cache_hit | rid=%s | similarity=%.4f | answer_chars=%s | time=%.3fs",
            rid,
            semantic_cached.get("semantic_similarity") or 0.0,
            len(answer_text),
            elapsed,
        )

        for i in range(0, len(answer_text), max(1, chunk_size)):
            yield answer_text[i: i + chunk_size]
        return

    logger.info(f"chat stream semantic_cache_miss | rid={rid}")

    # =========================
    # 3) 正常流式 RAG
    # =========================
    try:
        chunks = rag_retrieve(q)
        messages = build_messages(q, chunks)

        out_chars = 0
        answer_parts = []

        for token in stream_answer(messages):
            out_chars += len(token)
            answer_parts.append(token)
            yield token

        answer_text = "".join(answer_parts)

        payload = {
            "question": q,
            "answer": answer_text,
            "chunks": chunks,
            "cache_hit": False,
            "cache_type": "none",
            "semantic_similarity": None,
            "matched_cached_question": None,
        }

        # exact cache
        set_cache(cache_key, payload)

        # semantic cache
        save_semantic_cache(
            question=q,
            answer=answer_text,
            user_id=user_id,
            retrieval_mode=retrieval_mode,
        )

        elapsed = time.time() - start
        logger.info(
            f"chat stream done | rid={rid} | chunks={len(chunks)} | out_chars={out_chars} | time={elapsed:.3f}s"
        )

    except LLMServiceError as e:
        elapsed = time.time() - start
        logger.error(f"chat stream llm_fail | rid={rid} | time={elapsed:.3f}s | error={e}")
        raise AppError(
            code="LLM_UPSTREAM_ERROR",
            message="LLM service failed",
            status_code=503,
            details=str(e),
        )

    except AppError:
        raise

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"chat stream fail | rid={rid} | time={elapsed:.3f}s | error={e}")
        raise AppError(
            code="CHAT_STREAM_INTERNAL_ERROR",
            message="Internal stream chat error",
            status_code=500,
            details=str(e),
        )