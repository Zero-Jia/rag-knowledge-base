from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentMetric(Base):
    """
    P1-3：每轮 agent 请求的关键指标持久化（一行 = 一轮 assistant 请求）。

    数据源：agent graph 执行结束后的 state + rag_trace + debug_info。
    用途：每日报表、ReAct vs quick path 效果对比、REACT_AGENT_ENABLED 灰度决策。
    写入由 metric_service.persist_agent_metric 完成，异常静默不影响主流程。
    原文答案不在此表存储（PII 考量），原文由 chat_messages 表持有。
    """

    __tablename__ = "agent_metrics"
    __table_args__ = (
        Index("ix_agent_metrics_user_created", "user_id", "created_at"),
        Index("ix_agent_metrics_session_created", "session_id", "created_at"),
        Index("ix_agent_metrics_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # 关联到该轮 assistant 消息（nullable 便于容错：save_turn 失败时 metric 仍可写入）
    chat_message_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("chat_messages.id"),
        nullable=True,
        index=True,
    )
    session_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # classify / cache
    route: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cache_hit: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # P1-2：ReAct 三层漏斗路由
    need_react: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    react_attempted: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    react_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    react_trigger_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    react_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    react_tool_rounds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    react_evidence_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # evidence grade
    evidence_grade: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    grade_metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # grounding 门控
    grounding_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    grounding_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # fallback
    need_fallback: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    fallback_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # 延迟与 token（来自 rag_trace）
    total_latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    node_timings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    token_prompt: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_completion: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 元数据（如 error 标记、source 等）
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
