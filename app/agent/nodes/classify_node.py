from typing import Any, Dict, List

from app.agent.state import AgentState
from app.agent.prompts import CLASSIFY_SYSTEM_PROMPT
from app.services.llm_service import generate_answer


FOLLOWUP_HINTS = [
    "这个",
    "那个",
    "它",
    "上面",
    "刚才",
    "之前",
    "那么",
    "那",
    "这",
    "其",
]

CHAT_HINTS = [
    "你好",
    "你是谁",
    "hi",
    "hello",
    "早上好",
    "晚上好",
]


def _is_followup(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return False

    if len(q) <= 20 and any(token in q for token in FOLLOWUP_HINTS):
        return True

    followup_patterns = [
        "那怎么",
        "那为什么",
        "那如果",
        "那这个",
        "那它",
        "这个怎么",
        "这个为什么",
        "这个有什么",
        "那缓存呢",
        "那优点呢",
    ]
    return any(p in q for p in followup_patterns)


def _is_chat(question: str) -> bool:
    q = (question or "").strip().lower()
    if not q:
        return False

    return any(token in q for token in CHAT_HINTS)


def _get_recent_history_text(chat_history: List[Dict[str, str]], max_turns: int = 4) -> str:
    """
    取最近若干轮对话，供 LLM classify 参考
    """
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
        elif role == "assistant":
            lines.append(f"助手：{content}")
        else:
            lines.append(f"{role}：{content}")

    return "\n".join(lines)


def _clean_label(text: str) -> str:
    """
    清洗 LLM 输出，只保留合法标签
    """
    label = (text or "").strip().lower()
    label = label.strip('"').strip("'").strip("“").strip("”")

    valid_labels = {"chat", "kb_qa", "followup"}
    if label in valid_labels:
        return label

    # 处理模型偶尔输出一整句的情况
    for item in valid_labels:
        if item in label:
            return item

    return "kb_qa"


def classify_node(state: AgentState) -> AgentState:
    """
    第13天版本：规则优先 + LLM 兜底

    分类结果：
    - chat
    - kb_qa
    - followup
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    question = (state.get("question") or "").strip()
    chat_history = state.get("chat_history", [])

    if not question:
        state["route"] = "chat"
        debug_info["classify_status"] = "empty_question_default_chat"
        state["debug_info"] = debug_info
        return state

    # 1) 强规则：明显闲聊
    if _is_chat(question):
        state["route"] = "chat"
        debug_info["classify_status"] = "rule_chat"
        state["debug_info"] = debug_info
        return state

    # 2) 强规则：明显 followup
    if chat_history and _is_followup(question):
        state["route"] = "followup"
        debug_info["classify_status"] = "rule_followup"
        state["debug_info"] = debug_info
        return state

    # 3) 规则无法确定时，交给 LLM
    history_text = _get_recent_history_text(chat_history)

    user_prompt = (
        f"对话历史：\n{history_text or '（无）'}\n\n"
        f"当前用户问题：{question}\n\n"
        f"请输出分类标签："
    )

    messages = [
        {
            "role": "system",
            "content": CLASSIFY_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    try:
        llm_output = generate_answer(messages, temperature=0.0)
        label = _clean_label(llm_output)

        state["route"] = label
        debug_info["classify_status"] = "llm_classified"
        debug_info["classify_raw_output"] = llm_output
        state["debug_info"] = debug_info
        return state

    except Exception as e:
        # 4) LLM 失败时，保守回退到 kb_qa
        state["route"] = "kb_qa"
        debug_info["classify_status"] = "llm_failed_default_kb_qa"
        debug_info["classify_error"] = str(e)
        state["debug_info"] = debug_info
        return state