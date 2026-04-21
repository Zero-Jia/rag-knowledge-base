from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.agent.state import AgentState
from app.schemas.rag_trace import set_fallback_reason


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _build_grade_metrics(
    *,
    retrieved_docs: List[Dict[str, Any]],
    reranked_docs: List[Dict[str, Any]],
    score_threshold: float,
) -> Dict[str, Any]:
    top1_score = None
    if reranked_docs:
        top1_score = _safe_float(
            reranked_docs[0].get("rerank_score", reranked_docs[0].get("score"))
        )

    qualified_docs_count = 0
    for doc in reranked_docs:
        score = _safe_float(doc.get("rerank_score", doc.get("score")))
        if score is not None and score >= score_threshold:
            qualified_docs_count += 1

    auto_merged_count = sum(1 for doc in reranked_docs if doc.get("auto_merged"))

    return {
        "retrieved_count": len(retrieved_docs),
        "reranked_count": len(reranked_docs),
        "top1_rerank_score": top1_score,
        "qualified_docs_count": qualified_docs_count,
        "auto_merged_count": auto_merged_count,
        "score_threshold": score_threshold,
    }


def _grade_reason(metrics: Dict[str, Any], *, min_reranked_docs: int) -> Optional[str]:
    if metrics["retrieved_count"] <= 0:
        return "no_retrieved_docs"
    if metrics["reranked_count"] <= 0:
        return "empty_reranked_docs"
    if metrics["top1_rerank_score"] is None:
        return "missing_rerank_score"
    if metrics["top1_rerank_score"] < metrics["score_threshold"]:
        return "low_rerank_score"
    if metrics["qualified_docs_count"] < min_reranked_docs:
        return "insufficient_supporting_docs"
    return None


def grade_documents_node(state: AgentState) -> AgentState:
    """
    Decide whether current evidence is enough.

    First insufficient grade routes to query_expansion. If evidence is still
    insufficient after expansion, it routes to fallback.
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    rag_trace: Dict[str, Any] = state.get("rag_trace", {})
    retrieved_docs: List[Dict[str, Any]] = state.get("retrieved_docs", [])
    reranked_docs: List[Dict[str, Any]] = state.get("reranked_docs", [])

    score_threshold = float(debug_info.get("rerank_score_threshold", 0.1))
    min_reranked_docs = int(debug_info.get("min_reranked_docs", 1))
    expansion_attempted = bool(state.get("expansion_attempted", False))

    metrics = _build_grade_metrics(
        retrieved_docs=retrieved_docs,
        reranked_docs=reranked_docs,
        score_threshold=score_threshold,
    )
    reason = _grade_reason(metrics, min_reranked_docs=min_reranked_docs)
    sufficient = reason is None

    stage = "expanded" if expansion_attempted else "initial"
    attempt = {
        "stage": stage,
        "query": state.get("initial_query") or state.get("rewritten_question") or state.get("question"),
        "retrieved_count": metrics["retrieved_count"],
        "reranked_count": metrics["reranked_count"],
        "top_score": metrics["top1_rerank_score"],
        "sufficient": sufficient,
        "reason": reason,
    }

    retrieval_attempts = list(state.get("retrieval_attempts", []))
    retrieval_attempts.append(attempt)
    state["retrieval_attempts"] = retrieval_attempts

    state["evidence_grade"] = "sufficient" if sufficient else "insufficient"
    state["grade_reason"] = reason
    state["grade_metrics"] = metrics

    debug_info["evidence_grade"] = state["evidence_grade"]
    debug_info["grade_reason"] = reason
    debug_info["grade_metrics"] = metrics
    debug_info["retrieval_attempts"] = retrieval_attempts

    rag_trace["retrieval_attempts"] = retrieval_attempts
    rag_trace["grade_documents"] = {
        "stage": stage,
        "evidence_grade": state["evidence_grade"],
        "reason": reason,
        "metrics": metrics,
    }

    if sufficient:
        state["need_query_expansion"] = False
        state["need_fallback"] = False
        state["fallback_reason"] = None
        set_fallback_reason(rag_trace, None)
    elif not expansion_attempted:
        state["need_query_expansion"] = True
        state["need_fallback"] = False
        state["fallback_reason"] = reason
        set_fallback_reason(rag_trace, reason)
    else:
        state["need_query_expansion"] = False
        state["need_fallback"] = True
        state["fallback_reason"] = reason
        set_fallback_reason(rag_trace, reason)

    state["rag_trace"] = rag_trace
    state["debug_info"] = debug_info
    return state
