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
    1. chat：跳过缓存
    2. exact cache：所有非 chat 问题都可用
    3. followup：只保留 exact cache，跳过 semantic cache
    4. kb_qa：exact miss 后再查 semantic cache
    5. miss -> 继续后续流程
    """
    question = (state.get("question") or "").strip()
    route = state.get("route", "kb_qa")
    debug_info: Dict[str, Any] = state.get("debug_info", {})

    # 1. chat 直接跳过缓存
    if route == "chat":
        debug_info["cache_status"] = "skipped_for_chat"
        state["cache_hit"] = False
        state["debug_info"] = debug_info
        return state

    # 2. 空问题直接返回 miss
    if not question:
        debug_info["cache_status"] = "empty_question"
        state["cache_hit"] = False
        state["debug_info"] = debug_info
        return state

    user_id = debug_info.get("user_id")
    top_k = debug_info.get("top_k", 5)

    # 3. 先查 exact cache（followup 和 kb_qa 都保留）
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

    # 4. followup 不再查 semantic cache，直接返回 miss
    if route == "followup":
        state["cache_hit"] = False
        debug_info["cache_status"] = "skip_semantic_for_followup"
        state["debug_info"] = debug_info
        return state

    # 5. 普通 kb_qa 才查 semantic cache
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

    # 6. 最终 miss
    state["cache_hit"] = False
    debug_info["cache_status"] = "miss"
    state["debug_info"] = debug_info
    return state