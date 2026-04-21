import time
from typing import Any, Dict, List

from app.agent.state import AgentState
from app.agent.tools.cache_tool import save_agent_cache
from app.schemas.rag_trace import record_timing, set_fallback_reason
from app.services.llm_service import generate_answer
from app.services.prompt_builder import build_messages


def answer_node(state: AgentState) -> AgentState:
    """
    Agent answer node.

    It also records answer-stage timing into rag_trace. Existing state fields
    and return shape are preserved.
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    rag_trace: Dict[str, Any] = state.get("rag_trace", {})
    question = (state.get("question") or "").strip()
    route = state.get("route", "kb_qa")

    if state.get("cache_hit") is True:
        debug_info["answer_status"] = "skipped_due_to_cache_hit"
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    if not question:
        state["final_answer"] = "问题不能为空。"
        set_fallback_reason(rag_trace, "empty_question")
        debug_info["answer_status"] = "empty_question"
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    if route == "chat":
        messages = [
            {
                "role": "system",
                "content": "你是一个友好的 AI 助手，请直接回答用户的问题。",
            },
            {
                "role": "user",
                "content": question,
            },
        ]
        answer_start = time.time()
        answer = generate_answer(messages)
        record_timing(rag_trace, "answer_ms", (time.time() - answer_start) * 1000.0)

        state["final_answer"] = answer
        debug_info["answer_status"] = "chat_success"
        debug_info["used_context"] = "none"
        debug_info["answer_chars"] = len(answer)
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    reranked_docs: List[Dict[str, Any]] = state.get("reranked_docs", [])
    retrieved_docs: List[Dict[str, Any]] = state.get("retrieved_docs", [])
    context_docs = reranked_docs if reranked_docs else retrieved_docs

    if not context_docs:
        state["final_answer"] = "当前知识库中没有检索到足够相关的内容，暂时无法给出可靠答案。"
        set_fallback_reason(rag_trace, "no_context_docs")
        debug_info["answer_status"] = "no_context_docs"
        debug_info["context_doc_count"] = 0
        state["rag_trace"] = rag_trace
        state["debug_info"] = debug_info
        return state

    messages = build_messages(question, context_docs)
    answer_start = time.time()
    answer = generate_answer(messages)
    record_timing(rag_trace, "answer_ms", (time.time() - answer_start) * 1000.0)

    state["final_answer"] = answer
    debug_info["answer_status"] = "success"
    debug_info["context_doc_count"] = len(context_docs)
    debug_info["used_context"] = "reranked_docs" if reranked_docs else "retrieved_docs"
    debug_info["answer_chars"] = len(answer)
    state["rag_trace"] = rag_trace
    state["debug_info"] = debug_info

    user_id = debug_info.get("user_id")
    top_k = debug_info.get("top_k", 5)

    save_agent_cache(
        question=question,
        answer=answer,
        chunks=context_docs,
        user_id=user_id,
        retrieval_mode="agentic",
        top_k=top_k,
    )

    return state
