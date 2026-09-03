import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from app.agent.prompts import build_grounding_check_messages
from app.agent.state import AgentState
from app.schemas.rag_trace import record_token_usage, record_timing, set_fallback_reason
from app.services.llm_service import LLMServiceError, generate_answer_with_usage

logger = logging.getLogger("rag.grounding")

# 容错：从 LLM 输出中抽取 supported 布尔值
_SUPPORTED_PATTERN = re.compile(
    r'"supported"\s*:\s*(true|false)', re.IGNORECASE
)


def _parse_grounding_response(raw: str) -> Optional[Dict[str, Any]]:
    """
    解析 grounding 校验 LLM 输出，期望 {"supported": bool, "reason": str}。

    容错策略：
    1. 直接 json.loads
    2. 正则提取 supported 字段
    3. 都失败返回 None（上层默认放行）
    """
    if not raw:
        return None

    text = raw.strip()
    # 去掉可能的 markdown 代码块包裹
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    # 尝试 1：标准 JSON
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "supported" in data:
            return {
                "supported": bool(data["supported"]),
                "reason": str(data.get("reason", "")).strip() or None,
            }
    except (ValueError, TypeError):
        pass

    # 尝试 2：正则提取 supported
    m = _SUPPORTED_PATTERN.search(raw)
    if m:
        supported = m.group(1).lower() == "true"
        reason_match = re.search(r'"reason"\s*:\s*"([^"]*)"', raw)
        reason = reason_match.group(1).strip() if reason_match else None
        return {"supported": supported, "reason": reason}

    return None


def grounding_check_node(state: AgentState) -> AgentState:
    """
    P0-2：答案生成后的 groundedness / faithfulness 校验节点。

    逻辑：
    - chat 路由 / 无证据 / 无答案 / cache 命中场景直接短路放行
    - 否则调用 LLM 判断答案是否被 reranked_docs 证据支持
    - 不通过 → 设置 need_fallback=True + fallback_reason="grounding_failed"
      （由 graph 条件边路由到 fallback_node）
    - LLM 调用或解析失败 → 保守放行，避免 grounding 自身故障拖垮主流程
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    rag_trace: Dict[str, Any] = state.get("rag_trace", {})
    route = state.get("route", "kb_qa")
    final_answer = state.get("final_answer") or ""

    # 短路场景：chat / cache 命中 / 无答案
    if route == "chat":
        state["grounding_passed"] = True
        state["grounding_reason"] = "chat_skip"
        debug_info["grounding_status"] = "skipped_chat"
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    if state.get("cache_hit") is True:
        # 理论上 cache 命中不进此节点（route_after_cache 直接 END），保险判断
        state["grounding_passed"] = True
        state["grounding_reason"] = "cache_skip"
        debug_info["grounding_status"] = "skipped_cache_hit"
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    if not final_answer:
        state["grounding_passed"] = True
        state["grounding_reason"] = "empty_answer_skip"
        debug_info["grounding_status"] = "skipped_empty_answer"
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    # 取证据文档（与 answer_node 一致：优先 reranked，否则 retrieved）
    reranked_docs: List[Dict[str, Any]] = state.get("reranked_docs", [])
    retrieved_docs: List[Dict[str, Any]] = state.get("retrieved_docs", [])
    evidence_docs = reranked_docs if reranked_docs else retrieved_docs

    if not evidence_docs:
        # answer_node 在无 context 时已输出拒答文案，这里放行（拒答不算幻觉）
        state["grounding_passed"] = True
        state["grounding_reason"] = "no_evidence_skip"
        debug_info["grounding_status"] = "skipped_no_evidence"
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    question = (state.get("question") or "").strip()
    messages = build_grounding_check_messages(question, final_answer, evidence_docs)

    grounding_start = time.time()
    try:
        raw, usage = generate_answer_with_usage(messages, temperature=0.0)
        grounding_ms = (time.time() - grounding_start) * 1000.0
        record_timing(rag_trace, "grounding_check_ms", grounding_ms)
        record_token_usage(
            rag_trace,
            node="grounding_check",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_ms=grounding_ms,
            source="llm",
        )
    except LLMServiceError as exc:
        grounding_ms = (time.time() - grounding_start) * 1000.0
        record_timing(rag_trace, "grounding_check_ms", grounding_ms)
        record_token_usage(
            rag_trace,
            node="grounding_check",
            latency_ms=grounding_ms,
            source="llm_error_pass_through",
        )
        logger.error("grounding LLM call failed, fallback to pass | error=%s", exc)
        state["grounding_passed"] = True
        state["grounding_reason"] = "llm_error_pass_through"
        debug_info["grounding_status"] = "llm_error_pass_through"
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    parsed = _parse_grounding_response(raw)
    if parsed is None:
        # 解析失败，保守放行，避免误杀
        logger.warning("grounding response parse failed, pass through | raw=%s", raw[:200])
        state["grounding_passed"] = True
        state["grounding_reason"] = "parse_error_pass_through"
        debug_info["grounding_status"] = "parse_error_pass_through"
        debug_info["grounding_raw_preview"] = raw[:200]
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    supported = bool(parsed["supported"])
    reason = parsed.get("reason")

    state["grounding_passed"] = supported
    state["grounding_reason"] = reason

    if supported:
        debug_info["grounding_status"] = "passed"
    else:
        debug_info["grounding_status"] = "failed"
        debug_info["grounding_reason"] = reason
        # 触发 fallback：由 graph 条件边路由到 fallback_node
        state["need_fallback"] = True
        state["fallback_reason"] = "grounding_failed"
        set_fallback_reason(rag_trace, "grounding_failed")

    state["rag_trace"] = rag_trace
    state["debug_info"] = debug_info
    return state
