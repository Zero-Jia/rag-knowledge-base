from typing import Any, Dict
from app.agent.state import AgentState


def fallback_node(state: AgentState) -> AgentState:
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    reason = state.get("fallback_reason") or "unknown"

    reason_to_message = {
        "empty_question": "问题不能为空，请重新输入。",
        "no_retrieved_docs": "当前知识库中没有检索到相关内容。",
        "empty_reranked_docs": "检索到了内容，但没有相关证据。",
        "low_top1_score": "最相关内容仍然不够相关，无法可靠回答。",
        "not_enough_support_docs": "缺乏足够支撑证据，无法可靠回答。",
        "invalid_rerank_scores": "评分异常，无法判断答案可靠性。",
        "unknown": "当前知识库证据不足，暂时无法回答。",
    }

    state["final_answer"] = reason_to_message.get(reason, reason_to_message["unknown"])

    debug_info["fallback_status"] = "used"
    debug_info["fallback_reason"] = reason

    state["debug_info"] = debug_info
    return state