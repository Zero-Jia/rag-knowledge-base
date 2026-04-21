from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ParentChunk(Base):
    """Parent chunk store for hierarchical RAG chunking.

    L1 and L2 chunks are stored here as retrievable parent context.
    L3 chunks remain in the vector store and reference these rows through
    parent_chunk_id/root_chunk_id in their metadata.
    """

    __tablename__ = "parent_chunks"
    __table_args__ = (
        UniqueConstraint("chunk_id", name="uq_parent_chunks_chunk_id"),
        Index("ix_parent_chunks_doc_level", "document_id", "chunk_level"),
        Index("ix_parent_chunks_doc_root", "document_id", "root_chunk_id"),
        Index("ix_parent_chunks_doc_parent", "document_id", "parent_chunk_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )
    parent_chunk_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        index=True,
    )
    root_chunk_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )
    chunk_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
