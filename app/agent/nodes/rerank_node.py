from typing import Any, Dict, List

from app.agent.state import AgentState
from app.agent.tools.rerank_tool import rerank_tool
from app.schemas.rag_trace import record_rerank_scores, set_fallback_reason


def rerank_node(state: AgentState) -> AgentState:
    """
    第16天版本：更合理的证据充分性判断

    逻辑：
    1. chat 路由不做 fallback 判断
    2. 如果 retrieved_docs 为空 -> fallback
    3. 如果 reranked_docs 为空 -> fallback
    4. 综合 top1 score + reranked_docs 数量判断是否足够回答
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    rag_trace: Dict[str, Any] = state.get("rag_trace", {})
    route = state.get("route", "kb_qa")
    question = (state.get("question") or "").strip()
    retrieved_docs: List[Dict[str, Any]] = state.get("retrieved_docs", [])

    # chat 模式不需要 rerank 证据判断
    if route == "chat":
        debug_info["rerank_status"] = "skipped_for_chat"
        state["need_fallback"] = False
        state["fallback_reason"] = None
        set_fallback_reason(rag_trace, None)
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    if state.get("cache_hit") is True:
        debug_info["rerank_status"] = "skipped_due_to_cache_hit"
        state["debug_info"] = debug_info
        state["rag_trace"] = rag_trace
        return state

    if not question:
        state["reranked_docs"] = []
        state["initial_reranked_docs"] = []
        state["need_fallback"] = True
        state["fallback_reason"] = "empty_question"
        set_fallback_reason(rag_trace, "empty_question")
        state["rag_trace"] = rag_trace
        debug_info["rerank_status"] = "empty_question"
        state["debug_info"] = debug_info
        return state

    if not retrieved_docs:
        state["reranked_docs"] = []
        state["initial_reranked_docs"] = []
        state["need_fallback"] = True
        state["fallback_reason"] = "no_retrieved_docs"
        set_fallback_reason(rag_trace, "no_retrieved_docs")
        state["rag_trace"] = rag_trace
        debug_info["rerank_status"] = "no_retrieved_docs"
        debug_info["rerank_count"] = 0
        debug_info["evidence_status"] = "insufficient_no_retrieved_docs"
        state["debug_info"] = debug_info
        return state

    top_n = debug_info.get("rerank_top_n", 3)
    score_threshold = float(debug_info.get("rerank_score_threshold", 0.1))
    min_reranked_docs = int(debug_info.get("min_reranked_docs", 1))

    docs = rerank_tool(
        question=question,
        docs=retrieved_docs,
        top_n=top_n,
    )

    state["reranked_docs"] = docs
    state["initial_reranked_docs"] = docs
    record_rerank_scores(rag_trace, docs)
    debug_info["rerank_status"] = "success"
    debug_info["rerank_count"] = len(docs)
    debug_info["rerank_top_n"] = top_n
    debug_info["rerank_score_threshold"] = score_threshold
    debug_info["min_reranked_docs"] = min_reranked_docs

    if not docs:
        state["need_fallback"] = True
        state["fallback_reason"] = "empty_reranked_docs"
        set_fallback_reason(rag_trace, "empty_reranked_docs")
        state["rag_trace"] = rag_trace
        debug_info["evidence_status"] = "insufficient_empty_reranked_docs"
        state["debug_info"] = debug_info
        return state

    top1_score = docs[0].get("rerank_score")
    top1_score = float(top1_score) if top1_score is not None else None
    debug_info["top1_rerank_score"] = top1_score

    # 统计“相对相关”的文档数量
    qualified_docs_count = 0
    for doc in docs:
        score = doc.get("rerank_score")
        if score is not None and float(score) >= score_threshold:
            qualified_docs_count += 1
    debug_info["qualified_docs_count"] = qualified_docs_count

    # ========= 第16天核心：组合判断 =========
    # 情况1：top1 太低，直接 fallback
    if top1_score is None or top1_score < score_threshold:
        state["need_fallback"] = True
        state["fallback_reason"] = "low_rerank_score"
        set_fallback_reason(rag_trace, "low_rerank_score")
        state["rag_trace"] = rag_trace
        debug_info["evidence_status"] = "insufficient_low_rerank_score"
        state["debug_info"] = debug_info
        return state

    # 情况2：虽然 top1 达标，但满足阈值的文档数量太少
    if qualified_docs_count < min_reranked_docs:
        state["need_fallback"] = True
        state["fallback_reason"] = "insufficient_supporting_docs"
        set_fallback_reason(rag_trace, "insufficient_supporting_docs")
        state["rag_trace"] = rag_trace
        debug_info["evidence_status"] = "insufficient_supporting_docs"
        state["debug_info"] = debug_info
        return state

    state["need_fallback"] = False
    state["fallback_reason"] = None
    set_fallback_reason(rag_trace, None)
    state["rag_trace"] = rag_trace
    debug_info["evidence_status"] = "sufficient"
    state["debug_info"] = debug_info
    return state
