from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.chat_session_service import (
    MAX_HISTORY_MESSAGES,
    append_session_message as _append_session_message,
    clear_session_history as _clear_session_history,
    get_session_history as _get_session_history,
    get_session_messages,
    list_chat_sessions,
    overwrite_session_history as _overwrite_session_history,
    save_turn as _save_turn,
)


def get_session_history(
    session_id: str,
    *,
    limit: int = MAX_HISTORY_MESSAGES,
    user_id: Optional[int] = None,
) -> List[Dict[str, str]]:
    """
    Persistent replacement for the old in-memory session history.
    """
    return _get_session_history(session_id, limit=limit, user_id=user_id)


def append_session_message(
    session_id: str,
    role: str,
    content: str,
    *,
    user_id: Optional[int] = None,
    rag_trace: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    _append_session_message(
        session_id,
        role,
        content,
        user_id=user_id,
        rag_trace=rag_trace,
        metadata=metadata,
    )


def save_turn(
    session_id: str,
    user_question: str,
    assistant_answer: str,
    *,
    user_id: Optional[int] = None,
    rag_trace: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Save one user/assistant turn. rag_trace is stored on the assistant message.
    """
    _save_turn(
        session_id,
        user_question,
        assistant_answer,
        user_id=user_id,
        rag_trace=rag_trace,
    )


def overwrite_session_history(
    session_id: str,
    chat_history: Optional[List[Dict[str, str]]],
    *,
    user_id: Optional[int] = None,
) -> None:
    _overwrite_session_history(session_id, chat_history, user_id=user_id)


def clear_session_history(session_id: str, *, user_id: Optional[int] = None) -> None:
    _clear_session_history(session_id, user_id=user_id)


__all__ = [
    "MAX_HISTORY_MESSAGES",
    "get_session_history",
    "append_session_message",
    "save_turn",
    "overwrite_session_history",
    "clear_session_history",
    "list_chat_sessions",
    "get_session_messages",
]
