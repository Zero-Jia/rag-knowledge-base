import logging
import time

from app.services.request_context import get_request_id
from app.services.rag_retrieval import rag_retrieve
from app.services.prompt_builder import build_messages
from app.services.llm_service import generate_answer, stream_answer, LLMServiceError
from app.exceptions import AppError

logger = logging.getLogger("rag.perf")


def chat_with_rag(question: str):
    """
    Day19：service 层统一抛 AppError
    """
    rid = get_request_id()
    start = time.time()

    q = (question or "").strip()
    if not q:
        raise AppError(code="EMPTY_QUESTION", message="question cannot be empty", status_code=400)

    logger.info(f"chat start | rid={rid} | question_len={len(q)}")

    try:
        chunks = rag_retrieve(q)
        messages = build_messages(q, chunks)
        answer = generate_answer(messages)

        elapsed = time.time() - start
        logger.info(
            f"chat done  | rid={rid} | chunks={len(chunks)} | answer_chars={len(answer)} | time={elapsed:.3f}s"
        )
        return {
            "question": q,
            "answer": answer,
            "chunks": chunks,
        }

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
        # 其他 service 已经抛 AppError 的，直接透传
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


def stream_chat_with_rag(question: str):
    """
    Day19：流式依然可以抛 AppError（但注意 StreamingResponse 下的异常表现）
    """
    rid = get_request_id()
    start = time.time()

    q = (question or "").strip()
    if not q:
        raise AppError(code="EMPTY_QUESTION", message="question cannot be empty", status_code=400)

    logger.info(f"chat stream start | rid={rid} | question_len={len(q)}")

    try:
        chunks = rag_retrieve(q)
        messages = build_messages(q, chunks)

        out_chars = 0
        for token in stream_answer(messages):
            out_chars += len(token)
            yield token

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
