import time
import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.security import get_current_user
from app.services.chat_service import chat_with_rag, stream_chat_with_rag
from app.services.agent_chat_service import agent_chat
from app.services.agent_stream_service import stream_agent_chat_sse
from app.services.agent_memory_service import get_session_messages, list_chat_sessions
from app.services.llm_service import LLMServiceError
from app.services.request_context import get_request_id
from app.schemas.common import APIResponse
from app.schemas.chat import ChatRequest
from app.schemas.agent_chat import AgentChatRequest
from app.exceptions import AppError

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger("api.chat")


@router.post(
    "/",
    summary="Chat with RAG (non-streaming)",
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
        "- Supports chat_history for multi-turn followup\n"
        "- Response is wrapped in APIResponse"
    ),
    response_model=APIResponse,
)
def chat_agent_api(
    req: AgentChatRequest,
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
        "/chat/agent | rid=%s | user=%s | session_id=%s | top_k=%s | history_count=%s | q_len=%s | q_preview='%s'",
        rid,
        current_user.id,
        req.session_id,
        req.top_k,
        len(req.chat_history),
        len(q),
        q_preview,
    )

    try:
        result = agent_chat(
            q,
            user_id=current_user.id,
            session_id=req.session_id,
            top_k=req.top_k,
            rerank_top_n=req.rerank_top_n,
            rerank_score_threshold=req.rerank_score_threshold,
            chat_history=[msg.model_dump() for msg in req.chat_history],
        )

        elapsed = time.time() - start
        logger.info(
            "/chat/agent done | rid=%s | user=%s | route=%s | cache_hit=%s | time=%.3fs",
            rid,
            current_user.id,
            result.get("route"),
            result.get("cache_hit"),
            elapsed,
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
            "/chat/agent error | rid=%s | user=%s | time=%.3fs | error=%s",
            rid,
            current_user.id,
            elapsed,
            e,
        )
        raise AppError(
            code="AGENT_CHAT_INTERNAL_ERROR",
            message="Internal agent chat error",
            status_code=500,
            details=str(e),
        )


@router.post(
    "/agent/stream",
    summary="Chat with Agentic RAG (SSE streaming)",
    description=(
        "Stream Agentic RAG progress and answer using Server-Sent Events.\n\n"
        "Events: `rag_step`, `content`, `trace`, `error`, `done`."
    ),
)
def chat_agent_stream_api(
    req: AgentChatRequest,
    current_user=Depends(get_current_user),
):
    rid = get_request_id()
    q = (req.question or "").strip()
    if not q:
        raise AppError(code="EMPTY_QUESTION", message="question cannot be empty", status_code=400)

    q_preview = q.replace("\n", " ")[:80]
    logger.info(
        "/chat/agent/stream | rid=%s | user=%s | session_id=%s | top_k=%s | history_count=%s | q_len=%s | q_preview='%s'",
        rid,
        current_user.id,
        req.session_id,
        req.top_k,
        len(req.chat_history),
        len(q),
        q_preview,
    )

    return StreamingResponse(
        stream_agent_chat_sse(
            q,
            user_id=current_user.id,
            session_id=req.session_id,
            top_k=req.top_k,
            rerank_top_n=req.rerank_top_n,
            rerank_score_threshold=req.rerank_score_threshold,
            chat_history=[msg.model_dump() for msg in req.chat_history],
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/agent/sessions",
    summary="List persistent agent chat sessions",
    response_model=APIResponse,
)
def list_agent_chat_sessions_api(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
):
    data = list_chat_sessions(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return APIResponse(
        success=True,
        data=data,
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get(
    "/agent/sessions/{session_id}/messages",
    summary="Get persistent messages for an agent chat session",
    response_model=APIResponse,
)
def get_agent_chat_session_messages_api(
    session_id: str,
    request: Request,
    include_trace: bool = Query(False),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
):
    data = get_session_messages(
        session_id=session_id,
        user_id=current_user.id,
        include_trace=include_trace,
        limit=limit,
        offset=offset,
    )
    return APIResponse(
        success=True,
        data=data,
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.post(
    "/stream",
    summary="Chat with RAG (streaming)",
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
