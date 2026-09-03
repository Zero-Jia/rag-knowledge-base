"""P1-4：监控大盘 API 响应模型。"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class MetricSummary(BaseModel):
    """聚合概览：单用户在时间范围内的整体指标。"""

    total_requests: int = Field(0, description="总请求数")
    fallback_count: int = Field(0, description="触发 fallback 的请求数")
    fallback_rate: float = Field(0.0, description="fallback 率 (0-1)")

    react_triggered_count: int = Field(0, description="ReAct 触发数")
    react_triggered_rate: float = Field(0.0, description="ReAct 触发率 (0-1)")
    react_success_count: int = Field(
        0, description="ReAct 触发且未 fallback（抢救成功）数"
    )
    react_rescue_rate: float = Field(0.0, description="ReAct 抢救率 (0-1)")

    avg_latency_ms: Optional[float] = Field(None, description="平均端到端延迟 ms")
    p95_latency_ms: Optional[float] = Field(None, description="P95 延迟 ms")

    avg_token_total: Optional[float] = Field(None, description="平均 token 消耗")
    total_token_consumed: int = Field(0, description="时间范围内总 token 消耗")

    grounding_passed_count: int = Field(0, description="grounding 通过数")
    grounding_pass_rate: float = Field(0.0, description="grounding 通过率 (0-1)")

    cache_hit_count: int = Field(0, description="缓存命中数")
    cache_hit_rate: float = Field(0.0, description="缓存命中率 (0-1)")

    # P1-7: auto_merge（Small-to-Big）观测
    auto_merge_requests: int = Field(
        0, description="检索结果发生过 auto-merge（子块合并回父块）的请求数"
    )
    auto_merge_parent_chunks: int = Field(
        0, description="时间范围内 auto-merge 产生的父块总数"
    )
    auto_merge_rate: float = Field(
        0.0, description="auto-merge 请求占比 (0-1)"
    )

    start: Optional[str] = Field(None, description="查询起始时间 ISO")
    end: Optional[str] = Field(None, description="查询结束时间 ISO")


class MetricTimeseriesItem(BaseModel):
    """按日聚合的时间序列项。"""

    date: str = Field(..., description="日期 YYYY-MM-DD")
    request_count: int = Field(0, description="当日请求数")
    fallback_count: int = Field(0, description="当日 fallback 数")
    react_triggered_count: int = Field(0, description="当日 ReAct 触发数")
    avg_latency_ms: Optional[float] = Field(None, description="当日平均延迟 ms")
    avg_token_total: Optional[float] = Field(None, description="当日平均 token")
    grounding_passed_count: int = Field(0, description="当日 grounding 通过数")


class MetricRecentItem(BaseModel):
    """最近 N 条明细行（debug 用）。"""

    id: int
    chat_message_id: Optional[int] = None
    session_id: Optional[str] = None
    created_at: Optional[str] = None
    route: Optional[str] = None
    cache_hit: Optional[bool] = None
    need_react: Optional[bool] = None
    react_attempted: Optional[bool] = None
    react_reason: Optional[str] = None
    react_trigger_reason: Optional[str] = None
    react_status: Optional[str] = None
    react_tool_rounds: Optional[int] = None
    react_evidence_count: Optional[int] = None
    evidence_grade: Optional[str] = None
    grounding_passed: Optional[bool] = None
    grounding_reason: Optional[str] = None
    need_fallback: Optional[bool] = None
    fallback_reason: Optional[str] = None
    total_latency_ms: Optional[float] = None
    token_total: Optional[int] = None
    node_timings: Optional[dict[str, Any]] = None
    metadata_json: Optional[dict[str, Any]] = None


class ReactGroupStats(BaseModel):
    """ReAct 对比中单组（quick path 或 react）的统计。"""

    count: int = Field(0, description="该组样本数")
    fallback_count: int = Field(0, description="fallback 数")
    fallback_rate: Optional[float] = Field(None, description="fallback 率 (0-1)")
    avg_latency_ms: Optional[float] = Field(None, description="平均延迟 ms")
    avg_token_total: Optional[float] = Field(None, description="平均 token")
    grounding_pass_rate: Optional[float] = Field(None, description="grounding 通过率")
    # react 组专属
    avg_tool_rounds: Optional[float] = Field(None, description="平均工具轮数")
    avg_evidence_count: Optional[float] = Field(None, description="平均证据条数")
    success_count: Optional[int] = Field(
        None, description="ReAct 抢救成功数（未 fallback）"
    )
    rescue_rate: Optional[float] = Field(
        None, description="ReAct 抢救率 (0-1)"
    )


class ReactComparison(BaseModel):
    """ReAct vs quick path 对比结果。"""

    quick_path: ReactGroupStats
    react: ReactGroupStats
    delta_latency_ms: Optional[float] = Field(
        None, description="ReAct 比 quick path 平均多花多少延迟 ms"
    )
    delta_token_total: Optional[float] = Field(
        None, description="ReAct 比 quick path 平均多花多少 token"
    )
