from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes.classify_node import classify_node
from app.agent.nodes.cache_node import cache_node
from app.agent.nodes.rewrite_node import rewrite_node
from app.agent.nodes.retrieve_node import retrieve_node
from app.agent.nodes.rerank_node import rerank_node
from app.agent.nodes.answer_node import answer_node
from app.agent.nodes.fallback_node import fallback_node


def route_after_classify(state: AgentState) -> str:
    """
    classify_node 之后的路由逻辑
    """
    route = state.get("route", "kb_qa")
    if route == "chat":
        return "answer"
    return "cache"


def route_after_cache(state: AgentState) -> str:
    """
    cache_node 之后的路由逻辑
    """
    if state.get("cache_hit") is True:
        return "end"

    route = state.get("route", "kb_qa")
    if route == "followup":
        return "rewrite"

    return "retrieve"


def route_after_rerank(state: AgentState) -> str:
    """
    rerank_node 之后的路由逻辑：
    - 证据不足 -> fallback
    - 证据足够 -> answer
    """
    if state.get("need_fallback") is True:
        return "fallback"
    return "answer"


def build_agent_graph():
    """
    第9天版本：
    classify -> (chat ? answer : cache)
    cache -> (hit ? END : followup走rewrite，否则retrieve)
    rewrite -> retrieve -> rerank
    rerank -> (fallback / answer)
    fallback -> END
    answer -> END
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("classify", classify_node)
    workflow.add_node("cache", cache_node)
    workflow.add_node("rewrite", rewrite_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("rerank", rerank_node)
    workflow.add_node("fallback", fallback_node)
    workflow.add_node("answer", answer_node)

    workflow.set_entry_point("classify")

    workflow.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "answer": "answer",
            "cache": "cache",
        },
    )

    workflow.add_conditional_edges(
        "cache",
        route_after_cache,
        {
            "end": END,
            "rewrite": "rewrite",
            "retrieve": "retrieve",
        },
    )

    workflow.add_edge("rewrite", "retrieve")
    workflow.add_edge("retrieve", "rerank")

    workflow.add_conditional_edges(
        "rerank",
        route_after_rerank,
        {
            "fallback": "fallback",
            "answer": "answer",
        },
    )

    workflow.add_edge("fallback", END)
    workflow.add_edge("answer", END)

    return workflow.compile()


agent_graph = build_agent_graph()