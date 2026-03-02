import logging
import time
from typing import Dict, Any, Generator, Optional

from app.services.request_context import get_request_id
from app.services.rag_retrieval import rag_retrieve
from app.services.prompt_builder import build_messages
from app.services.llm_service import generate_answer, stream_answer, LLMServiceError
from app.services.cache_service import get_cache, set_cache, make_cache_key  # ✅ 新增
from app.exceptions import AppError

logger = logging.getLogger("rag.perf")


def _build_chat_cache_key(
    *,
    question: str,
    user_id: Optional[int] = None,
    retrieval_mode: str = "semantic",
    top_k: Optional[int] = None,
    stream: bool = False,
) -> str:
    """
    缓存 key 生成：
    - 你现在 service 没有 user_id/mode/top_k，这里先提供可扩展参数
    - 当前默认只基于 question 命中；若你 router 能传 user_id/mode/top_k，建议带上
    """
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
    非流式：✅ 完整缓存
    Day19：service 层统一抛 AppError
    Day25：Redis cache
    """
    rid = get_request_id()
    start = time.time()

    q = (question or "").strip()
    if not q:
        raise AppError(code="EMPTY_QUESTION", message="question cannot be empty", status_code=400)

    # ✅ 1) 查缓存（非流式）
    cache_key = _build_chat_cache_key(
        question=q,
        user_id=user_id,
        retrieval_mode=retrieval_mode,
        top_k=top_k,
        stream=False,
    )

    cached = get_cache(cache_key)
    if cached is not None:
        elapsed = time.time() - start
        logger.info(f"chat cache_hit | rid={rid} | key={cache_key} | time={elapsed:.3f}s")
        return cached

    logger.info(f"chat cache_miss | rid={rid} | key={cache_key} | question_len={len(q)}")

    try:
        chunks = rag_retrieve(q)
        messages = build_messages(q, chunks)

        # ✅ 验收点：只有 cache miss 才会调用 LLM
        answer = generate_answer(messages)

        payload = {
            "question": q,
            "answer": answer,
            "chunks": chunks,
        }

        # ✅ 2) 写缓存
        set_cache(cache_key, payload)

        elapsed = time.time() - start
        logger.info(
            f"chat done  | rid={rid} | chunks={len(chunks)} | answer_chars={len(answer)} | time={elapsed:.3f}s"
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
    chunk_size: int = 20,
) -> Generator[str, None, None]:
    """
    流式：✅ 命中缓存则“直接流式吐出缓存 answer”，不调用检索/LLM
         ✅ 未命中走原逻辑，结束后把最终 answer 写入缓存

    Day19：流式依然可以抛 AppError（但注意 StreamingResponse 下的异常表现）
    Day25：Redis cache
    """
    rid = get_request_id()
    start = time.time()

    q = (question or "").strip()
    if not q:
        raise AppError(code="EMPTY_QUESTION", message="question cannot be empty", status_code=400)

    # ✅ 1) 查缓存（流式）
    cache_key = _build_chat_cache_key(
        question=q,
        user_id=user_id,
        retrieval_mode=retrieval_mode,
        top_k=top_k,
        stream=True,
    )

    cached = get_cache(cache_key)
    if cached is not None and isinstance(cached, dict) and isinstance(cached.get("answer"), str):
        answer_text = cached["answer"]
        elapsed = time.time() - start
        logger.info(f"chat stream cache_hit | rid={rid} | key={cache_key} | answer_chars={len(answer_text)} | time={elapsed:.3f}s")

        # ✅ 直接把缓存答案分段 yield（保持“流式体验”）
        for i in range(0, len(answer_text), max(1, chunk_size)):
            yield answer_text[i : i + chunk_size]
        return

    logger.info(f"chat stream cache_miss | rid={rid} | key={cache_key} | question_len={len(q)}")

    try:
        chunks = rag_retrieve(q)
        messages = build_messages(q, chunks)

        out_chars = 0
        answer_parts = []  # ✅ 用来拼最终答案写缓存

        for token in stream_answer(messages):
            out_chars += len(token)
            answer_parts.append(token)
            yield token

        answer_text = "".join(answer_parts)

        # ✅ 2) 写缓存（流式的最终结果）
        payload = {
            "question": q,
            "answer": answer_text,
            "chunks": chunks,
        }
        set_cache(cache_key, payload)

        elapsed = time.time() - start
        logger.info(
            f"chat stream done  | rid={rid} | chunks={len(chunks)} | out_chars={out_chars} | time={elapsed:.3f}s"
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