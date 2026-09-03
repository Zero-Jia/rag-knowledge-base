from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, TypedDict

from app.core.config import settings


class RagTrace(TypedDict, total=False):
    original_query: str
    retrieval_mode: str
    initial_chunks: List[Dict[str, Any]]
    merged_chunks: List[Dict[str, Any]]
    rerank_scores: List[Dict[str, Any]]
    auto_merge_steps: List[Dict[str, Any]]
    timing: Dict[str, float]
    fallback_reason: Optional[str]
    cache_hit: bool
    # P0-6：token / 成本统计
    token_usage: Dict[str, Any]


def now_ms() -> float:
    return time.perf_counter() * 1000.0


def elapsed_ms(start_ms: float) -> float:
    return round(now_ms() - start_ms, 3)


def _empty_token_total() -> Dict[str, float]:
    return {"prompt": 0, "completion": 0, "total": 0}


def create_token_usage_skeleton() -> Dict[str, Any]:
    """P0-6：token_usage 骨架，随 rag_trace 一起创建/持久化。"""
    return {
        "model": settings.OPENAI_MODEL,
        "total": _empty_token_total(),
        "by_node": {},
    }


def create_rag_trace(
    *,
    original_query: str,
    retrieval_mode: str,
    cache_hit: bool = False,
) -> RagTrace:
    return {
        "original_query": original_query,
        "retrieval_mode": retrieval_mode,
        "initial_chunks": [],
        "merged_chunks": [],
        "rerank_scores": [],
        "auto_merge_steps": [],
        "timing": {},
        "fallback_reason": None,
        "cache_hit": cache_hit,
        "token_usage": create_token_usage_skeleton(),
    }


def ensure_rag_trace(
    trace: Optional[Dict[str, Any]],
    *,
    original_query: str,
    retrieval_mode: str,
) -> RagTrace:
    if trace is None:
        return create_rag_trace(
            original_query=original_query,
            retrieval_mode=retrieval_mode,
        )

    trace.setdefault("original_query", original_query)
    trace.setdefault("retrieval_mode", retrieval_mode)
    trace.setdefault("initial_chunks", [])
    trace.setdefault("merged_chunks", [])
    trace.setdefault("rerank_scores", [])
    trace.setdefault("auto_merge_steps", [])
    trace.setdefault("timing", {})
    trace.setdefault("fallback_reason", None)
    trace.setdefault("cache_hit", False)
    # P0-6：兼容旧 rag_trace（无 token_usage）补骨架
    if "token_usage" not in trace or not isinstance(trace.get("token_usage"), dict):
        trace["token_usage"] = create_token_usage_skeleton()
    else:
        tu = trace["token_usage"]
        tu.setdefault("model", settings.OPENAI_MODEL)
        if not isinstance(tu.get("total"), dict):
            tu["total"] = _empty_token_total()
        else:
            tu["total"].setdefault("prompt", 0)
            tu["total"].setdefault("completion", 0)
            tu["total"].setdefault("total", 0)
        tu.setdefault("by_node", {})
    return trace  # type: ignore[return-value]


def compact_chunk(chunk: Dict[str, Any], *, include_text: bool = True) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "document_id": chunk.get("document_id"),
        "chunk_id": chunk.get("chunk_id"),
        "chunk_index": chunk.get("chunk_index"),
        "chunk_level": chunk.get("chunk_level"),
        "parent_chunk_id": chunk.get("parent_chunk_id"),
        "root_chunk_id": chunk.get("root_chunk_id"),
        "score": chunk.get("score"),
        "final_score": chunk.get("final_score"),
        "rerank_score": chunk.get("rerank_score"),
        "auto_merged": chunk.get("auto_merged", False),
        "merged_child_count": chunk.get("merged_child_count"),
        "retrieval_sources": chunk.get("retrieval_sources"),
    }

    if include_text:
        text = chunk.get("text")
        if isinstance(text, str):
            item["text_preview"] = text[:160]
            item["text_length"] = len(text)

    return {key: value for key, value in item.items() if value is not None}


def record_initial_chunks(trace: Dict[str, Any], chunks: List[Dict[str, Any]]) -> None:
    trace["initial_chunks"] = [compact_chunk(chunk) for chunk in chunks]


