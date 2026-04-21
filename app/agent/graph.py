from langgraph.graph import END, StateGraph

from app.agent.nodes.answer_node import answer_node
from app.agent.nodes.cache_node import cache_node
from app.agent.nodes.classify_node import classify_node
from app.agent.nodes.fallback_node import fallback_node
from app.agent.nodes.grade_documents_node import grade_documents_node
from app.agent.nodes.query_expansion_node import query_expansion_node
from app.agent.nodes.rerank_expanded_node import rerank_expanded_node
from app.agent.nodes.rerank_node import rerank_node
from app.agent.nodes.retrieve_expanded_node import retrieve_expanded_node
from app.agent.nodes.retrieve_node import retrieve_node
from app.agent.nodes.rewrite_node import rewrite_node
from app.agent.state import AgentState


def route_after_classify(state: AgentState) -> str:
    route = state.get("route", "kb_qa")
    if route == "chat":
        return "answer"
    return "cache"


def route_after_cache(state: AgentState) -> str:
    if state.get("cache_hit") is True:
        return "end"

    route = state.get("route", "kb_qa")
    if route == "followup":
        return "rewrite"

    return "retrieve_initial"


def route_after_grade_documents(state: AgentState) -> str:
    """
    NEW: evidence gate after rerank.

    - sufficient evidence -> answer
    - insufficient first pass -> query_expansion
    - insufficient after expansion -> fallback
    """
    if state.get("need_query_expansion") is True:
        return "query_expansion"
    if state.get("need_fallback") is True:
        return "fallback"
    return "answer"


def build_agent_graph():
    """
    Phase 2 graph:

    classify
      -> cache
      -> rewrite
      -> retrieve_initial
      -> rerank_initial
      -> grade_documents
           -> answer
           -> query_expansion
                -> retrieve_expanded
                -> rerank_expanded
                -> grade_documents
                     -> answer / fallback

    NEW nodes:
    - grade_documents
    - query_expansion
    - retrieve_expanded
    - rerank_expanded
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
            "retrieve_initial": "retrieve_initial",
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
        },
    )

    workflow.add_edge("query_expansion", "retrieve_expanded")
    workflow.add_edge("retrieve_expanded", "rerank_expanded")
    workflow.add_edge("rerank_expanded", "grade_documents")

    workflow.add_edge("fallback", END)
    workflow.add_edge("answer", END)

    return workflow.compile()


agent_graph = build_agent_graph()
