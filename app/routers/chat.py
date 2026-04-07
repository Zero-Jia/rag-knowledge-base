import time
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.security import get_current_user
from app.services.chat_service import chat_with_rag, stream_chat_with_rag
from app.services.llm_service import LLMServiceError
from app.services.request_context import get_request_id
from app.schemas.common import APIResponse
from app.schemas.chat import ChatRequest
from app.exceptions import AppError

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("api.chat")


@router.post(
    "/",
    summary="Chat with RAG (non-streaming)",
    description=(
        "Generate an answer using Retrieval-Augmented Generation (RAG).\n\n"
        "- Auth required\n"
        "- Request body contains `question`\n"
        "- Optional: `retrieval_mode`, `top_k`\n"
        "- Response is wrapped in `APIResponse`\n"
        "- Returns cache metadata: `cache_hit`, `cache_type`, `semantic_similarity`, `matched_cached_question`"
    ),
    response_model=APIResponse,
    responses={
        200: {
            "description": "Chat answer (APIResponse)",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "question": "什么是深度学习？",
                            "answer": "深度学习是机器学习的一个分支，通常通过多层神经网络从数据中自动学习特征。",
                            "chunks": [
                                {
                                    "text": "深度学习是机器学习的一个分支，通常使用多层神经网络进行特征学习。",
                                    "document_id": 1,
                                    "score": 0.87,
                                }
                            ],
                            "cache_hit": False,
                            "cache_type": "none",
                            "semantic_similarity": None,
                            "matched_cached_question": None,
                        },
                        "error": None,
                        "trace_id": "a1b2c3d4e5f6",
                    }
                }
            },
        },
        400: {
            "description": "Bad request (empty question)",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "EMPTY_QUESTION",
                            "message": "question cannot be empty",
                            "details": None,
                        },
                        "trace_id": "badf00d00001",
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized (missing/invalid token)",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {"code": "UNAUTHORIZED", "message": "Not authenticated", "details": None},
                        "trace_id": "cafe1234dead",
                    }
                }
            },
        },
        503: {
            "description": "LLM upstream service failed",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "LLM_UPSTREAM_ERROR",
                            "message": "LLM service failed",
                            "details": "Upstream timeout",
                        },
                        "trace_id": "deadbeef0001",
                    }
                }
            },
        },
        500: {
            "description": "Internal chat error",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "CHAT_INTERNAL_ERROR",
                            "message": "Internal chat error",
                            "details": "Unexpected error",
                        },
                        "trace_id": "deadbeef0002",
                    }
                }
            },
        },
    },
)
def chat_api(
    req: ChatRequest,
    request: Request,
    current_user=Depends(get_current_user),
):
    rid = get_request_id()
    start = time.time()

    q = (req.question or "").strip()
    if not q:
        raise AppError(code="EMPTY_QUESTION", message="question cannot be empty", status_code=400)

    q_preview = q.replace("\n", " ")[:80]
    logger.info(
        f"/chat | rid={rid} | user={current_user.id} | mode={req.retrieval_mode} | top_k={req.top_k} | q_len={len(q)} | q_preview='{q_preview}'"
    )

    try:
        result = chat_with_rag(
            q,
            user_id=current_user.id,
            retrieval_mode=req.retrieval_mode,
            top_k=req.top_k,
        )

        elapsed = time.time() - start
        logger.info(
            f"/chat done | rid={rid} | user={current_user.id} | cache_type={result.get('cache_type')} | time={elapsed:.3f}s"
        )

        return APIResponse(
            success=True,
            data=result,
            error=None,
            trace_id=getattr(request.state, "trace_id", None),
        )

    except LLMServiceError as e:
        elapsed = time.time() - start
        logger.error(
            f"/chat llm_error | rid={rid} | user={current_user.id} | time={elapsed:.3f}s | error={e}"
        )
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
        logger.error(f"/chat error | rid={rid} | user={current_user.id} | time={elapsed:.3f}s | error={e}")
        raise AppError(
            code="CHAT_INTERNAL_ERROR",
            message="Internal chat error",
            status_code=500,
            details=str(e),
        )


@router.post(
    "/stream",
    summary="Chat with RAG (streaming)",
    description=(
        "Stream answer tokens progressively (non-JSON streaming).\n\n"
        "- Auth required\n"
        "- Request body contains `question`\n"
        "- Optional: `retrieval_mode`, `top_k`\n"
        "- Response is `text/plain` stream (NOT wrapped in `APIResponse`)\n"
        "- Frontend should read chunks incrementally (e.g. fetch + ReadableStream)"
    ),
    responses={
        200: {
            "description": "Plain text streaming response",
            "content": {
                "text/plain": {
                    "example": (
                        "深度学习是机器学习的一个分支，\n"
                        "通常通过多层神经网络学习特征。\n"
                    )
                }
            },
        },
        401: {
            "description": "Unauthorized (missing/invalid token)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Not authenticated"
                    }
                }
            },
        },
    },
)
def chat_stream_api(
    req: ChatRequest,
    current_user=Depends(get_current_user),
):
    """
    流式接口保持 text/plain（不包 APIResponse）
    """
    rid = get_request_id()
    q = (req.question or "").strip()
    if not q:
        raise AppError(code="EMPTY_QUESTION", message="question cannot be empty", status_code=400)

    q_preview = q.replace("\n", " ")[:80]
    logger.info(
        f"/chat/stream | rid={rid} | user={current_user.id} | mode={req.retrieval_mode} | top_k={req.top_k} | q_len={len(q)} | q_preview='{q_preview}'"
    )

    return StreamingResponse(
        stream_chat_with_rag(
            q,
            user_id=current_user.id,
            retrieval_mode=req.retrieval_mode,
            top_k=req.top_k,
        ),
        media_type="text/plain",
    )