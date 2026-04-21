from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.chat_session import ChatMessage, ChatSession

MAX_HISTORY_MESSAGES = 20


def _normalize_message(role: str, content: str) -> Optional[Dict[str, str]]:
    role = (role or "").strip()
    content = (content or "").strip()
    if not role or not content:
        return None
    return {"role": role, "content": content}


def _make_title(text: str) -> str:
    title = " ".join((text or "").strip().split())
    return title[:80] if title else "New chat"


def get_or_create_session(
    db: Session,
    *,
    session_id: str,
    user_id: Optional[int] = None,
    title: Optional[str] = None,
) -> ChatSession:
    existing = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    if existing:
        if user_id is not None and existing.user_id is None:
            existing.user_id = user_id
        if title and not existing.title:
            existing.title = title
        existing.updated_at = datetime.utcnow()
        db.flush()
        return existing

    session = ChatSession(
        session_id=session_id,
        user_id=user_id,
        title=title,
        metadata_json={},
    )
    db.add(session)
    db.flush()
    return session


def get_session_history(
    session_id: str,
    *,
    limit: int = MAX_HISTORY_MESSAGES,
    user_id: Optional[int] = None,
) -> List[Dict[str, str]]:
    if not session_id:
        return []

    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if not session:
            return []
        if user_id is not None and session.user_id not in (None, user_id):
            return []

        rows = (
            db.query(ChatMessage)
            .filter(ChatMessage.chat_session_id == session.id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return [{"role": row.role, "content": row.content} for row in rows]
    finally:
        db.close()


def append_session_message(
    session_id: str,
    role: str,
    content: str,
    *,
    user_id: Optional[int] = None,
    rag_trace: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[ChatMessage]:
    message = _normalize_message(role, content)
    if not session_id or message is None:
        return None

    db = SessionLocal()
    try:
        title = _make_title(content) if message["role"] == "user" else None
        session = get_or_create_session(
            db,
            session_id=session_id,
            user_id=user_id,
            title=title,
        )
        row = ChatMessage(
            chat_session_id=session.id,
            session_id=session_id,
            user_id=user_id if user_id is not None else session.user_id,
            role=message["role"],
            content=message["content"],
            rag_trace=rag_trace,
            metadata_json=metadata or {},
        )
        session.updated_at = datetime.utcnow()
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def save_turn(
    session_id: str,
    user_question: str,
    assistant_answer: str,
    *,
    user_id: Optional[int] = None,
    rag_trace: Optional[Dict[str, Any]] = None,
) -> None:
    append_session_message(
        session_id,
        "user",
        user_question,
        user_id=user_id,
        metadata={"turn_role": "question"},
    )
    append_session_message(
        session_id,
        "assistant",
        assistant_answer,
        user_id=user_id,
        rag_trace=rag_trace,
        metadata={"turn_role": "answer"},
    )


def overwrite_session_history(
    session_id: str,
    chat_history: Optional[List[Dict[str, str]]],
    *,
    user_id: Optional[int] = None,
) -> None:
    if not session_id:
        return

    normalized: List[Dict[str, str]] = []
    for msg in chat_history or []:
        item = _normalize_message(msg.get("role", ""), msg.get("content", ""))
        if item:
            normalized.append(item)
    normalized = normalized[-MAX_HISTORY_MESSAGES:]

    db = SessionLocal()
    try:
        title = None
        for item in normalized:
            if item["role"] == "user":
                title = _make_title(item["content"])
                break

        session = get_or_create_session(
            db,
            session_id=session_id,
            user_id=user_id,
            title=title,
        )
        db.query(ChatMessage).filter(ChatMessage.chat_session_id == session.id).delete(
            synchronize_session=False
        )
        for item in normalized:
            db.add(
                ChatMessage(
                    chat_session_id=session.id,
                    session_id=session_id,
                    user_id=user_id if user_id is not None else session.user_id,
                    role=item["role"],
                    content=item["content"],
                    metadata_json={"source": "overwrite_session_history"},
                )
            )
        session.updated_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def clear_session_history(session_id: str, *, user_id: Optional[int] = None) -> None:
    if not session_id:
        return

    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if not session:
            return
        if user_id is not None and session.user_id not in (None, user_id):
            return
        db.query(ChatMessage).filter(ChatMessage.chat_session_id == session.id).delete(
            synchronize_session=False
        )
        session.updated_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def list_chat_sessions(
    *,
    user_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        query = db.query(ChatSession)
        if user_id is not None:
            query = query.filter(ChatSession.user_id == user_id)

        total = query.count()
        rows = (
            query.order_by(ChatSession.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "items": [
                {
                    "session_id": row.session_id,
                    "user_id": row.user_id,
                    "title": row.title,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in rows
            ],
            "total": total,
        }
    finally:
        db.close()


def get_session_messages(
    session_id: str,
    *,
    user_id: Optional[int] = None,
    include_trace: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if not session:
            return {"session_id": session_id, "items": [], "total": 0}
        if user_id is not None and session.user_id not in (None, user_id):
            return {"session_id": session_id, "items": [], "total": 0}

        query = db.query(ChatMessage).filter(ChatMessage.chat_session_id == session.id)
        total = query.count()
        rows = query.order_by(ChatMessage.id.asc()).offset(offset).limit(limit).all()

        items: List[Dict[str, Any]] = []
        for row in rows:
            item: Dict[str, Any] = {
                "id": row.id,
                "session_id": row.session_id,
                "role": row.role,
                "content": row.content,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            if include_trace:
                item["rag_trace"] = row.rag_trace
            items.append(item)

        return {
            "session_id": session_id,
            "items": items,
            "total": total,
        }
    finally:
        db.close()
