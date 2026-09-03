"""P1-4：监控大盘 API（聚合 agent_metrics 表查询）。

鉴权：复用 get_current_user，已登录用户默认只看自己的 metric（租户隔离）。
全部只读查询，不改 agent/graph/prompt。
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.schemas.common import APIResponse
from app.schemas.metrics import (
    MetricRecentItem,
    MetricSummary,
    MetricTimeseriesItem,
    ReactComparison,
)
from app.security import get_current_user
from app.services.metric_service import (
    get_metrics_summary,
    get_metrics_timeseries,
    get_recent_metrics,
    get_react_comparison,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])
logger = logging.getLogger("api.metrics")


@router.get(
    "/summary",
    summary="Agent metrics summary (aggregated overview)",
    description=(
        "Aggregate overview of agent metrics in a time range.\n\n"
        "- Auth required; scoped to current user (tenant isolation)\n"
        "- Supports start/end (ISO 8601) and session_id filters\n"
        "- Returns total requests / fallback rate / react trigger rate / "
        "avg & p95 latency / avg & total tokens / grounding pass rate / cache hit rate"
    ),
    response_model=APIResponse,
)
def metrics_summary_api(
    current_user=Depends(get_current_user),
    start: Optional[str] = Query(None, description="ISO 8601 start time"),
    end: Optional[str] = Query(None, description="ISO 8601 end time"),
    session_id: Optional[str] = Query(None, description="Filter by session id"),
):
    data = get_metrics_summary(
        user_id=current_user.id,
        start=start,
        end=end,
        session_id=session_id,
    )
    return APIResponse(success=True, data=MetricSummary(**data))


@router.get(
    "/timeseries",
    summary="Agent metrics daily timeseries",
    description=(
        "Daily-aggregated timeseries of agent metrics.\n\n"
        "- Auth required; scoped to current user\n"
        "- Returns list of {date, request_count, fallback_count, "
        "react_triggered_count, avg_latency_ms, avg_token_total, "
        "grounding_passed_count} ordered by date asc"
    ),
    response_model=APIResponse,
)
def metrics_timeseries_api(
    current_user=Depends(get_current_user),
    start: Optional[str] = Query(None, description="ISO 8601 start time"),
    end: Optional[str] = Query(None, description="ISO 8601 end time"),
    session_id: Optional[str] = Query(None, description="Filter by session id"),
):
    rows = get_metrics_timeseries(
        user_id=current_user.id,
        start=start,
        end=end,
        session_id=session_id,
    )
    items = [MetricTimeseriesItem(**r) for r in rows]
    return APIResponse(success=True, data=items)


@router.get(
    "/recent",
    summary="Recent agent metric rows (debug)",
    description=(
        "Recent N agent metric rows for debugging.\n\n"
        "- Auth required; scoped to current user\n"
        "- Ordered by created_at desc\n"
        "- limit clamped to [1, 200], default 20"
    ),
    response_model=APIResponse,
)
def metrics_recent_api(
    current_user=Depends(get_current_user),
    limit: int = Query(20, ge=1, le=200, description="Number of rows to return"),
    session_id: Optional[str] = Query(None, description="Filter by session id"),
):
    rows = get_recent_metrics(
        user_id=current_user.id,
        limit=limit,
        session_id=session_id,
    )
    items = [MetricRecentItem(**r) for r in rows]
    return APIResponse(success=True, data=items)


@router.get(
    "/react",
    summary="ReAct vs quick path comparison",
    description=(
        "Compare ReAct (react_attempted=True) vs quick path (react_attempted "
        "False/None) groups.\n\n"
        "- Auth required; scoped to current user\n"
        "- Returns per-group {count, fallback_rate, avg_latency_ms, "
        "avg_token_total, grounding_pass_rate} plus react-specific "
        "{avg_tool_rounds, avg_evidence_count, success_count, rescue_rate}\n"
        "- delta_latency_ms / delta_token_total show react minus quick path"
    ),
    response_model=APIResponse,
)
def metrics_react_api(
    current_user=Depends(get_current_user),
    start: Optional[str] = Query(None, description="ISO 8601 start time"),
    end: Optional[str] = Query(None, description="ISO 8601 end time"),
    session_id: Optional[str] = Query(None, description="Filter by session id"),
):
    data = get_react_comparison(
        user_id=current_user.id,
        start=start,
        end=end,
        session_id=session_id,
    )
    return APIResponse(success=True, data=ReactComparison(**data))
