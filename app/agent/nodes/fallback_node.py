from typing import Any, Dict

from app.agent.state import AgentState
from app.schemas.rag_trace import set_fallback_reason


def fallback_node(state: AgentState) -> AgentState:
    """
    第16天版本：更细致的 fallback 文案
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    rag_trace: Dict[str, Any] = state.get("rag_trace", {})
    reason = state.get("fallback_reason") or "unknown"
    route = state.get("route", "kb_qa")

    if route == "chat":
        # chat 理论上不该进 fallback，这里只是兜底
        state["final_answer"] = "我可以继续和你聊天，你也可以问我知识库相关的问题。"
        debug_info["fallback_status"] = "used_unexpected_chat_fallback"
        debug_info["fallback_reason"] = reason
        set_fallback_reason(rag_trace, reason)
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    reason_to_message = {
        "empty_question": "问题不能为空，请重新输入。",
        "no_retrieved_docs": "当前知识库中没有检索到相关内容，暂时无法给出可靠答案。你可以换一种更具体的问法。",
        "empty_reranked_docs": "虽然完成了检索，但没有得到足够相关的证据，暂时无法可靠回答。你可以补充更明确的主题对象。",
        "low_rerank_score": "当前检索到的内容相关性较弱，证据不足，暂时不建议直接回答。建议你换一种更具体的问法，或者补充上下文。",
        "insufficient_supporting_docs": "虽然检索到了部分内容，但支持证据还不够充分，暂时无法给出稳定可靠的回答。你可以补充更多背景信息。",
        # P0-2：groundedness 校验未通过（答案可能含证据外信息/幻觉），改走拒答兜底
        "grounding_failed": "生成的答案未能通过证据可靠性校验，为避免给出不够准确的内容，暂不直接回答。建议你换一种更具体的问法，或补充更多背景信息。",
        # P1-2：ReAct 多轮自主检索后仍无证据 / ReAct 执行异常
        "react_no_evidence": "经过多轮深度检索，知识库中仍未找到足够相关的内容，暂时无法给出可靠答案。你可以换一种更具体的问法，或补充背景信息后再试。",
        "react_error": "深度检索过程中出现异常，暂时无法给出可靠答案。请稍后重试，或换一种问法。",
        # P3-2：Prompt Injection 拦截（直接注入命中 / 间接注入证据全被剔除）
        "injection_blocked": "您的请求或检索内容中检测到疑似指令注入（Prompt Injection）行为，已被安全策略拦截，无法继续处理。请调整提问内容后重试。",
        "unknown": "当前知识库证据不足，暂时无法给出可靠答案。",
    }

    state["final_answer"] = reason_to_message.get(reason, reason_to_message["unknown"])
    debug_info["fallback_status"] = "used"
    debug_info["fallback_reason"] = reason
    set_fallback_reason(rag_trace, reason)
    state["rag_trace"] = rag_trace
    state["debug_info"] = debug_info
    return state
