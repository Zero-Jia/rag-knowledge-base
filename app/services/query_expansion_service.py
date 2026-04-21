from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.schemas.rag_trace import record_timing
from app.services.llm_service import LLMServiceError, generate_answer


@dataclass
class QueryExpansionItem:
    query: str
    strategy: str
    source: str
    reason: Optional[str] = None


@dataclass
class QueryExpansionResult:
    original_query: str
    rewritten_query: Optional[str]
    strategies: List[str]
    expanded_queries: List[QueryExpansionItem] = field(default_factory=list)
    triggered: bool = True
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_query": self.original_query,
            "rewritten_query": self.rewritten_query,
            "strategies": self.strategies,
            "expanded_queries": [asdict(item) for item in self.expanded_queries],
            "triggered": self.triggered,
            "reason": self.reason,
        }

    def queries(self) -> List[str]:
        return [item.query for item in self.expanded_queries]


_PUNCT_RE = re.compile(r"[?？!！。.\s]+$")


def _normalize_query(query: str) -> str:
    return _PUNCT_RE.sub("", (query or "").strip())


def _dedupe_items(items: List[QueryExpansionItem], *, limit: int) -> List[QueryExpansionItem]:
    seen: set[str] = set()
    deduped: List[QueryExpansionItem] = []

    for item in items:
        q = _normalize_query(item.query)
        if not q:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        item.query = q
        deduped.append(item)
        if len(deduped) >= limit:
            break

    return deduped


def _looks_how_to(query: str) -> bool:
    q = query.lower()
    return any(marker in q for marker in ("如何", "怎么", "怎样", "步骤", "流程", "实现", "how to"))


def _looks_definition(query: str) -> bool:
    q = query.lower()
    return any(marker in q for marker in ("是什么", "什么是", "定义", "含义", "作用", "what is", "define"))


def _looks_compare(query: str) -> bool:
    q = query.lower()
    return any(marker in q for marker in ("区别", "对比", "比较", "差异", "vs", "versus", "compare"))


def choose_rewrite_strategy(
    query: str,
    *,
    fallback_reason: Optional[str] = None,
    retrieved_count: int = 0,
    top_rerank_score: Optional[float] = None,
) -> List[str]:
    """
    Pick expansion strategies for a failed retrieval attempt.

    The function is intentionally rule-based and cheap. More strategies can be
    added without changing callers.
    """
    q = _normalize_query(query)
    if not q or not settings.QUERY_EXPANSION_ENABLED:
        return []

    strategies: List[str] = ["original"]

    if settings.STEP_BACK_ENABLED:
        strategies.append("step_back")

    should_use_hyde = bool(settings.HYDE_ENABLED)
    if fallback_reason in {"no_retrieved_docs", "empty_reranked_docs"}:
        should_use_hyde = True
    if top_rerank_score is not None and top_rerank_score < 0.08:
        should_use_hyde = True
    if retrieved_count == 0:
        should_use_hyde = True

    if should_use_hyde:
        strategies.append("hyde")

    return list(dict.fromkeys(strategies))


def step_back_expand(query: str) -> QueryExpansionItem:
    """
    Generate a broader conceptual query.

    Step-back is deterministic so retrieval recovery still works when the LLM is
    unavailable.
    """
    q = _normalize_query(query)
    if not q:
        return QueryExpansionItem(query="", strategy="step_back", source="rule")

    if _looks_compare(q):
        expanded = f"{q} 的核心概念、适用场景、关键差异和优缺点"
        reason = "compare_query"
    elif _looks_how_to(q):
        expanded = f"{q} 的实现流程、关键步骤、依赖组件和注意事项"
        reason = "how_to_query"
    elif _looks_definition(q):
        expanded = f"{q} 的定义、核心概念、作用、使用场景和相关机制"
        reason = "definition_query"
    else:
        expanded = f"{q} 的背景、核心概念、关键机制和应用场景"
        reason = "general_query"

    return QueryExpansionItem(
        query=expanded,
        strategy="step_back",
        source="rule",
        reason=reason,
    )


