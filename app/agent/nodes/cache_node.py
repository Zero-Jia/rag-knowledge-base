from typing import Any, Dict

from app.agent.state import AgentState
from app.agent.tools.cache_tool import (
    lookup_exact_cache,
    lookup_semantic_cache,
)


def cache_node(state: AgentState) -> AgentState:
    """
    Agent 的缓存检查节点

    优先级：
    1. exact cache
    2. semantic cache
    3. miss -> 继续后续流程
    """
    question = (state.get("question") or "").strip()
    debug_info: Dict[str, Any] = state.get("debug_info", {})

    if not question:
        debug_info["cache_status"] = "empty_question"
        state["cache_hit"] = False
        state["debug_info"] = debug_info
        return state

    # 第一版先不强依赖 state 固定字段，从 debug_info 里拿
    user_id = debug_info.get("user_id")
    top_k = debug_info.get("top_k", 5)

    exact_cached = lookup_exact_cache(
        question=question,
        user_id=user_id,
        retrieval_mode="agentic",
        top_k=top_k,
    )
    if exact_cached is not None:
        state["cache_hit"] = True
        state["cached_answer"] = exact_cached.get("answer")
        state["final_answer"] = exact_cached.get("answer")
        debug_info["cache_status"] = "exact_hit"
        state["debug_info"] = debug_info
        return state

    semantic_cached = lookup_semantic_cache(
        question=question,
        user_id=user_id,
        retrieval_mode="agentic",
    )
    if semantic_cached is not None:
        state["cache_hit"] = True
        state["cached_answer"] = semantic_cached.get("answer")
        state["final_answer"] = semantic_cached.get("answer")
        debug_info["cache_status"] = "semantic_hit"
        debug_info["semantic_similarity"] = semantic_cached.get("semantic_similarity")
        state["debug_info"] = debug_info
        return state

    state["cache_hit"] = False
    debug_info["cache_status"] = "miss"
    state["debug_info"] = debug_info
    return state