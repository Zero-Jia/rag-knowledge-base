from typing import Dict, List, Optional

# 第12天先做内存版 session store
# 后续如果要升级 Redis / DB，这里可以整体替换
_SESSION_STORE: Dict[str, List[Dict[str, str]]] = {}

# 为了避免单个 session 无限增长，先做一个简单上限
MAX_HISTORY_MESSAGES = 20


def get_session_history(session_id: str) -> List[Dict[str, str]]:
    """
    获取某个 session 的历史消息
    """
    if not session_id:
        return []
    return list(_SESSION_STORE.get(session_id, []))


def append_session_message(session_id: str, role: str, content: str) -> None:
    """
    向某个 session 追加一条消息
    """
    if not session_id:
        return

    role = (role or "").strip()
    content = (content or "").strip()

    if not role or not content:
        return

    messages = _SESSION_STORE.setdefault(session_id, [])
    messages.append(
        {
            "role": role,
            "content": content,
        }
    )

    # 限制最大长度，只保留最近若干条
    if len(messages) > MAX_HISTORY_MESSAGES:
        _SESSION_STORE[session_id] = messages[-MAX_HISTORY_MESSAGES:]


def save_turn(session_id: str, user_question: str, assistant_answer: str) -> None:
    """
    保存一轮对话（user + assistant）
    """
    append_session_message(session_id, "user", user_question)
    append_session_message(session_id, "assistant", assistant_answer)


def overwrite_session_history(session_id: str, chat_history: Optional[List[Dict[str, str]]]) -> None:
    """
    用外部传入的 chat_history 覆盖当前 session 的历史。
    适合接口层显式传入 history 的场景。
    """
    if not session_id:
        return

    normalized: List[Dict[str, str]] = []
    for msg in chat_history or []:
        role = (msg.get("role") or "").strip()
        content = (msg.get("content") or "").strip()
        if not role or not content:
            continue
        normalized.append(
            {
                "role": role,
                "content": content,
            }
        )

    _SESSION_STORE[session_id] = normalized[-MAX_HISTORY_MESSAGES:]


def clear_session_history(session_id: str) -> None:
    """
    清空某个 session 的历史
    """
    if not session_id:
        return
    _SESSION_STORE.pop(session_id, None)