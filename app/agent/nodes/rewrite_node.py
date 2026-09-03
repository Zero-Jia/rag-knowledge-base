import time
from typing import Any, Dict, List, Optional

from app.agent.state import AgentState
from app.agent.prompts import REWRITE_SYSTEM_PROMPT
from app.schemas.rag_trace import record_token_usage
from app.services.llm_service import generate_answer_with_usage


SELF_CONTAINED_QUERY_HINTS = [
    "深度学习",
    "机器学习",
    "RAG",
    "rag",
    "缓存",
    "BM25",
    "bm25",
    "rerank",
    "embedding",
    "向量数据库",
    "redis",
    "Redis",
    "langgraph",
    "langchain",
    "项目",
    "知识库",
]


def _get_last_user_message(chat_history: List[Dict[str, str]]) -> Optional[str]:
    if not chat_history:
        return None

    for msg in reversed(chat_history):
        if msg.get("role") == "user":
            content = (msg.get("content") or "").strip()
            if content:
                return content
    return None


def _select_rewrite_context(chat_history: List[Dict[str, str]], max_messages: int = 4) -> List[Dict[str, str]]:
    """
    为 rewrite 选择更有价值的上下文，而不是直接无脑取最近几条。
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

    return list(reversed(selected_reversed))


def _get_recent_history_text(chat_history: List[Dict[str, str]], max_turns: int = 4) -> str:
    """
    将筛选后的历史拼成文本，供 LLM 改写使用
    """
    if not chat_history:
        return ""

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
    last_user_question = _get_last_user_message(chat_history)
    if not last_user_question:
        return question
    return f"关于“{last_user_question}”，{question}"


def _clean_rewritten_question(text: str, original_question: str) -> str:
    cleaned = (text or "").strip()

    if not cleaned:
        return original_question

    cleaned = cleaned.strip('"').strip("“").strip("”").strip("'")
    cleaned = " ".join(line.strip() for line in cleaned.splitlines() if line.strip())

    if not cleaned:
        return original_question

    return cleaned


def rewrite_node(state: AgentState) -> AgentState:
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    route = state.get("route", "kb_qa")
    question = (state.get("question") or "").strip()
    chat_history: List[Dict[str, str]] = state.get("chat_history", [])

    # ===== 1. 非 followup，直接跳过 =====
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

    # ===== 2. 构造上下文 =====
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
                f"请判断该问题是否需要改写，并输出最终用于检索的问题："
            ),
        },
    ]

    rag_trace: Dict[str, Any] = state.get("rag_trace", {})
    rewrite_start = time.time()
    try:
        rewritten, usage = generate_answer_with_usage(messages, temperature=0.0)
        rewritten = _clean_rewritten_question(rewritten, question)

        # ===== 3. 判断是否真的发生改写 =====
        if rewritten == question:
            debug_info["rewrite_status"] = "llm_keep_original"
        else:
            debug_info["rewrite_status"] = "llm_rewritten"

        record_token_usage(
            rag_trace,
            node="rewrite",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=(time.time() - rewrite_start) * 1000.0,
            source="llm",
        )

        state["rewritten_question"] = rewritten
        debug_info["original_question"] = question
        debug_info["rewritten_question"] = rewritten
        debug_info["rewrite_context_count"] = len(selected_history)
        debug_info["rewrite_context_preview"] = history_text[:200]

        state["debug_info"] = debug_info
        state["rag_trace"] = rag_trace
        return state

    except Exception as e:
        # ===== 4. 规则兜底 =====
        fallback = _fallback_rule_rewrite(question, chat_history)

        record_token_usage(
            rag_trace,
            node="rewrite",
            latency_ms=(time.time() - rewrite_start) * 1000.0,
            source="llm_error_rule_fallback",
        )

        state["rewritten_question"] = fallback
        debug_info["rewrite_status"] = "llm_failed_rule_fallback"
        debug_info["rewrite_error"] = str(e)

        state["debug_info"] = debug_info
        state["rag_trace"] = rag_trace
        return state