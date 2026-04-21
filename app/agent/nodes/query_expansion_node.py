from __future__ import annotations

from typing import Any, Dict, List

from app.agent.state import AgentState
from app.services.query_expansion_service import expand_query


def query_expansion_node(state: AgentState) -> AgentState:
    """
    Build expanded queries after the initial retrieval is graded insufficient.
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    rag_trace: Dict[str, Any] = state.get("rag_trace", {})

    question = (state.get("question") or "").strip()
    rewritten_question = (state.get("rewritten_question") or "").strip() or None
    retrieved_docs: List[Dict[str, Any]] = state.get("retrieved_docs", [])
    grade_reason = state.get("grade_reason") or state.get("fallback_reason")
    grade_metrics: Dict[str, Any] = state.get("grade_metrics", {})

    result = expand_query(
        question,
        rewritten_query=rewritten_question,
        fallback_reason=grade_reason,
        retrieved_count=len(retrieved_docs),
        top_rerank_score=grade_metrics.get("top1_rerank_score"),
        rag_trace=rag_trace,
    )

    expanded_queries = result.queries()

    state["expanded_queries"] = expanded_queries
    state["query_expansion_strategy"] = result.strategies
    state["expansion_attempted"] = True

    debug_info["query_expansion_status"] = "success" if expanded_queries else "empty"
    debug_info["expanded_queries"] = expanded_queries
    debug_info["query_expansion_strategy"] = result.strategies

    state["rag_trace"] = rag_trace
    state["debug_info"] = debug_info
    return state
