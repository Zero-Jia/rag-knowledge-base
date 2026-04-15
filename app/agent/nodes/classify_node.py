from typing import Any, Dict

from app.agent.state import AgentState


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

    # 问题较短且带明显指代词，先认为是 followup
    if len(q) <= 20 and any(token in q for token in FOLLOWUP_HINTS):
        return True

    # 常见追问句式
    followup_patterns = [
        "那怎么",
        "那为什么",
        "那如果",
        "那这个",
        "那它",
        "这个怎么",
        "这个为什么",
        "这个有什么",
    ]
    return any(p in q for p in followup_patterns)


def _is_chat(question: str) -> bool:
    q = (question or "").strip().lower()
    if not q:
        return False

    return any(token in q for token in CHAT_HINTS)


def classify_node(state: AgentState) -> AgentState:
    """
    第6天版本：规则分类节点

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

    # 先识别闲聊
    if _is_chat(question):
        state["route"] = "chat"
        debug_info["classify_status"] = "rule_chat"
        state["debug_info"] = debug_info
        return state

    # 再识别 followup
    if chat_history and _is_followup(question):
        state["route"] = "followup"
        debug_info["classify_status"] = "rule_followup"
        state["debug_info"] = debug_info
        return state

    # 默认视为知识库问答
    state["route"] = "kb_qa"
    debug_info["classify_status"] = "default_kb_qa"
    state["debug_info"] = debug_info
    return state