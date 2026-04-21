from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Generator, List, Optional

from app.agent.debug import build_agent_debug_summary
from app.agent.graph import agent_graph
from app.core.config import settings
from app.schemas.rag_trace import create_rag_trace, record_timing, set_fallback_reason
from app.services.agent_memory_service import (
    get_session_history,
    overwrite_session_history,
    save_turn,
)
from app.services.request_context import get_request_id

logger = logging.getLogger("rag.agent.stream")


def _sse(event: str, data: Dict[str, Any]) -> str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
    )


def _normalize_history(chat_history: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for msg in chat_history or []:
        role = (msg.get("role") or "").strip()
        content = (msg.get("content") or "").strip()
        if not role or not content:
            continue
        normalized.append({"role": role, "content": content})
    return normalized


def _merge_graph_update(final_state: Dict[str, Any], update: Dict[str, Any]) -> str:
    """
    LangGraph default stream emits {node_name: state_update}.
    Nodes in this project return full AgentState, so update final_state with it.
    """
    node_name = "unknown"
    for key, value in update.items():
        node_name = str(key)
        if isinstance(value, dict):
            final_state.update(value)
    return node_name


def _step_payload(node_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
    debug_info = state.get("debug_info") or {}
    return {
        "node": node_name,
        "route": state.get("route"),
        "cache_hit": state.get("cache_hit", False),
        "need_query_expansion": state.get("need_query_expansion", False),
        "need_fallback": state.get("need_fallback", False),
        "fallback_reason": state.get("fallback_reason"),
        "retrieved_count": len(state.get("retrieved_docs") or []),
        "reranked_count": len(state.get("reranked_docs") or []),
        "expanded_query_count": len(state.get("expanded_queries") or []),
        "evidence_grade": state.get("evidence_grade"),
        "debug": {
            "classify_status": debug_info.get("classify_status"),
            "cache_status": debug_info.get("cache_status"),
            "retrieve_status": debug_info.get("retrieve_status"),
            "rerank_status": debug_info.get("rerank_status"),
            "query_expansion_status": debug_info.get("query_expansion_status"),
            "answer_status": debug_info.get("answer_status"),
            "fallback_status": debug_info.get("fallback_status"),
        },
    }


def stream_agent_chat_sse(
    question: str,
    *,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    top_k: int = 5,
    rerank_top_n: int = 3,
    rerank_score_threshold: float = 0.1,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> Generator[str, None, None]:
    """
    SSE generator for Agentic RAG.

    Events:
    - rag_step: graph/node progress
    - content: answer text chunks
    - trace: final rag_trace and debug summary
    - error: structured error
    - done: stream completion marker
    """
    rid = get_request_id()
    start = time.time()
    q = (question or "").strip()
    final_state: Dict[str, Any] = {}

    try:
        if not q:
            yield _sse(
                "error",
                {
                    "code": "EMPTY_QUESTION",
                    "message": "question cannot be empty",
                    "trace_id": rid,
                },
            )
            yield _sse("done", {"ok": False, "trace_id": rid})
            return

        final_session_id = session_id or f"agent-session-{user_id or 'anonymous'}"

        if chat_history:
            normalized_history = _normalize_history(chat_history)
            overwrite_session_history(final_session_id, normalized_history, user_id=user_id)
            effective_history = normalized_history
            history_source = "request"
        else:
            effective_history = get_session_history(final_session_id, user_id=user_id)
            history_source = "memory"

        state: Dict[str, Any] = {
            "question": q,
            "session_id": final_session_id,
            "chat_history": effective_history,
            "rag_trace": create_rag_trace(
                original_query=q,
                retrieval_mode="agentic_stream",
            ),
            "debug_info": {
                "user_id": user_id,
                "top_k": top_k,
                "rerank_top_n": rerank_top_n,
                "rerank_score_threshold": rerank_score_threshold,
                "history_source": history_source,
            },
        }
        final_state.update(state)

        yield _sse(
            "rag_step",
            {
                "node": "start",
                "session_id": final_session_id,
                "history_source": history_source,
                "history_count": len(effective_history),
                "trace_id": rid,
            },
        )

        for update in agent_graph.stream(state):
            node_name = _merge_graph_update(final_state, update)
            yield _sse("rag_step", _step_payload(node_name, final_state))

        final_answer = final_state.get("final_answer") or ""
        if final_answer:
            save_turn(
                session_id=final_session_id,
                user_question=q,
                assistant_answer=final_answer,
                user_id=user_id,
                rag_trace=final_state.get("rag_trace"),
            )

        chunk_size = max(1, int(getattr(settings, "CHAT_STREAM_CHUNK_SIZE", 20)))
        for index in range(0, len(final_answer), chunk_size):
            yield _sse(
                "content",
                {
                    "text": final_answer[index : index + chunk_size],
                    "index": index // chunk_size,
                },
            )

        elapsed = time.time() - start
        rag_trace = final_state.get("rag_trace") or {}
        if isinstance(rag_trace, dict):
            record_timing(rag_trace, "agent_stream_total_ms", elapsed * 1000.0)

        yield _sse(
            "trace",
            {
                "question": q,
                "session_id": final_session_id,
                "route": final_state.get("route"),
                "cache_hit": final_state.get("cache_hit", False),
                "need_fallback": final_state.get("need_fallback", False),
                "fallback_reason": final_state.get("fallback_reason"),
                "retrieved_docs": final_state.get("retrieved_docs", []),
                "reranked_docs": final_state.get("reranked_docs", []),
                "debug_info": build_agent_debug_summary(final_state),
                "rag_trace": rag_trace,
            },
        )

        yield _sse(
            "done",
            {
                "ok": True,
                "trace_id": rid,
                "elapsed_ms": round(elapsed * 1000.0, 3),
            },
        )

        logger.info(
            "agent stream done | rid=%s | user=%s | session_id=%s | route=%s | cache_hit=%s | time=%.3fs",
            rid,
            user_id,
            final_session_id,
            final_state.get("route"),
            final_state.get("cache_hit", False),
            elapsed,
        )

    except Exception as exc:
        elapsed = time.time() - start
        rag_trace = final_state.get("rag_trace") or {}
        if isinstance(rag_trace, dict):
            set_fallback_reason(rag_trace, str(exc))
            record_timing(rag_trace, "agent_stream_total_ms", elapsed * 1000.0)

        logger.exception("agent stream failed | rid=%s | user=%s | error=%s", rid, user_id, exc)
        yield _sse(
            "error",
            {
                "code": "AGENT_STREAM_ERROR",
                "message": "Agent stream failed",
                "details": str(exc),
                "trace_id": rid,
            },
        )
        if isinstance(rag_trace, dict):
            yield _sse("trace", {"rag_trace": rag_trace})
        yield _sse(
            "done",
            {
                "ok": False,
                "trace_id": rid,
                "elapsed_ms": round(elapsed * 1000.0, 3),
            },
        )
