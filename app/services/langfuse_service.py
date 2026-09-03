"""
Langfuse 上报服务（P0-5）。

设计要点：
1. 渐进式开关：`settings.LANGFUSE_ENABLED=False` 时所有上报走 no-op，
   不初始化 SDK、零网络调用，后端可正常启动且回归评估无影响。
2. 不阻塞主流程：`report_agent_trace` 内部 try/except 兜底，
   任何 Langfuse 错误只 log warning，不影响 agent 主链路。
3. 上报粒度：P0-5 只上报顶层 Trace（一条 agent 调用 → 一条 trace），
   P0-6 加 token/cost 后再细化为 spans/generations。
4. 不上报原文 chunk 全文，metadata 中只放 rag_trace.timing 等聚合指标，
   避免敏感数据外泄（为未来 PII 脱敏预留空间）。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger("rag.langfuse")

_langfuse_client = None


def _get_client():
    """
    懒加载 Langfuse 客户端。
    - 开关关闭 → 返回 None
    - 开关打开但缺 keys → 返回 None 并 warning
    - SDK 初始化失败 → 返回 None 并 warning，主流程不受影响
    """
    global _langfuse_client

    if not settings.LANGFUSE_ENABLED:
        return None

    if _langfuse_client is not None:
        return _langfuse_client

    if not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        logger.warning(
            "langfuse enabled but keys missing, "
            "set LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY in .env"
        )
        return None

    try:
        # v4 SDK 自动从环境变量读取，这里显式注入避免依赖 .env 自动加载顺序
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
        os.environ["LANGFUSE_BASE_URL"] = settings.LANGFUSE_HOST

        # 延迟 import，避免 LANGFUSE_ENABLED=False 时也触发 SDK 初始化
        from langfuse import get_client

        _langfuse_client = get_client()
        logger.info(
            "langfuse client initialized | host=%s",
            settings.LANGFUSE_HOST,
        )
        return _langfuse_client
    except Exception as exc:
        logger.warning("langfuse client init failed, fall back to no-op: %s", exc)
        return None


def _build_metadata(
    *,
    route: Optional[str],
    cache_hit: bool,
    need_fallback: bool,
    fallback_reason: Optional[str],
    grounding_passed: Optional[bool],
    grounding_reason: Optional[str],
    citations: List[Dict[str, Any]],
    rag_trace: Optional[Dict[str, Any]],
    source: str,
) -> Dict[str, Any]:
    """聚合 P0-1/P0-2/rag_trace.timing 等指标，不上报原文 chunk。"""
    metadata: Dict[str, Any] = {
        "source": source,
        "route": route,
        "cache_hit": cache_hit,
        "need_fallback": need_fallback,
        "fallback_reason": fallback_reason,
        "grounding_passed": grounding_passed,
        "grounding_reason": grounding_reason,
        "citations_count": len(citations or []),
    }

    # 只摘 timing 聚合，不带 initial_chunks/merged_chunks（避免原文外泄）
    if isinstance(rag_trace, dict):
        timing = rag_trace.get("timing")
        if isinstance(timing, dict):
            metadata["timing_ms"] = {
                k: v for k, v in timing.items() if isinstance(v, (int, float))
            }
        metadata["retrieval_mode"] = rag_trace.get("retrieval_mode")
        metadata["initial_chunks_count"] = len(rag_trace.get("initial_chunks") or [])
        metadata["merged_chunks_count"] = len(rag_trace.get("merged_chunks") or [])

    return metadata


def report_agent_trace(
    *,
    trace_id: str,
    question: str,
    final_answer: str,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
    route: Optional[str] = None,
    cache_hit: bool = False,
    need_fallback: bool = False,
    fallback_reason: Optional[str] = None,
    grounding_passed: Optional[bool] = None,
    grounding_reason: Optional[str] = None,
    citations: Optional[List[Dict[str, Any]]] = None,
    rag_trace: Optional[Dict[str, Any]] = None,
    source: str = "agent_chat",
    elapsed_ms: Optional[float] = None,
    error: Optional[str] = None,
) -> None:
    """
    上报一条 agent 调用到 Langfuse（顶层 Trace，无 spans）。

    任何异常都被吞掉，只 log warning，确保主流程不受影响。
    调用方在 try 末尾成功路径与 except 失败路径都应调用本函数。
    """
    client = _get_client()
    if client is None:
        return

    try:
        metadata = _build_metadata(
            route=route,
            cache_hit=cache_hit,
            need_fallback=need_fallback,
            fallback_reason=fallback_reason,
            grounding_passed=grounding_passed,
            grounding_reason=grounding_reason,
            citations=citations or [],
            rag_trace=rag_trace,
            source=source,
        )
        if elapsed_ms is not None:
            metadata["elapsed_ms"] = elapsed_ms
        if error is not None:
            metadata["error"] = error
            metadata["status"] = "error"
        else:
            metadata["status"] = "ok"

        # v4 SDK manual observation：不依赖上下文管理器，适合"事后上报"
        # start_observation 自动作为当前 active span 的 child；
        # 在 agent_chat/stream service 顶层调用时它就是 root trace。
        span = client.start_observation(
            name=f"{source}",
            input=question,
            metadata=metadata,
        )

        # 设置 user_id / session_id（用于 Langfuse UI 按用户/会话过滤）
        # v4 SDK 通过 update 接受 user_id/session_id 参数
        span.update(
            output=final_answer,
            user_id=str(user_id) if user_id is not None else None,
            session_id=session_id,
            trace_name=f"{source} | {route or 'unknown'}",
        )

        # 标记 tags 方便 Langfuse UI 筛选
        tags = [source]
        if route:
            tags.append(f"route:{route}")
        if cache_hit:
            tags.append("cache-hit")
        if need_fallback:
            tags.append("fallback")
        span.update(tags=tags)

        span.end()

        logger.debug(
            "langfuse trace reported | trace_id=%s | source=%s | route=%s",
            trace_id,
            source,
            route,
        )
    except Exception as exc:
        logger.warning(
            "langfuse report failed (ignored) | trace_id=%s | error=%s",
            trace_id,
            exc,
        )


def flush() -> None:
    """
    主动 flush 上报队列。
    短生命周期进程（如 CLI 评估脚本）需要调用以确保 trace 落地。
    长驻 uvicorn 进程可不调用，SDK 后台异步批量发送。
    """
    client = _get_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception as exc:
        logger.warning("langfuse flush failed (ignored): %s", exc)
