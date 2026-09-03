"""
P1-3：Agent 指标持久化服务。

从 agent graph 执行结束后的 state（含 rag_trace/debug_info）提取关键指标，
写入 agent_metrics 表。异常静默处理，绝不影响主流程。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import Integer

from app.database import SessionLocal
from app.models.metric import AgentMetric

logger = logging.getLogger("rag.metric")


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    return bool(value)


def _extract_total_latency(timing: Optional[Dict[str, Any]]) -> Optional[float]:
    """优先取 agent_total_ms / agent_stream_total_ms，否则取 timing 最大值兜底。"""
    if not isinstance(timing, dict):
        return None
    for key in ("agent_total_ms", "agent_stream_total_ms"):
        val = timing.get(key)
        if val is not None:
            return _safe_float(val)
    # 兜底：取所有 stage 延迟之和
    if timing:
        total = 0.0
        has_value = False
        for v in timing.values():
            f = _safe_float(v)
            if f is not None:
                total += f
                has_value = True
        return total if has_value else None
    return None


def persist_agent_metric(
    *,
    state: Dict[str, Any],
    session_id: Optional[str],
    user_id: Optional[int],
    chat_message_id: Optional[int] = None,
    source: str = "agent_chat",
    error: Optional[str] = None,
    elapsed_ms: Optional[float] = None,
) -> None:
    """
    从 agent 最终 state 提取指标写入 agent_metrics 表。

    - 写入失败只 log warning，不抛异常，不阻断主流程。
    - chat_message_id 由调用方在 save_turn 之后传入（P1-3 改造后 save_turn 返回 ChatMessage）。
    - 异常路径（agent 抛错）也写入一行，记录 fallback/error，便于统计失败率。
    """
    try:
        rag_trace = state.get("rag_trace") or {}
        if not isinstance(rag_trace, dict):
            rag_trace = {}
        debug_info = state.get("debug_info") or {}
        if not isinstance(debug_info, dict):
            debug_info = {}

        timing = rag_trace.get("timing") if isinstance(rag_trace.get("timing"), dict) else {}
        token_total = (
            rag_trace.get("token_usage", {}).get("total", {})
            if isinstance(rag_trace.get("token_usage"), dict)
            else {}
        )

        # 总延迟：优先调用方传入的 elapsed_ms（端到端计时），其次 rag_trace
        total_latency = _safe_float(elapsed_ms) or _extract_total_latency(timing)

        meta: Dict[str, Any] = {"source": source}
        # P3-2：注入拦截标记（直接注入命中 / 间接注入证据全被剔除）
        if state.get("injection_blocked"):
            meta["injection_blocked"] = True
        if debug_info.get("injection_filtered_count"):
            meta["injection_filtered_count"] = debug_info.get("injection_filtered_count")
        if error:
            meta["error"] = error

        row = AgentMetric(
            chat_message_id=chat_message_id,
            session_id=session_id,
            user_id=user_id,
            route=state.get("route"),
            cache_hit=_safe_bool(state.get("cache_hit")),
            need_react=_safe_bool(state.get("need_react")),
            react_attempted=_safe_bool(state.get("react_attempted")),
            react_reason=state.get("react_reason"),
            react_trigger_reason=debug_info.get("react_trigger_reason"),
            react_status=debug_info.get("react_status"),
            react_tool_rounds=_safe_int(debug_info.get("react_tool_rounds")),
            react_evidence_count=_safe_int(debug_info.get("react_evidence_count")),
            evidence_grade=state.get("evidence_grade"),
            grade_metrics=state.get("grade_metrics") if isinstance(state.get("grade_metrics"), dict) else None,
            grounding_passed=_safe_bool(state.get("grounding_passed")),
            grounding_reason=state.get("grounding_reason"),
            need_fallback=_safe_bool(state.get("need_fallback")),
            fallback_reason=state.get("fallback_reason"),
            total_latency_ms=total_latency,
            node_timings=timing if timing else None,
            token_prompt=_safe_int(token_total.get("prompt")),
            token_completion=_safe_int(token_total.get("completion")),
            token_total=_safe_int(token_total.get("total")),
            metadata_json=meta,
        )

        db = SessionLocal()
        try:
            db.add(row)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning("persist_agent_metric failed (suppressed) | error=%s", exc)


# ---------------------------------------------------------------------------
# P1-4：监控大盘聚合查询（只读）
# ---------------------------------------------------------------------------

from datetime import datetime  # noqa: E402

from sqlalchemy import func  # noqa: E402


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    """容错解析 ISO 时间字符串；None/空返回 None。"""
    if not value:
        return None
    try:
        # 兼容带 Z / 带时区的 ISO 串
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _apply_filters(
    query,
    *,
    user_id: Optional[int],
    start: Optional[datetime],
    end: Optional[datetime],
    session_id: Optional[str],
):
    """通用过滤条件拼装：user_id 强制租户隔离，start/end/session_id 可选。"""
    if user_id is not None:
        query = query.filter(AgentMetric.user_id == user_id)
    if start is not None:
        query = query.filter(AgentMetric.created_at >= start)
    if end is not None:
        query = query.filter(AgentMetric.created_at <= end)
    if session_id:
        query = query.filter(AgentMetric.session_id == session_id)
    return query


def _percentile(values: list, p: float) -> Optional[float]:
    """简单 P 分位数计算（样本量小，避免引入 numpy）。
    values: 已排序或未排序的数值列表；p: 0-1。
    """
    if not values:
        return None
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[f])
    return float(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


def get_metrics_summary(
    *,
    user_id: Optional[int],
    start: Optional[str] = None,
    end: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """聚合概览：总数/fallback/react/延迟/token/grounding/cache。"""
    start_dt = _parse_time(start)
    end_dt = _parse_time(end)

    db = SessionLocal()
    try:
        base = db.query(AgentMetric)
        base = _apply_filters(
            base, user_id=user_id, start=start_dt, end=end_dt, session_id=session_id
        )

        total = base.count()

        if total == 0:
            return {
                "total_requests": 0,
                "fallback_count": 0,
                "fallback_rate": 0.0,
                "react_triggered_count": 0,
                "react_triggered_rate": 0.0,
                "react_success_count": 0,
                "react_rescue_rate": 0.0,
                "avg_latency_ms": None,
                "p95_latency_ms": None,
                "avg_token_total": None,
                "total_token_consumed": 0,
                "grounding_passed_count": 0,
                "grounding_pass_rate": 0.0,
                "cache_hit_count": 0,
                "cache_hit_rate": 0.0,
                "auto_merge_requests": 0,
                "auto_merge_parent_chunks": 0,
                "auto_merge_rate": 0.0,
                "injection_blocked_count": 0,
                "injection_blocked_rate": 0.0,
                "injection_filtered_requests": 0,
                "start": start,
                "end": end,
            }

        fallback_count = base.filter(AgentMetric.need_fallback.is_(True)).count()
        react_q = base.filter(AgentMetric.react_attempted.is_(True))
        react_triggered = react_q.count()
        react_success = react_q.filter(AgentMetric.need_fallback.is_(False)).count()

        grounding_passed = base.filter(
            AgentMetric.grounding_passed.is_(True)
        ).count()
        cache_hit = base.filter(AgentMetric.cache_hit.is_(True)).count()

        # 聚合 avg/sum
        agg = base.with_entities(
            func.avg(AgentMetric.total_latency_ms),
            func.sum(AgentMetric.token_total),
            func.avg(AgentMetric.token_total),
        ).one()
        avg_latency = float(agg[0]) if agg[0] is not None else None
        total_token = int(agg[1] or 0)
        avg_token = float(agg[2]) if agg[2] is not None else None

        # P95 延迟：拉全量 latency 列计算（样本量小可接受）
        latency_vals = [
            row[0]
            for row in base.with_entities(AgentMetric.total_latency_ms).all()
            if row[0] is not None
        ]
        p95_latency = _percentile(latency_vals, 0.95)

        # P1-7: auto_merge（Small-to-Big）观测 + P3-2 注入过滤观测。
        # grade_metrics 为 JSON 列，SQLite 无法 SQL 层聚合，
        # 样本量小，Python 层解析可接受
        auto_merge_requests = 0
        auto_merge_parent_chunks = 0
        injection_filtered_requests = 0
        for (gm,) in base.with_entities(AgentMetric.grade_metrics).all():
            if not isinstance(gm, dict):
                continue
            merged = _safe_int(gm.get("auto_merged_count")) or 0
            if merged > 0:
                auto_merge_requests += 1
                auto_merge_parent_chunks += merged
            if (_safe_int(gm.get("injection_filtered_count")) or 0) > 0:
                injection_filtered_requests += 1

        # P3-2：注入拦截观测 —— fallback_reason 枚举值 SQL 层可过滤
        injection_blocked_count = base.filter(
            AgentMetric.fallback_reason == "injection_blocked"
        ).count()

        def _rate(num: int, den: int) -> float:
            return round(num / den, 4) if den else 0.0

        return {
            "total_requests": total,
            "fallback_count": fallback_count,
            "fallback_rate": _rate(fallback_count, total),
            "react_triggered_count": react_triggered,
            "react_triggered_rate": _rate(react_triggered, total),
            "react_success_count": react_success,
            "react_rescue_rate": _rate(react_success, react_triggered),
            "avg_latency_ms": round(avg_latency, 3) if avg_latency is not None else None,
            "p95_latency_ms": round(p95_latency, 3) if p95_latency is not None else None,
            "avg_token_total": round(avg_token, 3) if avg_token is not None else None,
            "total_token_consumed": total_token,
            "grounding_passed_count": grounding_passed,
            "grounding_pass_rate": _rate(grounding_passed, total),
            "cache_hit_count": cache_hit,
            "cache_hit_rate": _rate(cache_hit, total),
            "auto_merge_requests": auto_merge_requests,
            "auto_merge_parent_chunks": auto_merge_parent_chunks,
            "auto_merge_rate": _rate(auto_merge_requests, total),
            "injection_blocked_count": injection_blocked_count,
            "injection_blocked_rate": _rate(injection_blocked_count, total),
            "injection_filtered_requests": injection_filtered_requests,
            "start": start,
            "end": end,
        }
    finally:
        db.close()


def get_metrics_timeseries(
    *,
    user_id: Optional[int],
    start: Optional[str] = None,
    end: Optional[str] = None,
    session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """按日聚合时间序列。日期用 SQLite 的 date() 函数提取。"""
    start_dt = _parse_time(start)
    end_dt = _parse_time(end)

    db = SessionLocal()
    try:
        # SQLite: func.date 提取 YYYY-MM-DD
        day_col = func.date(AgentMetric.created_at).label("day")
        q = (
            db.query(
                day_col,
                func.count(AgentMetric.id).label("request_count"),
                func.sum(
                    func.cast(AgentMetric.need_fallback, Integer)
                ).label("fallback_count"),
                func.sum(
                    func.cast(AgentMetric.react_attempted, Integer)
                ).label("react_triggered_count"),
                func.avg(AgentMetric.total_latency_ms).label("avg_latency_ms"),
                func.avg(AgentMetric.token_total).label("avg_token_total"),
                func.sum(
                    func.cast(AgentMetric.grounding_passed, Integer)
                ).label("grounding_passed_count"),
            )
            .filter(AgentMetric.user_id == user_id if user_id is not None else True)
        )
        if start_dt is not None:
            q = q.filter(AgentMetric.created_at >= start_dt)
        if end_dt is not None:
            q = q.filter(AgentMetric.created_at <= end_dt)
        if session_id:
            q = q.filter(AgentMetric.session_id == session_id)
        q = q.group_by(day_col).order_by(day_col.asc())

        rows = q.all()
        return [
            {
                "date": str(r.day) if r.day is not None else "",
                "request_count": int(r.request_count or 0),
                "fallback_count": int(r.fallback_count or 0),
                "react_triggered_count": int(r.react_triggered_count or 0),
                "avg_latency_ms": round(float(r.avg_latency_ms), 3)
                if r.avg_latency_ms is not None
                else None,
                "avg_token_total": round(float(r.avg_token_total), 3)
                if r.avg_token_total is not None
                else None,
                "grounding_passed_count": int(r.grounding_passed_count or 0),
            }
            for r in rows
        ]
    finally:
        db.close()


def get_recent_metrics(
    *,
    user_id: Optional[int],
    limit: int = 20,
    session_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """最近 N 条明细行（按 created_at desc）。"""
    db = SessionLocal()
    try:
        q = db.query(AgentMetric)
        if user_id is not None:
            q = q.filter(AgentMetric.user_id == user_id)
        if session_id:
            q = q.filter(AgentMetric.session_id == session_id)
        rows = (
            q.order_by(AgentMetric.created_at.desc(), AgentMetric.id.desc())
            .limit(max(1, min(limit, 200)))
            .all()
        )
        return [_metric_row_to_dict(r) for r in rows]
    finally:
        db.close()


def get_react_comparison(
    *,
    user_id: Optional[int],
    start: Optional[str] = None,
    end: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """ReAct vs quick path 对比。react_attempted=True 一组，False/None 一组。"""
    start_dt = _parse_time(start)
    end_dt = _parse_time(end)

    def _group_stats(filter_react: bool) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            if filter_react:
                cond = AgentMetric.react_attempted.is_(True)
            else:
                cond = AgentMetric.react_attempted.isnot(True)
            q = db.query(AgentMetric).filter(cond)
            if user_id is not None:
                q = q.filter(AgentMetric.user_id == user_id)
            if start_dt is not None:
                q = q.filter(AgentMetric.created_at >= start_dt)
            if end_dt is not None:
                q = q.filter(AgentMetric.created_at <= end_dt)
            if session_id:
                q = q.filter(AgentMetric.session_id == session_id)

            count = q.count()
            if count == 0:
                empty = {
                    "count": 0,
                    "fallback_count": 0,
                    "fallback_rate": None,
                    "avg_latency_ms": None,
                    "avg_token_total": None,
                    "grounding_pass_rate": None,
                }
                if filter_react:
                    empty.update(
                        {
                            "avg_tool_rounds": None,
                            "avg_evidence_count": None,
                            "success_count": None,
                            "rescue_rate": None,
                        }
                    )
                return empty

            fb = q.filter(AgentMetric.need_fallback.is_(True)).count()
            gp = q.filter(AgentMetric.grounding_passed.is_(True)).count()

            agg = q.with_entities(
                func.avg(AgentMetric.total_latency_ms),
                func.avg(AgentMetric.token_total),
            ).one()
            avg_lat = float(agg[0]) if agg[0] is not None else None
            avg_tok = float(agg[1]) if agg[1] is not None else None

            result = {
                "count": count,
                "fallback_count": fb,
                "fallback_rate": round(fb / count, 4),
                "avg_latency_ms": round(avg_lat, 3) if avg_lat is not None else None,
                "avg_token_total": round(avg_tok, 3) if avg_tok is not None else None,
                "grounding_pass_rate": round(gp / count, 4),
            }

            if filter_react:
                # react 组专属
                success = q.filter(AgentMetric.need_fallback.is_(False)).count()
                agg2 = q.with_entities(
                    func.avg(AgentMetric.react_tool_rounds),
                    func.avg(AgentMetric.react_evidence_count),
                ).one()
                result["avg_tool_rounds"] = (
                    round(float(agg2[0]), 3) if agg2[0] is not None else None
                )
                result["avg_evidence_count"] = (
                    round(float(agg2[1]), 3) if agg2[1] is not None else None
                )
                result["success_count"] = success
                result["rescue_rate"] = round(success / count, 4) if count else 0.0

            return result
        finally:
            db.close()

    quick = _group_stats(filter_react=False)
    react = _group_stats(filter_react=True)

    delta_lat = None
    delta_tok = None
    if (
        quick.get("avg_latency_ms") is not None
        and react.get("avg_latency_ms") is not None
    ):
        delta_lat = round(react["avg_latency_ms"] - quick["avg_latency_ms"], 3)
    if (
        quick.get("avg_token_total") is not None
        and react.get("avg_token_total") is not None
    ):
        delta_tok = round(react["avg_token_total"] - quick["avg_token_total"], 3)

    return {
        "quick_path": quick,
        "react": react,
        "delta_latency_ms": delta_lat,
        "delta_token_total": delta_tok,
    }


def _metric_row_to_dict(r: AgentMetric) -> Dict[str, Any]:
    """ORM 行 -> dict（用于 recent 明细响应）。"""
    return {
        "id": r.id,
        "chat_message_id": r.chat_message_id,
        "session_id": r.session_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "route": r.route,
        "cache_hit": r.cache_hit,
        "need_react": r.need_react,
        "react_attempted": r.react_attempted,
        "react_reason": r.react_reason,
        "react_trigger_reason": r.react_trigger_reason,
        "react_status": r.react_status,
        "react_tool_rounds": r.react_tool_rounds,
        "react_evidence_count": r.react_evidence_count,
        "evidence_grade": r.evidence_grade,
        "grounding_passed": r.grounding_passed,
        "grounding_reason": r.grounding_reason,
        "need_fallback": r.need_fallback,
        "fallback_reason": r.fallback_reason,
        "total_latency_ms": r.total_latency_ms,
        "token_total": r.token_total,
        "node_timings": r.node_timings,
        "metadata_json": r.metadata_json,
    }

