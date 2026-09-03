"""
P1-2：ReAct（Tool Calling）agent 链路。

- ``build_react_agent``：用 langgraph.prebuilt.create_react_agent 构造 ReAct 子图，
  绑定 P1-1 的 4 个检索工具（user_id 服务端闭包注入，租户隔离不放松）。
- ``react_agent_node``：注册进主 StateGraph 的节点，内部 invoke ReAct 子图，
  把最终答案 / 证据 / citations / token 消耗回写 AgentState。

三层漏斗路由中的 ReAct 升级点：
1. 前置升级：classify 判定复杂问题（规则脚本 OR LLM need_react），cache miss 后进入；
2. 后置升级：expansion 二轮证据仍不足 / grounding 校验失败，fallback 前抢救一次。

防循环护栏：节点入口置 ``react_attempted=True``，路由函数据此保证 ReAct 最多执行一次；
ReAct 产出后与 quick path 共享同一个 grounding_check 质量门。
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.agent.nodes.answer_node import build_citations
from app.agent.prompts import REACT_SYSTEM_PROMPT
from app.agent.state import AgentState
from app.agent.tools import build_retrieval_tools
from app.core.config import settings
from app.schemas.rag_trace import record_token_usage, record_timing, set_fallback_reason
from app.services.injection_guard import filter_evidence_injection
from app.services.llm_service import generate_answer_with_usage
from app.services.pii_mask_service import mask_pii
from app.services.prompt_builder import build_messages

logger = logging.getLogger("rag.agent.react")

# 带入 ReAct 的历史对话轮数（user+assistant 各一条算一轮）
_MAX_HISTORY_TURNS = 6


def build_react_agent(user_id: Optional[int], rag_trace: Optional[Dict[str, Any]]):
    """
    构造 ReAct agent 子图。

    - 工具集：P1-1 的 hybrid_search / vector_search / keyword_search / rerank，
      user_id 闭包绑定（LLM 无法越权传参）；
    - 工具返回片段正文用 REACT_TOOL_TEXT_LIMIT（比 quick path 默认值长，
      保证 grounding 证据与 citation 文本不被过度截断）。
    """
    tools = build_retrieval_tools(
        user_id=user_id,
        rag_trace=rag_trace,
        text_limit=getattr(settings, "REACT_TOOL_TEXT_LIMIT", 800),
    )

    model = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        temperature=0.1,
        timeout=settings.TIMEOUT_SECONDS,
    )

    return create_react_agent(model=model, tools=tools, prompt=REACT_SYSTEM_PROMPT)


def _history_to_messages(chat_history: List[Dict[str, str]]) -> list:
    """把多轮历史转为 LangChain 消息（最近 _MAX_HISTORY_TURNS 轮）。"""
    messages: List[Any] = []
    for msg in (chat_history or [])[-_MAX_HISTORY_TURNS:]:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        else:
            messages.append(AIMessage(content=content))
    return messages


def _collect_evidence(messages: List[Any]) -> Tuple[List[Dict[str, Any]], int]:
    """
    从 ReAct 消息序列中的 ToolMessage 收集证据片段。

    - 工具返回为 {"count": N, "chunks": [...]} JSON（错误返回为 {"error": ...}，跳过）；
    - 按 chunk_id 跨工具调用去重，保留首次出现顺序；
    - 返回 (evidence_docs, tool_rounds)。
    """
    chunks_by_id: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    tool_rounds = 0

    for msg in messages:
        # ToolMessage 的 type 固定为 "tool"，避免硬依赖导入做 isinstance
        if getattr(msg, "type", None) != "tool":
            continue
        tool_rounds += 1
        try:
            data = json.loads(msg.content if isinstance(msg.content, str) else "")
        except Exception:
            continue
        if not isinstance(data, dict) or not isinstance(data.get("chunks"), list):
            continue
        for chunk in data["chunks"]:
            if not isinstance(chunk, dict):
                continue
            cid = chunk.get("chunk_id")
            if cid and cid not in chunks_by_id:
                chunks_by_id[cid] = chunk
                order.append(cid)

    return [chunks_by_id[cid] for cid in order], tool_rounds


def _sum_token_usage(messages: List[Any]) -> Tuple[int, int]:
    """累加 ReAct 全程 AIMessage 的 usage_metadata（langchain-openai 标准字段）。"""
    prompt_tokens = 0
    completion_tokens = 0
    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        usage = getattr(msg, "usage_metadata", None) or {}
        prompt_tokens += int(usage.get("input_tokens", 0) or 0)
        completion_tokens += int(usage.get("output_tokens", 0) or 0)
    return prompt_tokens, completion_tokens


def _finalize_failure(
    state: AgentState,
    *,
    reason: str,
    debug_info: Dict[str, Any],
    rag_trace: Dict[str, Any],
    elapsed_ms: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> AgentState:
    """ReAct 无证据 / 异常的统一收尾：置 fallback 标记，交由 fallback_node 终态拒答。"""
    state["need_fallback"] = True
    state["fallback_reason"] = reason
    state["final_answer"] = ""
    state["citations"] = []
    set_fallback_reason(rag_trace, reason)
    record_timing(rag_trace, "react_agent_ms", elapsed_ms)
    if prompt_tokens or completion_tokens:
        record_token_usage(
            rag_trace,
            node="react_agent",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=elapsed_ms,
            source="llm",
        )
    debug_info["react_status"] = "failed"
    debug_info["react_fail_reason"] = reason
    state["rag_trace"] = rag_trace
    state["debug_info"] = debug_info
    return state


def react_agent_node(state: AgentState) -> AgentState:
    """
    ReAct 图节点：自主多轮工具调用 → 综合作答。

    成功路径：回写 final_answer / citations / reranked_docs（证据），
    重置前序失败标记，随后进入与 quick path 共享的 grounding_check 门控；
    失败路径（无证据 / 异常 / 超步数）：置 need_fallback，由 fallback_node 终态拒答。
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    rag_trace: Dict[str, Any] = state.get("rag_trace", {})
    user_id = debug_info.get("user_id")
    question = (state.get("question") or "").strip()

    # 后置升级场景下 rewritten_question 是消解指代后的独立查询，检索更准
    effective_question = (state.get("rewritten_question") or "").strip() or question
    trigger_reason = state.get("react_reason") or "upgraded"

    # 防循环护栏：ReAct 整条链路最多执行一次
    state["react_attempted"] = True
    debug_info["react_trigger_reason"] = trigger_reason

    start = time.time()
    prompt_tokens = 0
    completion_tokens = 0
    try:
        agent = build_react_agent(user_id, rag_trace)
        messages = _history_to_messages(state.get("chat_history", []))
        messages.append(HumanMessage(content=effective_question))

        result = agent.invoke(
            {"messages": messages},
            config={"recursion_limit": int(getattr(settings, "REACT_RECURSION_LIMIT", 25))},
        )

        out_messages = result.get("messages", []) if isinstance(result, dict) else []
        evidence, tool_rounds = _collect_evidence(out_messages)
        loop_prompt_tokens, loop_completion_tokens = _sum_token_usage(out_messages)
        elapsed_ms = (time.time() - start) * 1000.0

        # P3-2：间接注入扫描 —— 工具返回的证据同样可能被埋入恶意指令
        # （检索内容即输入，ReAct 路径是主要攻击面），进答案合成 prompt 前
        # 剔除；合成与 citations 均基于过滤后列表，[N] 编号保持一致。
        # 开关关闭时零行为。
        react_evidence_flagged: List[Dict[str, Any]] = []
        if evidence and bool(getattr(settings, "INJECTION_GUARD_ENABLED", False)):
            evidence, react_evidence_flagged = filter_evidence_injection(evidence)
            if react_evidence_flagged:
                rag_trace["injection"] = {
                    **(rag_trace.get("injection") or {}),
                    "react_evidence_flagged": react_evidence_flagged,
                }
                debug_info["injection_filtered_count"] = len(react_evidence_flagged)
                logger.warning(
                    "injection guard filtered react evidence | count=%s | chunk_ids=%s",
                    len(react_evidence_flagged),
                    [f.get("chunk_id") for f in react_evidence_flagged],
                )

        if not evidence:
            # agent 多轮换词/换工具后仍未拿到任何证据（或超步数未产出工具结果 /
            # 证据全部被注入过滤剔除）
            no_evidence_reason = (
                "injection_blocked" if react_evidence_flagged else "react_no_evidence"
            )
            rag_trace["react_agent"] = {
                "trigger_reason": trigger_reason,
                "tool_rounds": tool_rounds,
                "evidence_count": 0,
                "status": "no_evidence",
            }
            logger.info(
                "react agent no evidence | reason=%s | tool_rounds=%s",
                trigger_reason, tool_rounds,
            )
            return _finalize_failure(
                state,
                reason=no_evidence_reason,
                debug_info=debug_info,
                rag_trace=rag_trace,
                elapsed_ms=elapsed_ms,
                prompt_tokens=loop_prompt_tokens,
                completion_tokens=loop_completion_tokens,
            )

        # 证据收集成功 → 复用 P0 统一答案合成链路（prompt_builder + answer 同款 prompt）：
        # - ReAct 的自主性体现在"拆问/多轮/换工具"的证据收集阶段；
        # - 最终答案合成复用 quick path 成熟 prompt，天然保证 [N] 引用格式、
        #   无过程性语句、与 evidence 编号严格一致（citations 可确定性映射）。
        synth_start = time.time()
        synth_messages = build_messages(question, evidence)
        answer, synth_usage = generate_answer_with_usage(synth_messages)
        answer = (answer or "").strip()
        synth_ms = (time.time() - synth_start) * 1000.0

        prompt_tokens = loop_prompt_tokens + int(synth_usage.get("prompt_tokens", 0) or 0)
        completion_tokens = loop_completion_tokens + int(synth_usage.get("completion_tokens", 0) or 0)

        if not answer:
            rag_trace["react_agent"] = {
                "trigger_reason": trigger_reason,
                "tool_rounds": tool_rounds,
                "evidence_count": len(evidence),
                "status": "empty_synthesis",
            }
            return _finalize_failure(
                state,
                reason="react_error",
                debug_info=debug_info,
                rag_trace=rag_trace,
                elapsed_ms=(time.time() - start) * 1000.0,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

        # 成功：重置前序 grade/grounding 失败标记，交给 grounding_check 重新门控
        state["need_fallback"] = False
        state["fallback_reason"] = None
        set_fallback_reason(rag_trace, None)
        record_timing(rag_trace, "react_agent_ms", (time.time() - start) * 1000.0)
        record_timing(rag_trace, "react_synthesis_ms", synth_ms)
        record_token_usage(
            rag_trace,
            node="react_agent",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=(time.time() - start) * 1000.0,
            source="llm",
        )

        state["final_answer"] = answer
        # 证据回写：grounding_check 与 citations 均从 reranked_docs 取
        state["reranked_docs"] = evidence
        state["retrieved_docs"] = evidence
        citations = build_citations(answer, evidence)
        state["citations"] = citations

        rag_trace["react_agent"] = {
            "trigger_reason": trigger_reason,
            "tool_rounds": tool_rounds,
            "evidence_count": len(evidence),
            "citation_count": len(citations),
            "synthesis_ms": round(synth_ms, 2),
            "status": "success",
        }

        debug_info.update(
            {
                "react_status": "success",
                "react_tool_rounds": tool_rounds,
                "react_evidence_count": len(evidence),
                "answer_status": "react_success",
                "used_context": "react_tools",
                "answer_chars": len(answer),
                "citation_count": len(citations),
                "context_doc_count": len(evidence),
            }
        )
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info

        logger.info(
            "react agent success | reason=%s | tool_rounds=%s | evidence=%s | citations=%s | tokens=%s/%s",
            trigger_reason, tool_rounds, len(evidence), len(citations),
            prompt_tokens, completion_tokens,
        )
        return state

    except Exception as exc:
        elapsed_ms = (time.time() - start) * 1000.0
        # P3-3：异常日志掩码（异常文本可能夹带工具返回的证据片段）
        logger.exception(
            "react agent failed | reason=%s | error=%s",
            trigger_reason,
            mask_pii(str(exc)),
        )
        rag_trace["react_agent"] = {
            "trigger_reason": trigger_reason,
            "status": "error",
            "error": str(exc),
        }
        return _finalize_failure(
            state,
            reason="react_error",
            debug_info=debug_info,
            rag_trace=rag_trace,
            elapsed_ms=elapsed_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
