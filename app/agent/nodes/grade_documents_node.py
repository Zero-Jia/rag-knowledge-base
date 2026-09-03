from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.agent.state import AgentState
from app.core.config import settings
from app.schemas.rag_trace import set_fallback_reason
from app.services.injection_guard import filter_evidence_injection

logger = logging.getLogger("rag.agent.grade")


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

    # P3-2：间接注入扫描 —— guard 开启时在证据进入答案合成 prompt 前剔除
    # 携带恶意指令的 chunk。过滤发生在 grade 指标计算之前：坏证据不计入
    # 合格证据数；全部被剔除时以 injection_blocked 走 fallback（ReAct 升级
    # 护栏照常生效，允许 ReAct 换词/换工具再捞一轮干净证据）。
    # 开关关闭时本段零行为，quick path 不受影响。
    evidence_flagged: List[Dict[str, Any]] = []
    if bool(getattr(settings, "INJECTION_GUARD_ENABLED", False)) and reranked_docs:
        reranked_docs, evidence_flagged = filter_evidence_injection(reranked_docs)
        if evidence_flagged:
            state["reranked_docs"] = reranked_docs
            metrics_injection = {"injection_filtered_count": len(evidence_flagged)}
            rag_trace["injection"] = {
                **(rag_trace.get("injection") or {}),
                "evidence_flagged": evidence_flagged,
            }
            debug_info["injection_filtered_count"] = len(evidence_flagged)
            logger.warning(
                "injection guard filtered evidence | count=%s | chunk_ids=%s",
                len(evidence_flagged),
                [f.get("chunk_id") for f in evidence_flagged],
            )
        else:
            metrics_injection = {}
    else:
        metrics_injection = {}

    score_threshold = float(debug_info.get("rerank_score_threshold", 0.1))
    min_reranked_docs = int(debug_info.get("min_reranked_docs", 1))
    expansion_attempted = bool(state.get("expansion_attempted", False))

    metrics = _build_grade_metrics(
        retrieved_docs=retrieved_docs,
        reranked_docs=reranked_docs,
        score_threshold=score_threshold,
    )
    # P3-2：过滤计数并入 grade_metrics（随 JSON 列持久化，供大盘解析）
    metrics.update(metrics_injection)

    # P3-2：证据被间接注入全部剔除 → 不做 expansion 重试（同样语料只会
    # 捞回同样的坏证据），直接以 injection_blocked 转 fallback；
    # route_after_grade_documents 的 ReAct 升级护栏照常生效
    all_evidence_filtered = bool(evidence_flagged) and not reranked_docs

    if all_evidence_filtered:
        reason = "injection_blocked"
        sufficient = False
    else:
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

    if all_evidence_filtered:
        state["injection_blocked"] = True
        state["need_query_expansion"] = False
        state["need_fallback"] = True
        state["fallback_reason"] = "injection_blocked"
        set_fallback_reason(rag_trace, "injection_blocked")
    elif sufficient:
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
