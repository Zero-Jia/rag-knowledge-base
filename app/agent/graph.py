from langgraph.graph import END, StateGraph

from app.agent.nodes.answer_node import answer_node
from app.agent.nodes.cache_node import cache_node
from app.agent.nodes.classify_node import classify_node
from app.agent.nodes.fallback_node import fallback_node
from app.agent.nodes.grade_documents_node import grade_documents_node
from app.agent.nodes.grounding_check_node import grounding_check_node
from app.agent.nodes.query_expansion_node import query_expansion_node
from app.agent.nodes.rerank_expanded_node import rerank_expanded_node
from app.agent.nodes.rerank_node import rerank_node
from app.agent.nodes.retrieve_expanded_node import retrieve_expanded_node
from app.agent.nodes.retrieve_node import retrieve_node
from app.agent.nodes.rewrite_node import rewrite_node
from app.agent.react_agent import react_agent_node
from app.agent.state import AgentState
from app.core.config import settings


def _react_enabled() -> bool:
    """P1-2：ReAct 总开关（默认关闭，灰度/回滚与 Langfuse 开关同款策略）。"""
    return bool(getattr(settings, "REACT_AGENT_ENABLED", False))


def _can_upgrade_to_react(state: AgentState) -> bool:
    """
    P1-2 防循环护栏：开关开启且 ReAct 尚未执行过时才允许升级。
    react_agent_node 入口置 react_attempted=True，保证 ReAct 最多执行一次。
    """
    return _react_enabled() and state.get("react_attempted") is not True


def predict_react_upgrade(prev_node: str, state: AgentState) -> bool:
    """
    P1-2：供流式服务在节点完成后预测"下一步是否进入 react_agent"，
    以便提前推送 deep_research 过渡事件（路由判定逻辑集中在本文件，避免重复）。

    - cache 之后：cache miss 且 classify 前置判定 need_react
    - grade_documents 之后：expansion 二轮证据仍不足（need_fallback）
    - grounding_check 之后：groundedness 校验失败（need_fallback）
    """
    if not _can_upgrade_to_react(state):
        return False
    if prev_node == "cache":
        return state.get("cache_hit") is not True and state.get("need_react") is True
    if prev_node in ("grade_documents", "grounding_check"):
        return state.get("need_fallback") is True
    return False


def route_after_classify(state: AgentState) -> str:
    # P3-2：注入拦截短路 —— guard 命中时 classify 已置 need_fallback，
    # 直接进 fallback 终态拒答（跳过 cache/检索/回答）；开关关闭时
    # classify 从不提前置 need_fallback，本分支零行为，quick path 不受影响
    if state.get("need_fallback") is True:
        return "fallback"
    route = state.get("route", "kb_qa")
    if route == "chat":
        return "answer"
    return "cache"


def route_after_cache(state: AgentState) -> str:
    if state.get("cache_hit") is True:
        return "end"

    # P1-2 前置升级：classify 判定复杂问题（规则脚本 OR LLM need_react），
    # cache miss 后直接进入 ReAct 自主多轮检索
    if state.get("need_react") is True and _can_upgrade_to_react(state):
        return "react_agent"

    route = state.get("route", "kb_qa")
    if route == "followup":
        return "rewrite"

    return "retrieve_initial"


def route_after_grade_documents(state: AgentState) -> str:
    """
    NEW: evidence gate after rerank.

    - sufficient evidence -> answer
    - insufficient first pass -> query_expansion
    - insufficient after expansion -> react_agent（P1-2 后置升级）/ fallback
    """
    if state.get("need_query_expansion") is True:
        return "query_expansion"
    if state.get("need_fallback") is True:
        # P1-2 后置升级 1：expansion 二轮证据仍不足，fallback 前先让 ReAct
        # 拆子问题/换工具/闭环检索抢救一次
        if _can_upgrade_to_react(state):
            return "react_agent"
        return "fallback"
    return "answer"


def route_after_grounding(state: AgentState) -> str:
    """
    P0-2: faithfulness gate after answer generation.

    - grounding failed (answer not supported by evidence)
      -> react_agent（P1-2 后置升级 2，重新检索合成）/ fallback
    - grounding passed (or skipped for chat/cache/no-evidence) -> end
    """
    if state.get("need_fallback") is True:
        # P1-2 后置升级 2：答案未被证据支持，很可能是证据没捞全，
        # ReAct 重新检索合成一次；已尝试过则终态 fallback 拒答
        if _can_upgrade_to_react(state):
            return "react_agent"
        return "fallback"
    return "end"


