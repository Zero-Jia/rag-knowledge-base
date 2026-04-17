from typing import Any, Dict, List

from app.agent.state import AgentState
from app.agent.prompts import CLASSIFY_SYSTEM_PROMPT
from app.services.llm_service import generate_answer


CHAT_HINTS = [
    "你好",
    "你是谁",
    "hi",
    "hello",
    "早上好",
    "晚上好",
]


def _is_chat(question: str) -> bool:
    q = (question or "").strip().lower()
    return any(token in q for token in CHAT_HINTS)


def _get_recent_history_text(chat_history: List[Dict[str, str]], max_turns: int = 4) -> str:
    if not chat_history:
        return ""

    recent_msgs = chat_history[-max_turns:]
    lines = []

    for msg in recent_msgs:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if not content:
            continue

        if role == "user":
            lines.append(f"用户：{content}")
        else:
            lines.append(f"助手：{content}")

    return "\n".join(lines)


def _clean_label(text: str) -> str:
    label = (text or "").strip().lower()
    label = label.strip('"').strip("'").strip("“").strip("”")

    valid_labels = {"chat", "kb_qa", "followup"}

    if label in valid_labels:
        return label

    for v in valid_labels:
        if v in label:
            return v

    return "kb_qa"


def _rule_fallback(question: str, chat_history: List[Dict[str, str]]) -> str:
    """
    LLM失败 or 输出异常时的兜底策略
    """
    q = (question or "").strip()

    if _is_chat(q):
        return "chat"

    # 简单 followup 判断
    if chat_history and any(token in q for token in ["那", "它", "这个", "那个"]):
        if len(q) <= 12:
            return "followup"

    return "kb_qa"


def _light_post_fix(label: str, question: str, chat_history: List[Dict[str, str]]) -> str:
    """
    LLM结果轻量修正（不是强规则，只是防明显错误）
    """
    q = (question or "").strip()

    # 明显短追问，强行拉回 followup
    if chat_history and len(q) <= 10 and any(token in q for token in ["那", "它", "这个"]):
        return "followup"

    return label


def classify_node(state: AgentState) -> AgentState:
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    question = (state.get("question") or "").strip()
    chat_history = state.get("chat_history", [])

    # ===== 1. 极少量强规则 =====
    if not question:
        state["route"] = "chat"
        debug_info["classify_status"] = "empty_question"
        state["debug_info"] = debug_info
        return state

    if _is_chat(question):
        state["route"] = "chat"
        debug_info["classify_status"] = "rule_chat"
        state["debug_info"] = debug_info
        return state

    # ===== 2. LLM 主分类 =====
    history_text = _get_recent_history_text(chat_history)

    user_prompt = (
        f"对话历史：\n{history_text or '（无）'}\n\n"
        f"当前问题：{question}\n\n"
        f"请判断分类标签："
    )

    messages = [
        {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    try:
        llm_output = generate_answer(messages, temperature=0.0)
        label = _clean_label(llm_output)

        # ===== 3. 轻量修正（关键）=====
        label = _light_post_fix(label, question, chat_history)

        state["route"] = label
        debug_info["classify_status"] = "llm_main"
        debug_info["classify_raw_output"] = llm_output
        state["debug_info"] = debug_info
        return state

    except Exception as e:
        # ===== 4. 规则兜底 =====
        label = _rule_fallback(question, chat_history)

        state["route"] = label
        debug_info["classify_status"] = "llm_failed_fallback"
        debug_info["classify_error"] = str(e)
        state["debug_info"] = debug_info
        return state