from typing import Any, Dict, List, Optional

from app.agent.state import AgentState


def _get_last_user_message(chat_history: List[Dict[str, str]]) -> Optional[str]:
    """
    从 chat_history 中提取最近一条 user 消息
    """
    if not chat_history:
        return None

    for msg in reversed(chat_history):
        if msg.get("role") == "user":
            content = (msg.get("content") or "").strip()
            if content:
                return content
    return None


def rewrite_node(state: AgentState) -> AgentState:
    """
    第7天版本：规则版 followup 改写节点

    逻辑：
    1. 仅当 route == followup 时尝试改写
    2. 从 chat_history 中取最近一条 user 消息
    3. 将当前问题补全为一个更适合检索的 rewritten_question
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    route = state.get("route", "kb_qa")
    question = (state.get("question") or "").strip()
    chat_history: List[Dict[str, str]] = state.get("chat_history", [])

    # 非 followup，不做改写
    if route != "followup":
        state["rewritten_question"] = question
        debug_info["rewrite_status"] = "skipped_not_followup"
        state["debug_info"] = debug_info
        return state

    # followup 但没有问题内容
    if not question:
        state["rewritten_question"] = question
        debug_info["rewrite_status"] = "empty_question"
        state["debug_info"] = debug_info
        return state

    # followup 但没有历史
    last_user_question = _get_last_user_message(chat_history)
    if not last_user_question:
        state["rewritten_question"] = question
        debug_info["rewrite_status"] = "no_history_fallback_original"
        state["debug_info"] = debug_info
        return state

    # 简单规则拼接
    rewritten = f'关于“{last_user_question}”，{question}'

    state["rewritten_question"] = rewritten
    debug_info["rewrite_status"] = "rule_rewritten"
    debug_info["original_question"] = question
    debug_info["rewritten_question"] = rewritten
    state["debug_info"] = debug_info
    return state