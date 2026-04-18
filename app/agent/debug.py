from typing import Any, Dict


def build_agent_debug_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    从 agent graph 的最终结果中提炼统一的 debug 视图。
    目的：
    - 减少 debug_info 冗余
    - 对外暴露更稳定的字段
    - 便于接口调试和面试展示
    """
    raw_debug = result.get("debug_info", {}) or {}

    summary = {
        # 基础流程
        "route": result.get("route"),
        "cache_hit": result.get("cache_hit", False),
        "need_fallback": result.get("need_fallback", False),
        "fallback_reason": result.get("fallback_reason"),

        # classify
        "classify_status": raw_debug.get("classify_status"),

        # rewrite
        "rewrite_status": raw_debug.get("rewrite_status"),
        "rewritten_question": result.get("rewritten_question"),

        # retrieve
        "retrieve_status": raw_debug.get("retrieve_status"),
        "retrieve_source": raw_debug.get("retrieve_source"),
        "retrieve_count": raw_debug.get("retrieve_count"),
        "effective_query": raw_debug.get("effective_query"),

        # rerank / evidence
        "rerank_status": raw_debug.get("rerank_status"),
        "rerank_count": raw_debug.get("rerank_count"),
        "top1_rerank_score": raw_debug.get("top1_rerank_score"),
        "qualified_docs_count": raw_debug.get("qualified_docs_count"),
        "evidence_status": raw_debug.get("evidence_status"),

        # answer
        "answer_status": raw_debug.get("answer_status"),
        "used_context": raw_debug.get("used_context"),
        "answer_chars": raw_debug.get("answer_chars"),

        # memory / session
        "history_source": raw_debug.get("history_source"),
    }

    # 去掉值为 None 的字段，让输出更干净
    compact_summary = {k: v for k, v in summary.items() if v is not None}
    return compact_summary


def summarize_agent_result_for_log(result: Dict[str, Any]) -> str:
    """
    生成一条适合日志打印的摘要字符串
    """
    debug_summary = build_agent_debug_summary(result)

    parts = [
        f"route={debug_summary.get('route')}",
        f"cache_hit={debug_summary.get('cache_hit')}",
        f"fallback={debug_summary.get('need_fallback')}",
    ]

    if "classify_status" in debug_summary:
        parts.append(f"classify={debug_summary.get('classify_status')}")

    if "rewrite_status" in debug_summary:
        parts.append(f"rewrite={debug_summary.get('rewrite_status')}")

    if "retrieve_source" in debug_summary:
        parts.append(f"retrieve={debug_summary.get('retrieve_source')}")

    if "retrieve_count" in debug_summary:
        parts.append(f"retrieve_count={debug_summary.get('retrieve_count')}")

    if "top1_rerank_score" in debug_summary:
        parts.append(f"top1_score={debug_summary.get('top1_rerank_score')}")

    if "evidence_status" in debug_summary:
        parts.append(f"evidence={debug_summary.get('evidence_status')}")

    if "answer_status" in debug_summary:
        parts.append(f"answer={debug_summary.get('answer_status')}")

    if "fallback_reason" in debug_summary and debug_summary.get("fallback_reason"):
        parts.append(f"fallback_reason={debug_summary.get('fallback_reason')}")

    return " | ".join(parts)