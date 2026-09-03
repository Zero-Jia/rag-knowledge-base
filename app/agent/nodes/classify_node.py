import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from app.agent.state import AgentState
from app.agent.prompts import CLASSIFY_SYSTEM_PROMPT
from app.agent.routing import detect_complex_query
from app.core.config import settings
from app.schemas.rag_trace import record_token_usage, set_fallback_reason
from app.services.injection_guard import check_query_injection
from app.services.llm_service import generate_answer_with_usage

logger = logging.getLogger("rag.agent.classify")


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


def _parse_classify_output(raw: str) -> Tuple[str, bool]:
    """
    P1-2：解析 classify LLM 输出。

    新格式为 JSON：{"route": "...", "need_react": bool, "reason": "..."}；
    兼容旧格式（裸标签），解析失败时按旧逻辑清洗。
    返回 (route_label, llm_need_react)。
    """
    text = (raw or "").strip()
    if not text:
        return "kb_qa", False

    # 去掉可能的 markdown 代码块包裹
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            label = _clean_label(str(data.get("route", "")))
            need_react = bool(data.get("need_react", False))
            return label, need_react
    except Exception:
        pass

    # 兜底：整段文本按裸标签处理（旧格式/模型未遵守 JSON 时）
    return _clean_label(text), False


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
    rag_trace: Dict[str, Any] = state.get("rag_trace", {})

    react_enabled = bool(getattr(settings, "REACT_AGENT_ENABLED", False))

    # ===== 1. 极少量强规则 =====
    if not question:
        state["route"] = "chat"
        state["need_react"] = False
        debug_info["classify_status"] = "empty_question"
        state["debug_info"] = debug_info
        return state

    # ===== 1.5 P3-2：直接注入检测（guard 开启时生效）=====
    # 命中即短路：route 锁定 kb_qa + need_fallback，graph 层
    # route_after_classify 直接转 fallback 终态拒答（跳过 cache/检索/回答，
    # 零 LLM 消耗）；开关关闭时本段零行为，quick path 不受影响
    if bool(getattr(settings, "INJECTION_GUARD_ENABLED", False)):
        injection_rules = check_query_injection(question)
        if injection_rules:
            state["route"] = "kb_qa"
            state["need_react"] = False
            state["react_reason"] = None
            state["need_fallback"] = True
            state["fallback_reason"] = "injection_blocked"
            state["injection_blocked"] = True
            set_fallback_reason(rag_trace, "injection_blocked")
            rag_trace["injection"] = {"query_blocked": True, "rules": injection_rules}
            debug_info["classify_status"] = "injection_blocked"
            debug_info["injection_blocked"] = True
            debug_info["injection_rules"] = injection_rules
            state["rag_trace"] = rag_trace
            state["debug_info"] = debug_info
            logger.warning(
                "injection guard blocked query | rules=%s | q_len=%s",
                injection_rules,
                len(question),
            )
            return state

    if _is_chat(question):
        state["route"] = "chat"
        state["need_react"] = False
        debug_info["classify_status"] = "rule_chat"
        state["debug_info"] = debug_info
        return state

    # P1-2：规则脚本前置路由（无论开关与否都计算，结果写入 debug 便于观测；
    # 仅在开关开启时才实际影响路由）
    rule_hit, rule_reason = detect_complex_query(question)
    debug_info["complex_rule_hit"] = rule_hit
    debug_info["complex_rule_reason"] = rule_reason or None

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

    classify_start = time.time()
    try:
        llm_output, usage = generate_answer_with_usage(messages, temperature=0.0)
        label, llm_need_react = _parse_classify_output(llm_output)

        # ===== 3. 轻量修正（关键）=====
        label = _light_post_fix(label, question, chat_history)

        record_token_usage(
            rag_trace,
            node="classify",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=(time.time() - classify_start) * 1000.0,
            source="llm",
        )

        # P1-2：前置升级判定 = 规则命中（硬信号）OR LLM 语义判定（软信号）
        # 规则命中优先级最高，LLM 不能否决；开关关闭时不影响路由
        react_reason: Optional[str] = None
        if rule_hit:
            react_reason = rule_reason
        elif llm_need_react:
            react_reason = "llm_complex"

        state["route"] = label
        state["need_react"] = bool(react_enabled and react_reason is not None and label != "chat")
        state["react_reason"] = react_reason
        debug_info["classify_status"] = "llm_main"
        debug_info["classify_raw_output"] = llm_output
        debug_info["llm_need_react"] = llm_need_react
        debug_info["need_react"] = state["need_react"]
        debug_info["react_reason"] = react_reason
        state["debug_info"] = debug_info
        state["rag_trace"] = rag_trace
        return state

    except Exception as e:
        # ===== 4. 规则兜底 =====
        label = _rule_fallback(question, chat_history)

        record_token_usage(
            rag_trace,
            node="classify",
            latency_ms=(time.time() - classify_start) * 1000.0,
            source="llm_error_fallback",
        )

        # LLM 不可用时，规则脚本仍然生效（离线可用）
        react_reason = rule_reason if rule_hit else None
        state["route"] = label
        state["need_react"] = bool(react_enabled and react_reason is not None and label != "chat")
        state["react_reason"] = react_reason
        debug_info["classify_status"] = "llm_failed_fallback"
        debug_info["classify_error"] = str(e)
        debug_info["need_react"] = state["need_react"]
        debug_info["react_reason"] = react_reason

        state["debug_info"] = debug_info
        state["rag_trace"] = rag_trace
        return state
