from typing import Any, Dict, List

from app.agent.state import AgentState
from app.agent.tools.rerank_tool import rerank_tool


def rerank_node(state: AgentState) -> AgentState:
    """
    Agent rerank 节点（Day9 改进版）

    新增：
    - 多特征证据判断（top1 + supporting docs）
    """

    debug_info: Dict[str, Any] = state.get("debug_info", {})

    question = (state.get("rewritten_question") or state.get("question") or "").strip()
    retrieved_docs: List[Dict[str, Any]] = state.get("retrieved_docs", [])

    if state.get("cache_hit") is True:
        debug_info["rerank_status"] = "skipped_due_to_cache_hit"
        state["debug_info"] = debug_info
        return state

    # ❌ 空问题
    if not question:
        state["reranked_docs"] = []
        state["need_fallback"] = True
        state["fallback_reason"] = "empty_question"
        debug_info["evidence_status"] = "insufficient_empty_question"
        state["debug_info"] = debug_info
        return state

    # ❌ 没召回
    if not retrieved_docs:
        state["reranked_docs"] = []
        state["need_fallback"] = True
        state["fallback_reason"] = "no_retrieved_docs"
        debug_info["evidence_status"] = "insufficient_no_retrieved_docs"
        state["debug_info"] = debug_info
        return state

    top_n = debug_info.get("rerank_top_n", 3)

    docs = rerank_tool(
        question=question,
        docs=retrieved_docs,
        top_n=top_n,
    )

    state["reranked_docs"] = docs
    debug_info["rerank_status"] = "success"
    debug_info["rerank_count"] = len(docs)

    # ❌ rerank 后为空
    if not docs:
        state["need_fallback"] = True
        state["fallback_reason"] = "empty_reranked_docs"
        debug_info["evidence_status"] = "insufficient_empty_reranked_docs"
        state["debug_info"] = debug_info
        return state

    # ====== ⭐ 核心改动：多特征判断 ======

    scores = []
    for doc in docs:
        try:
            scores.append(float(doc.get("rerank_score")))
        except (TypeError, ValueError):
            continue

    debug_info["rerank_scores"] = scores

    if not scores:
        state["need_fallback"] = True
        state["fallback_reason"] = "invalid_rerank_scores"
        debug_info["evidence_status"] = "insufficient_invalid_scores"
        state["debug_info"] = debug_info
        return state

    top1_score = scores[0]
    debug_info["top1_rerank_score"] = top1_score

    # ⭐ 新参数（可调）
    top1_threshold = debug_info.get("top1_rerank_threshold", 6.5)
    multi_threshold = debug_info.get("multi_doc_rerank_threshold", 6.0)
    min_docs = debug_info.get("min_support_docs", 2)

    debug_info["top1_threshold"] = top1_threshold
    debug_info["multi_threshold"] = multi_threshold
    debug_info["min_docs"] = min_docs

    # 支撑文档数
    support_docs = sum(1 for s in scores if s >= multi_threshold)
    debug_info["support_doc_count"] = support_docs

    # ❌ 条件1：top1 不够强
    if top1_score < top1_threshold:
        state["need_fallback"] = True
        state["fallback_reason"] = "low_top1_score"
        debug_info["evidence_status"] = "insufficient_low_top1"
        state["debug_info"] = debug_info
        return state

    # ❌ 条件2：支撑文档太少
    if support_docs < min_docs:
        state["need_fallback"] = True
        state["fallback_reason"] = "not_enough_support_docs"
        debug_info["evidence_status"] = "insufficient_support_docs"
        state["debug_info"] = debug_info
        return state

    # ✅ 证据充分
    state["need_fallback"] = False
    state["fallback_reason"] = None
    debug_info["evidence_status"] = "sufficient"
    state["debug_info"] = debug_info
    return state