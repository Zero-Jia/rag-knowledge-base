from typing import Any, Dict, List

from app.agent.state import AgentState
from app.agent.tools.rerank_tool import rerank_tool


def rerank_node(state: AgentState) -> AgentState:
    """
    Agent rerank 节点

    当前版本逻辑：
    1. 如果缓存命中，则跳过 rerank
    2. 如果 retrieved_docs 为空，则不做 rerank
    3. 否则对 retrieved_docs 做 rerank，并保留前 top_n 条
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    question = (state.get("question") or "").strip()
    retrieved_docs: List[Dict[str, Any]] = state.get("retrieved_docs", [])

    if state.get("cache_hit") is True:
        debug_info["rerank_status"] = "skipped_due_to_cache_hit"
        state["debug_info"] = debug_info
        return state

    if not question:
        state["reranked_docs"] = []
        debug_info["rerank_status"] = "empty_question"
        state["debug_info"] = debug_info
        return state

    if not retrieved_docs:
        state["reranked_docs"] = []
        debug_info["rerank_status"] = "no_retrieved_docs"
        debug_info["rerank_count"] = 0
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
    debug_info["rerank_top_n"] = top_n
    state["debug_info"] = debug_info
    return state