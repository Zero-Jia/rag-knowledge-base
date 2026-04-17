from typing import Any, Dict, List, Optional

from app.agent.state import AgentState
from app.agent.prompts import REWRITE_SYSTEM_PROMPT
from app.services.llm_service import generate_answer


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


def _select_rewrite_context(
    chat_history: List[Dict[str, str]], max_messages: int = 4
) -> List[Dict[str, str]]:
    """
    为 rewrite 选择更有价值的上下文，而不是直接无脑取最近几条。

    当前轻量策略：
    1. 从后往前找，优先保留最近有内容的消息
    2. 跳过空 role / 空 content
    3. 最多保留 max_messages 条
    """
    if not chat_history:
        return []

    selected_reversed: List[Dict[str, str]] = []

    for msg in reversed(chat_history):
        role = (msg.get("role") or "").strip()
        content = (msg.get("content") or "").strip()
        if not role or not content:
            continue

        selected_reversed.append(
            {
                "role": role,
                "content": content,
            }
        )

        if len(selected_reversed) >= max_messages:
            break

    selected = list(reversed(selected_reversed))
    return selected


def _get_recent_history_text(chat_history: List[Dict[str, str]], max_turns: int = 4) -> str:
    """
    将筛选后的历史拼成文本，供 LLM 改写使用
    """
    selected_history = _select_rewrite_context(chat_history, max_messages=max_turns)
    if not selected_history:
        return ""

    lines: List[str] = []

    for msg in selected_history:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if not content:
            continue

        if role == "user":
            lines.append(f"用户：{content}")
        elif role == "assistant":
            lines.append(f"助手：{content}")
        else:
            lines.append(f"{role}：{content}")

    return "\n".join(lines)


def _fallback_rule_rewrite(question: str, chat_history: List[Dict[str, str]]) -> str:
    """
    当 LLM 改写失败时，回退到规则版改写
    """
    last_user_question = _get_last_user_message(chat_history)
    if not last_user_question:
        return question
    return f"关于“{last_user_question}”，{question}"


def _clean_rewritten_question(text: str, original_question: str) -> str:
    """
    清洗 LLM 改写结果
    """
    cleaned = (text or "").strip()

    if not cleaned:
        return original_question

    cleaned = cleaned.strip('"').strip("“").strip("”").strip("'")
    cleaned = " ".join(line.strip() for line in cleaned.splitlines() if line.strip())

    if not cleaned:
        return original_question

    return cleaned


def rewrite_node(state: AgentState) -> AgentState:
    """
    第14天版本：优化 history 选择后的 LLM rewrite 节点

    逻辑：
    1. 非 followup -> 不改写
    2. followup -> 先筛选最关键的历史上下文
    3. 用精简后的 history + 当前问题 调 LLM 改写
    4. 如果 LLM 失败 -> 回退到规则版 rewrite
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    route = state.get("route", "kb_qa")
    question = (state.get("question") or "").strip()
    chat_history: List[Dict[str, str]] = state.get("chat_history", [])

    if route != "followup":
        state["rewritten_question"] = question
        debug_info["rewrite_status"] = "skipped_not_followup"
        state["debug_info"] = debug_info
        return state

    if not question:
        state["rewritten_question"] = question
        debug_info["rewrite_status"] = "empty_question"
        state["debug_info"] = debug_info
        return state

    if not chat_history:
        state["rewritten_question"] = question
        debug_info["rewrite_status"] = "no_history_fallback_original"
        state["debug_info"] = debug_info
        return state

    selected_history = _select_rewrite_context(chat_history, max_messages=4)
    history_text = _get_recent_history_text(selected_history, max_turns=4)

    messages = [
        {
            "role": "system",
            "content": REWRITE_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (
                f"对话历史如下：\n{history_text}\n\n"
                f"当前用户问题：{question}\n\n"
                f"请输出改写后的独立问题："
            ),
        },
    ]

    try:
        rewritten = generate_answer(messages, temperature=0.0)
        rewritten = _clean_rewritten_question(rewritten, question)

        state["rewritten_question"] = rewritten
        debug_info["rewrite_status"] = "llm_rewritten"
        debug_info["original_question"] = question
        debug_info["rewritten_question"] = rewritten
        debug_info["rewrite_context_count"] = len(selected_history)
        debug_info["rewrite_context_preview"] = history_text[:200]
        state["debug_info"] = debug_info
        return state

    except Exception as e:
        fallback = _fallback_rule_rewrite(question, chat_history)
        state["rewritten_question"] = fallback
        debug_info["rewrite_status"] = "llm_failed_rule_fallback"
        debug_info["rewrite_error"] = str(e)
        debug_info["original_question"] = question
        debug_info["rewritten_question"] = fallback
        debug_info["rewrite_context_count"] = len(selected_history)
        debug_info["rewrite_context_preview"] = history_text[:200]
        state["debug_info"] = debug_info
        return state