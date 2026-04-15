from langgraph.graph import StateGraph, END

from app.agent.state import AgentState
from app.agent.nodes.cache_node import cache_node


def build_agent_graph():
    """
    第2天版本：
    先只挂一个 cache_node，
    验证 LangGraph + state + node 能跑通
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("cache", cache_node)

    workflow.set_entry_point("cache")
    workflow.add_edge("cache", END)

    return workflow.compile()


agent_graph = build_agent_graph()