def build_agent_graph():
    """
    Phase 2 graph:

    classify
      -> cache
      -> rewrite
      -> retrieve_initial
      -> rerank_initial
      -> grade_documents
           -> answer -> grounding_check -> (fallback | END)
           -> query_expansion
                -> retrieve_expanded
                -> rerank_expanded
                -> grade_documents
           -> fallback

    P0-2 NEW node:
    - grounding_check (faithfulness gate after answer, routes to fallback on failure)

    P1-2 NEW node:
    - react_agent (ReAct/Tool-Calling 链路，三层漏斗路由)：
      ① 前置升级：classify 判定复杂问题（规则脚本 OR LLM need_react），cache miss 后进入；
      ② 后置升级：grade_documents 二轮证据仍不足 → react_agent 抢救；
      ③ 后置升级：grounding_check 失败 → react_agent 重新检索合成。
      react_attempted 护栏保证 ReAct 最多执行一次；ReAct 产出后共享 grounding_check 门控，
      仍失败则终态 fallback。REACT_AGENT_ENABLED=False 时所有升级边回到原 quick path。
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("classify", classify_node)
    workflow.add_node("cache", cache_node)
    workflow.add_node("rewrite", rewrite_node)

    # Existing nodes reused as initial retrieval/rerank.
    workflow.add_node("retrieve_initial", retrieve_node)
    workflow.add_node("rerank_initial", rerank_node)

    # NEW: evidence grading and recovery branch.
    workflow.add_node("grade_documents", grade_documents_node)
    workflow.add_node("query_expansion", query_expansion_node)
    workflow.add_node("retrieve_expanded", retrieve_expanded_node)
    workflow.add_node("rerank_expanded", rerank_expanded_node)

    workflow.add_node("fallback", fallback_node)
    workflow.add_node("answer", answer_node)
    # P0-2：groundedness 校验节点，answer 之后执行
    workflow.add_node("grounding_check", grounding_check_node)
    # P1-2：ReAct（Tool Calling）节点，三层漏斗路由的升级链路
    workflow.add_node("react_agent", react_agent_node)

    workflow.set_entry_point("classify")

    workflow.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "answer": "answer",
            "cache": "cache",
            # P3-2：注入拦截短路（guard 命中 → 终态拒答）
            "fallback": "fallback",
        },
    )

    workflow.add_conditional_edges(
        "cache",
        route_after_cache,
        {
            "end": END,
            "rewrite": "rewrite",
            "retrieve_initial": "retrieve_initial",
            # P1-2：前置升级（classify 判定复杂问题，cache miss 后进 ReAct）
            "react_agent": "react_agent",
        },
    )

    workflow.add_edge("rewrite", "retrieve_initial")
    workflow.add_edge("retrieve_initial", "rerank_initial")
    workflow.add_edge("rerank_initial", "grade_documents")

    workflow.add_conditional_edges(
        "grade_documents",
        route_after_grade_documents,
        {
            "answer": "answer",
            "query_expansion": "query_expansion",
            "fallback": "fallback",
            # P1-2：后置升级 1（expansion 二轮证据仍不足 → ReAct 抢救）
            "react_agent": "react_agent",
        },
    )

    workflow.add_edge("query_expansion", "retrieve_expanded")
    workflow.add_edge("retrieve_expanded", "rerank_expanded")
    workflow.add_edge("rerank_expanded", "grade_documents")

    workflow.add_edge("fallback", END)
    # P0-2：answer 不再直接 END，先过 grounding_check 校验
    workflow.add_edge("answer", "grounding_check")
    # P1-2：ReAct 产出后与 quick path 共享同一个 grounding 质量门；
    # 无证据/异常时 react_agent_node 置 need_fallback + 空答案，
    # grounding_check 空答案短路通过，route_after_grounding 终态转 fallback
    workflow.add_edge("react_agent", "grounding_check")
    workflow.add_conditional_edges(
        "grounding_check",
        route_after_grounding,
        {
            "fallback": "fallback",
            "end": END,
            # P1-2：后置升级 2（grounding 失败 → ReAct 重新检索合成一次）
            "react_agent": "react_agent",
        },
    )

    return workflow.compile()


agent_graph = build_agent_graph()
