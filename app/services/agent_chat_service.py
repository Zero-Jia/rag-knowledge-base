import logging
import time
from typing import Any, Dict, Optional, List

from app.agent.graph import agent_graph
from app.exceptions import AppError
from app.services.request_context import get_request_id
from app.services.agent_memory_service import (
    get_session_history,
    overwrite_session_history,
    save_turn,
)

logger = logging.getLogger("rag.agent")


def agent_chat(
    question: str,
    *,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    top_k: int = 5,
    rerank_top_n: int = 3,
    rerank_score_threshold: float = 0.1,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Agent 版本聊天主入口（非流式）

    第12天增强：
    - 若传入 chat_history，则覆盖当前 session 的历史并使用它
    - 若未传入 chat_history，则自动从 session memory 读取历史
    - 回答完成后，自动保存当前轮对话
    """
    rid = get_request_id()
    start = time.time()

    q = (question or "").strip()
    if not q:
        raise AppError(
            code="EMPTY_QUESTION",
            message="question cannot be empty",
            status_code=400,
        )

    final_session_id = session_id or f"agent-session-{user_id or 'anonymous'}"

    # 1) 优先使用请求里显式传入的 chat_history
    if chat_history:
        normalized_history = []
        for msg in chat_history:
            role = (msg.get("role") or "").strip()
            content = (msg.get("content") or "").strip()
            if not role or not content:
                continue
            normalized_history.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        # 用请求中的历史覆盖当前 session 的历史
        overwrite_session_history(final_session_id, normalized_history)
        effective_history = normalized_history
        history_source = "request"
    else:
        # 2) 如果请求没传，就从 session memory 自动读取
        effective_history = get_session_history(final_session_id)
        history_source = "memory"

    state = {
        "question": q,
        "session_id": final_session_id,
        "chat_history": effective_history,
        "debug_info": {
            "user_id": user_id,
            "top_k": top_k,
            "rerank_top_n": rerank_top_n,
            "rerank_score_threshold": rerank_score_threshold,
            "history_source": history_source,
        },
    }

    logger.info(
        "agent_chat start | rid=%s | user=%s | session_id=%s | q_len=%s | history_count=%s | history_source=%s",
        rid,
        user_id,
        final_session_id,
        len(q),
        len(effective_history),
        history_source,
    )

    try:
        result = agent_graph.invoke(state)

        final_answer = result.get("final_answer") or ""

        # 3) 自动保存本轮对话
        if final_answer:
            save_turn(
                session_id=final_session_id,
                user_question=q,
                assistant_answer=final_answer,
            )

        latest_history = get_session_history(final_session_id)

        payload = {
            "question": q,
            "session_id": final_session_id,
            "history_source": history_source,
            "history_count": len(effective_history),
            "updated_history_count": len(latest_history),
            "route": result.get("route"),
            "rewritten_question": result.get("rewritten_question"),
            "answer": final_answer,
            "retrieved_docs": result.get("retrieved_docs", []),
            "reranked_docs": result.get("reranked_docs", []),
            "cache_hit": result.get("cache_hit", False),
            "need_fallback": result.get("need_fallback", False),
            "fallback_reason": result.get("fallback_reason"),
            "debug_info": result.get("debug_info", {}),
        }

        elapsed = time.time() - start
        logger.info(
            "agent_chat done | rid=%s | user=%s | route=%s | cache_hit=%s | fallback=%s | updated_history_count=%s | time=%.3fs",
            rid,
            user_id,
            payload.get("route"),
            payload.get("cache_hit"),
            payload.get("need_fallback"),
            payload.get("updated_history_count"),
            elapsed,
        )

        return payload

    except AppError:
        raise

    except Exception as e:
        elapsed = time.time() - start
        logger.error(
            "agent_chat fail | rid=%s | user=%s | time=%.3fs | error=%s",
            rid,
            user_id,
            elapsed,
            e,
        )
        raise AppError(
            code="AGENT_CHAT_INTERNAL_ERROR",
            message="Internal agent chat error",
            status_code=500,
            details=str(e),
        )