from __future__ import annotations

from typing import Any, Dict, List

from app.agent.state import AgentState
from app.agent.tools.rerank_tool import rerank_tool
from app.schemas.rag_trace import record_rerank_scores, set_fallback_reason


def rerank_expanded_node(state: AgentState) -> AgentState:
    """
    Final rerank after second-pass retrieval.

    The rerank query stays the user's question/rewrite, not the HyDE text.
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    rag_trace: Dict[str, Any] = state.get("rag_trace", {})
    question = (state.get("rewritten_question") or state.get("question") or "").strip()
    docs_to_rerank: List[Dict[str, Any]] = state.get(
        "combined_retrieved_docs",
        state.get("retrieved_docs", []),
    )

    if not question or not docs_to_rerank:
        state["expanded_reranked_docs"] = []
        state["reranked_docs"] = []
        state["need_fallback"] = True
        state["fallback_reason"] = "empty_expanded_rerank_input"
        set_fallback_reason(rag_trace, "empty_expanded_rerank_input")
        debug_info["rerank_expanded_status"] = "empty_input"
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    top_n = int(debug_info.get("rerank_top_n", 3))
    docs = rerank_tool(
        question=question,
        docs=docs_to_rerank,
        top_n=top_n,
    )

    state["expanded_reranked_docs"] = docs
    state["reranked_docs"] = docs
    record_rerank_scores(rag_trace, docs)

    debug_info["rerank_expanded_status"] = "success"
    debug_info["rerank_expanded_count"] = len(docs)
    state["rag_trace"] = rag_trace
    state["debug_info"] = debug_info
    return state
