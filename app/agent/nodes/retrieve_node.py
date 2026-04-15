from typing import Any, Dict, List

from app.agent.state import AgentState
from app.agent.tools.hybrid_tool import hybrid_search_tool
from app.agent.tools.vector_tool import vector_search_tool


def retrieve_node(state: AgentState) -> AgentState:
    """
    Agent 检索节点

    当前版本策略：
    1. 如果缓存已命中，则不再检索
    2. 默认优先走 hybrid search
    3. 如果 hybrid 结果为空，再回退到 vector search
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    question = (state.get("question") or "").strip()

    if state.get("cache_hit") is True:
        debug_info["retrieve_status"] = "skipped_due_to_cache_hit"
        state["debug_info"] = debug_info
        return state

    if not question:
        state["retrieved_docs"] = []
        debug_info["retrieve_status"] = "empty_question"
        state["debug_info"] = debug_info
        return state

    user_id = debug_info.get("user_id")
    top_k = debug_info.get("top_k", 5)

    # 第一版先固定优先使用 hybrid
    docs: List[Dict[str, Any]] = hybrid_search_tool(
        question=question,
        top_k=top_k,
        user_id=user_id,
    )

    if docs:
        state["retrieved_docs"] = docs
        debug_info["retrieve_status"] = "hybrid_success"
        debug_info["retrieve_count"] = len(docs)
        debug_info["retrieve_source"] = "hybrid"
        state["debug_info"] = debug_info
        return state

    # hybrid 没结果时，回退到向量检索
    docs = vector_search_tool(
        question=question,
        top_k=top_k,
    )

    state["retrieved_docs"] = docs
    debug_info["retrieve_status"] = "vector_fallback"
    debug_info["retrieve_count"] = len(docs)
    debug_info["retrieve_source"] = "vector"
    state["debug_info"] = debug_info
    return state