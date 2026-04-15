from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes.cache_node import cache_node
from app.agent.nodes.retrieve_node import retrieve_node
from app.agent.nodes.rerank_node import rerank_node


def route_after_cache(state: AgentState) -> str:
    """
    cache_node 之后的路由逻辑
    """
    if state.get("cache_hit") is True:
        return "end"
    return "retrieve"


def build_agent_graph():
    """
    第4天版本：
    cache -> (hit ? END : retrieve) -> rerank -> END
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("cache", cache_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("rerank", rerank_node)

    workflow.set_entry_point("cache")

    workflow.add_conditional_edges(
        "cache",
        route_after_cache,
        {
            "end": END,
            "retrieve": "retrieve",
        },
    )

    workflow.add_edge("retrieve", "rerank")
    workflow.add_edge("rerank", END)

    return workflow.compile()


agent_graph = build_agent_graph()