from typing import Any, Dict, List

from app.agent.state import AgentState
from app.agent.tools.hybrid_tool import hybrid_search_tool
from app.agent.tools.vector_tool import vector_search_tool
from app.schemas.rag_trace import (
    record_initial_chunks,
    record_merged_chunks,
    set_fallback_reason,
)


def retrieve_node(state: AgentState) -> AgentState:
    """
    Agent 检索节点

    当前版本策略：
    1. 如果缓存已命中，则不再检索
    2. 优先使用 rewritten_question，没有则回退到原 question
    3. 默认优先走 hybrid search
    4. 如果 hybrid 结果为空，再回退到 vector search
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    rag_trace: Dict[str, Any] = state.get("rag_trace", {})
    question = (state.get("question") or "").strip()
    rewritten_question = (state.get("rewritten_question") or "").strip()

    if state.get("cache_hit") is True:
        debug_info["retrieve_status"] = "skipped_due_to_cache_hit"
        state["debug_info"] = debug_info
        return state

    effective_query = rewritten_question if rewritten_question else question

    if not effective_query:
        state["retrieved_docs"] = []
        debug_info["retrieve_status"] = "empty_effective_query"
        set_fallback_reason(rag_trace, "empty_effective_query")
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    user_id = debug_info.get("user_id")
    top_k = debug_info.get("top_k", 5)

    docs: List[Dict[str, Any]] = hybrid_search_tool(
        question=effective_query,
        top_k=top_k,
        user_id=user_id,
        rag_trace=rag_trace,
    )

    if docs:
        state["retrieved_docs"] = docs
        state["initial_query"] = effective_query
        state["initial_retrieved_docs"] = docs
        debug_info["retrieve_status"] = "hybrid_success"
        debug_info["retrieve_count"] = len(docs)
        debug_info["retrieve_source"] = "hybrid"
        debug_info["effective_query"] = effective_query
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    docs = vector_search_tool(
        question=effective_query,
        top_k=top_k,
    )

    state["retrieved_docs"] = docs
    state["initial_query"] = effective_query
    state["initial_retrieved_docs"] = docs
    record_initial_chunks(rag_trace, docs)
    record_merged_chunks(rag_trace, docs)
    debug_info["retrieve_status"] = "vector_fallback"
    debug_info["retrieve_count"] = len(docs)
    debug_info["retrieve_source"] = "vector"
    debug_info["effective_query"] = effective_query
    state["rag_trace"] = rag_trace
    state["debug_info"] = debug_info
    return state
