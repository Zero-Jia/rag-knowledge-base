from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DocumentJobStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class DocumentJobStage(enum.Enum):
    UPLOAD = "upload"
    PARSE = "parse"
    PARENT_STORE = "parent_store"
    VECTOR_STORE = "vector_store"


class DocumentJob(Base):
    """Fine-grained indexing job status for uploaded documents."""

    __tablename__ = "document_jobs"
    __table_args__ = (
        Index("ix_document_jobs_doc_created", "document_id", "created_at"),
        Index("ix_document_jobs_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[DocumentJobStatus] = mapped_column(
        SAEnum(DocumentJobStatus),
        default=DocumentJobStatus.PENDING,
        nullable=False,
        index=True,
    )
    current_stage: Mapped[Optional[DocumentJobStage]] = mapped_column(
        SAEnum(DocumentJobStage),
        nullable=True,
        index=True,
    )
    stages: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
