import logging
import time
from typing import Any, Dict, Optional, List

from app.agent.graph import agent_graph
from app.exceptions import AppError
from app.services.request_context import get_request_id

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

    第11天增强：
    - 正式支持从接口透传 chat_history
    - 返回里补充 session_id 和 history_count，方便调试
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

    normalized_history = []
    for msg in (chat_history or []):
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

    final_session_id = session_id or f"agent-session-{user_id or 'anonymous'}"

    state = {
        "question": q,
        "session_id": final_session_id,
        "chat_history": normalized_history,
        "debug_info": {
            "user_id": user_id,
            "top_k": top_k,
            "rerank_top_n": rerank_top_n,
            "rerank_score_threshold": rerank_score_threshold,
        },
    }

    logger.info(
        "agent_chat start | rid=%s | user=%s | session_id=%s | q_len=%s | history_count=%s",
        rid,
        user_id,
        final_session_id,
        len(q),
        len(normalized_history),
    )

    try:
        result = agent_graph.invoke(state)

        payload = {
            "question": q,
            "session_id": final_session_id,
            "history_count": len(normalized_history),
            "route": result.get("route"),
            "rewritten_question": result.get("rewritten_question"),
            "answer": result.get("final_answer"),
            "retrieved_docs": result.get("retrieved_docs", []),
            "reranked_docs": result.get("reranked_docs", []),
            "cache_hit": result.get("cache_hit", False),
            "need_fallback": result.get("need_fallback", False),
            "fallback_reason": result.get("fallback_reason"),
            "debug_info": result.get("debug_info", {}),
        }

        elapsed = time.time() - start
        logger.info(
            "agent_chat done | rid=%s | user=%s | route=%s | cache_hit=%s | fallback=%s | time=%.3fs",
            rid,
            user_id,
            payload.get("route"),
            payload.get("cache_hit"),
            payload.get("need_fallback"),
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