def _fallback_hyde(query: str) -> str:
    q = _normalize_query(query)
    if _looks_how_to(q):
        return f"{q} 通常需要先明确目标，再说明关键步骤、输入输出、依赖模块、异常情况和验证方式。"
    if _looks_compare(q):
        return f"{q} 可以从定义、使用场景、实现方式、优势劣势和适用边界几个方面进行比较。"
    if _looks_definition(q):
        return f"{q} 是一个需要结合定义、核心作用、工作机制和典型使用场景来解释的概念。"
    return f"{q} 涉及背景概念、核心机制、实现流程、关键约束和实际应用。"


def hyde_expand(
    query: str,
    *,
    rewritten_query: Optional[str] = None,
    rag_trace: Optional[Dict[str, Any]] = None,
) -> QueryExpansionItem:
    """
    Generate a HyDE query: a short hypothetical answer used only for retrieval.

    If the upstream LLM fails, return a deterministic fallback instead of
    breaking the retrieval recovery loop.
    """
    q = _normalize_query(rewritten_query or query)
    if not q:
        return QueryExpansionItem(query="", strategy="hyde", source="llm")

    start = time.time()
    messages = [
        {
            "role": "system",
            "content": (
                "你是 RAG 检索查询扩展器。请生成一段简短的假设性答案，"
                "用于帮助向量检索召回相关文档。不要编造具体数字，不要输出列表标题。"
            ),
        },
        {
            "role": "user",
            "content": f"用户问题：{q}\n请输出 2-4 句话的假设性答案。",
        },
    ]

    try:
        generated = generate_answer(
            messages,
            temperature=0.1,
            max_retries=1,
            timeout=min(settings.TIMEOUT_SECONDS, 10),
        )
        expanded = generated.strip()
        source = "llm"
        reason = "hyde_generated"
    except (LLMServiceError, Exception) as exc:
        expanded = _fallback_hyde(q)
        source = "rule_fallback"
        reason = f"hyde_fallback:{type(exc).__name__}"

    max_chars = int(getattr(settings, "HYDE_MAX_CHARS", 600))
    if max_chars > 0 and len(expanded) > max_chars:
        expanded = expanded[:max_chars]

    if rag_trace is not None:
        record_timing(rag_trace, "hyde_expand_ms", (time.time() - start) * 1000.0)

    return QueryExpansionItem(
        query=expanded,
        strategy="hyde",
        source=source,
        reason=reason,
    )


def expand_query(
    query: str,
    *,
    rewritten_query: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    retrieved_count: int = 0,
    top_rerank_score: Optional[float] = None,
    rag_trace: Optional[Dict[str, Any]] = None,
) -> QueryExpansionResult:
    """
    Full query expansion entrypoint for Agent recovery.

    Returns structured expansion data and writes the same structure into
    rag_trace["query_expansion"] when a trace is provided.
    """
    start = time.time()
    original = _normalize_query(query)
    rewritten = _normalize_query(rewritten_query or "")
    strategies = choose_rewrite_strategy(
        rewritten or original,
        fallback_reason=fallback_reason,
        retrieved_count=retrieved_count,
        top_rerank_score=top_rerank_score,
    )

    result = QueryExpansionResult(
        original_query=original,
        rewritten_query=rewritten or None,
        strategies=strategies,
        reason=fallback_reason,
    )

    items: List[QueryExpansionItem] = []
    base_query = rewritten or original

    if "original" in strategies and original:
        items.append(
            QueryExpansionItem(
                query=original,
                strategy="original",
                source="input",
                reason="preserve_original_query",
            )
        )

    if rewritten and rewritten.lower() != original.lower():
        items.append(
            QueryExpansionItem(
                query=rewritten,
                strategy="rewrite",
                source="rewrite_node",
                reason="preserve_rewritten_query",
            )
        )

    if "step_back" in strategies:
        items.append(step_back_expand(base_query))

    if "hyde" in strategies:
        items.append(
            hyde_expand(
                base_query,
                rewritten_query=rewritten or None,
                rag_trace=rag_trace,
            )
        )

    max_queries = int(getattr(settings, "QUERY_EXPANSION_MAX_QUERIES", 3))
    result.expanded_queries = _dedupe_items(items, limit=max(1, max_queries))

    if rag_trace is not None:
        rag_trace["query_expansion"] = result.to_dict()
        record_timing(rag_trace, "query_expansion_ms", (time.time() - start) * 1000.0)

    return result