def record_merged_chunks(trace: Dict[str, Any], chunks: List[Dict[str, Any]]) -> None:
    trace["merged_chunks"] = [compact_chunk(chunk) for chunk in chunks]


def record_rerank_scores(trace: Dict[str, Any], chunks: List[Dict[str, Any]]) -> None:
    trace["rerank_scores"] = [
        {
            "document_id": chunk.get("document_id"),
            "chunk_id": chunk.get("chunk_id"),
            "chunk_index": chunk.get("chunk_index"),
            "chunk_level": chunk.get("chunk_level"),
            "score": chunk.get("score"),
            "rerank_score": chunk.get("rerank_score"),
        }
        for chunk in chunks
    ]


def record_auto_merge_steps(
    trace: Dict[str, Any],
    *,
    before_chunks: List[Dict[str, Any]],
    after_chunks: List[Dict[str, Any]],
) -> None:
    before_count = len(before_chunks)
    steps: List[Dict[str, Any]] = []

    for chunk in after_chunks:
        if not chunk.get("auto_merged"):
            continue
        steps.append(
            {
                "to_chunk_id": chunk.get("chunk_id"),
                "to_level": chunk.get("chunk_level"),
                "from_level": chunk.get("merged_from_level"),
                "parent_chunk_id": chunk.get("parent_chunk_id"),
                "root_chunk_id": chunk.get("root_chunk_id"),
                "merged_child_count": chunk.get("merged_child_count"),
                "score": chunk.get("score"),
            }
        )

    trace["auto_merge_steps"] = steps
    trace.setdefault("timing", {})
    trace["auto_merge_summary"] = {
        "before_count": before_count,
        "after_count": len(after_chunks),
        "merged_count": len(steps),
    }


def record_timing(trace: Dict[str, Any], stage: str, ms: float) -> None:
    timing = trace.setdefault("timing", {})
    timing[stage] = round(float(ms), 3)


def _ensure_token_usage(trace: Dict[str, Any]) -> Dict[str, Any]:
    tu = trace.get("token_usage")
    if not isinstance(tu, dict):
        tu = create_token_usage_skeleton()
        trace["token_usage"] = tu
    else:
        tu.setdefault("model", settings.OPENAI_MODEL)
        if not isinstance(tu.get("total"), dict):
            tu["total"] = _empty_token_total()
        else:
            tu["total"].setdefault("prompt", 0)
            tu["total"].setdefault("completion", 0)
            tu["total"].setdefault("total", 0)
        tu.setdefault("by_node", {})
    return tu


def record_token_usage(
    trace: Dict[str, Any],
    *,
    node: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: Optional[float] = None,
    source: str = "llm",
) -> None:
    """
    P0-6：记录某节点的 token 消耗，并累加到 total。

    - prompt/completion 为 0 时（cache 命中 / 短路 / 规则兜底）也写入 by_node，
      方便前端区分"未调用 LLM"与"缺失统计"。
    - 同一 node 多次调用（如 answer 走 chat 与 kb_qa 互斥，实际不重叠）会覆盖，
      如需累加请传不同 node 名。
    """
    tu = _ensure_token_usage(trace)

    prompt = int(prompt_tokens or 0)
    completion = int(completion_tokens or 0)
    total = prompt + completion

    entry: Dict[str, Any] = {
        "prompt": prompt,
        "completion": completion,
        "total": total,
        "source": source,
    }
    if latency_ms is not None:
        entry["latency_ms"] = round(float(latency_ms), 3)

    tu["by_node"][node] = entry

    agg = tu["total"]
    agg["prompt"] = int(agg.get("prompt", 0)) + prompt
    agg["completion"] = int(agg.get("completion", 0)) + completion
    agg["total"] = int(agg.get("total", 0)) + total


def set_cache_hit(trace: Dict[str, Any], cache_hit: bool) -> None:
    trace["cache_hit"] = bool(cache_hit)


def set_fallback_reason(trace: Dict[str, Any], fallback_reason: Optional[str]) -> None:
    trace["fallback_reason"] = fallback_reason
