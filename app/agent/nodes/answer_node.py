from typing import Any, Dict, List

from app.agent.state import AgentState
from app.agent.tools.cache_tool import save_agent_cache
from app.services.prompt_builder import build_messages
from app.services.llm_service import generate_answer


def answer_node(state: AgentState) -> AgentState:
    """
    Agent 回答节点

    当前版本逻辑：
    1. 如果缓存已命中，则直接跳过
    2. 如果 route == chat，则直接用简单 messages 调 LLM
    3. 否则优先使用 reranked_docs，其次 retrieved_docs
    4. 如果上下文为空，则返回兜底回答
    5. 成功后保存 final_answer
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    question = (state.get("question") or "").strip()
    route = state.get("route", "kb_qa")

    if state.get("cache_hit") is True:
        debug_info["answer_status"] = "skipped_due_to_cache_hit"
        state["debug_info"] = debug_info
        return state

    if not question:
        state["final_answer"] = "问题不能为空。"
        debug_info["answer_status"] = "empty_question"
        state["debug_info"] = debug_info
        return state

    # 1) chat 模式：直接调用 LLM，不走知识库上下文
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
        answer = generate_answer(messages)

        state["final_answer"] = answer
        debug_info["answer_status"] = "chat_success"
        debug_info["used_context"] = "none"
        debug_info["answer_chars"] = len(answer)
        state["debug_info"] = debug_info
        return state

    # 2) kb_qa / followup 模式：使用知识库上下文
    reranked_docs: List[Dict[str, Any]] = state.get("reranked_docs", [])
    retrieved_docs: List[Dict[str, Any]] = state.get("retrieved_docs", [])

    context_docs = reranked_docs if reranked_docs else retrieved_docs

    if not context_docs:
        state["final_answer"] = "当前知识库中没有检索到足够相关的内容，暂时无法给出可靠答案。"
        debug_info["answer_status"] = "no_context_docs"
        debug_info["context_doc_count"] = 0
        state["debug_info"] = debug_info
        return state

    messages = build_messages(question, context_docs)
    answer = generate_answer(messages)

    state["final_answer"] = answer
    debug_info["answer_status"] = "success"
    debug_info["context_doc_count"] = len(context_docs)
    debug_info["used_context"] = "reranked_docs" if reranked_docs else "retrieved_docs"
    debug_info["answer_chars"] = len(answer)
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