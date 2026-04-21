from __future__ import annotations

from typing import Any, Dict, List

from app.agent.state import AgentState
from app.agent.tools.hybrid_tool import hybrid_search_tool
from app.schemas.rag_trace import compact_chunk


def _chunk_key(item: Dict[str, Any]) -> str:
    chunk_id = item.get("chunk_id")
    if chunk_id:
        return f"chunk:{chunk_id}"
    return f"doc:{item.get('document_id')}:idx:{item.get('chunk_index')}:text:{hash(item.get('text', ''))}"


def _dedupe_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    deduped: List[Dict[str, Any]] = []

    for chunk in chunks:
        key = _chunk_key(chunk)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)

    return deduped


def retrieve_expanded_node(state: AgentState) -> AgentState:
    """
    Run second-pass retrieval for all expanded queries and combine results with
    initial retrieval results.
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    rag_trace: Dict[str, Any] = state.get("rag_trace", {})
    expanded_queries: List[str] = state.get("expanded_queries", [])

    if not expanded_queries:
        state["expanded_retrieved_docs"] = []
        state["combined_retrieved_docs"] = state.get("initial_retrieved_docs", [])
        state["retrieved_docs"] = state["combined_retrieved_docs"]
        debug_info["retrieve_expanded_status"] = "empty_expanded_queries"
        state["debug_info"] = debug_info
        state["rag_trace"] = rag_trace
        return state

    user_id = debug_info.get("user_id")
    top_k = int(debug_info.get("top_k", 5))
    expanded_top_k = max(top_k * 2, top_k)

    expanded_docs: List[Dict[str, Any]] = []
    per_query_counts: List[Dict[str, Any]] = []

    for expanded_query in expanded_queries:
        docs = hybrid_search_tool(
            question=expanded_query,
            top_k=expanded_top_k,
            user_id=user_id,
            rag_trace=None,
        )
        expanded_docs.extend(docs)
        per_query_counts.append(
            {
                "query": expanded_query,
                "count": len(docs),
            }
        )

    expanded_docs = _dedupe_chunks(expanded_docs)
    initial_docs = state.get("initial_retrieved_docs", state.get("retrieved_docs", []))
    combined_docs = _dedupe_chunks(list(initial_docs) + expanded_docs)

    state["expanded_retrieved_docs"] = expanded_docs
    state["combined_retrieved_docs"] = combined_docs
    state["retrieved_docs"] = combined_docs

    debug_info["retrieve_expanded_status"] = "success"
    debug_info["expanded_retrieved_count"] = len(expanded_docs)
    debug_info["combined_retrieved_count"] = len(combined_docs)
    debug_info["expanded_retrieval_per_query"] = per_query_counts

    rag_trace["expanded_chunks"] = [compact_chunk(chunk) for chunk in expanded_docs]
    rag_trace["combined_chunks"] = [compact_chunk(chunk) for chunk in combined_docs]
    rag_trace["expanded_retrieval"] = {
        "queries": expanded_queries,
        "per_query_counts": per_query_counts,
        "expanded_count": len(expanded_docs),
        "combined_count": len(combined_docs),
    }

    state["rag_trace"] = rag_trace
    state["debug_info"] = debug_info
    return state
