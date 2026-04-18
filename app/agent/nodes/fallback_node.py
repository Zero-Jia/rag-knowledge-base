from typing import Any, Dict

from app.agent.state import AgentState


def fallback_node(state: AgentState) -> AgentState:
    """
    第16天版本：更细致的 fallback 文案
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    reason = state.get("fallback_reason") or "unknown"
    route = state.get("route", "kb_qa")

    if route == "chat":
        # chat 理论上不该进 fallback，这里只是兜底
        state["final_answer"] = "我可以继续和你聊天，你也可以问我知识库相关的问题。"
        debug_info["fallback_status"] = "used_unexpected_chat_fallback"
        debug_info["fallback_reason"] = reason
        state["debug_info"] = debug_info
        return state

    reason_to_message = {
        "empty_question": "问题不能为空，请重新输入。",
        "no_retrieved_docs": "当前知识库中没有检索到相关内容，暂时无法给出可靠答案。你可以换一种更具体的问法。",
        "empty_reranked_docs": "虽然完成了检索，但没有得到足够相关的证据，暂时无法可靠回答。你可以补充更明确的主题对象。",
        "low_rerank_score": "当前检索到的内容相关性较弱，证据不足，暂时不建议直接回答。建议你换一种更具体的问法，或者补充上下文。",
        "insufficient_supporting_docs": "虽然检索到了部分内容，但支持证据还不够充分，暂时无法给出稳定可靠的回答。你可以补充更多背景信息。",
        "unknown": "当前知识库证据不足，暂时无法给出可靠答案。",
    }

    state["final_answer"] = reason_to_message.get(reason, reason_to_message["unknown"])
    debug_info["fallback_status"] = "used"
    debug_info["fallback_reason"] = reason
    state["debug_info"] = debug_info
    return state