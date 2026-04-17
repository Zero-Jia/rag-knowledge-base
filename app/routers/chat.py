import time
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.security import get_current_user
from app.services.chat_service import chat_with_rag, stream_chat_with_rag
from app.services.agent_chat_service import agent_chat
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
    "/agent",
    summary="Chat with Agentic RAG (non-streaming)",
    description=(
        "Generate an answer using Agentic RAG graph.\n\n"
        "- Auth required\n"
        "- Request body contains `question`\n"
        "- Uses classify / cache / rewrite / retrieve / rerank / fallback / answer graph\n"
        "- Response is wrapped in `APIResponse`"
    ),
    response_model=APIResponse,
)
def chat_agent_api(
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
        f"/chat/agent | rid={rid} | user={current_user.id} | top_k={req.top_k} | q_len={len(q)} | q_preview='{q_preview}'"
    )

    try:
        result = agent_chat(
            q,
            user_id=current_user.id,
            session_id=f"user-{current_user.id}",
            top_k=req.top_k or 5,
            rerank_top_n=3,
            rerank_score_threshold=0.1,
            chat_history=[],
        )

        elapsed = time.time() - start
        logger.info(
            f"/chat/agent done | rid={rid} | user={current_user.id} | route={result.get('route')} | cache_hit={result.get('cache_hit')} | time={elapsed:.3f}s"
        )

        return APIResponse(
            success=True,
            data=result,
            error=None,
            trace_id=getattr(request.state, "trace_id", None),
        )

    except AppError:
        raise

    except Exception as e:
        elapsed = time.time() - start
        logger.error(
            f"/chat/agent error | rid={rid} | user={current_user.id} | time={elapsed:.3f}s | error={e}"
        )
        raise AppError(
            code="AGENT_CHAT_INTERNAL_ERROR",
            message="Internal agent chat error",
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
)
def chat_stream_api(
    req: ChatRequest,
    current_user=Depends(get_current_user),
):
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