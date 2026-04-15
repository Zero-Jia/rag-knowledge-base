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
    2. 优先使用 reranked_docs 作为上下文
    3. 如果 reranked_docs 为空，则退回 retrieved_docs
    4. 如果上下文仍为空，则返回一个明确的兜底回答
    5. 构造 messages -> 调用 LLM -> 保存 final_answer
    6. 将结果写入 agent cache
    """
    debug_info: Dict[str, Any] = state.get("debug_info", {})
    question = (state.get("question") or "").strip()

    # 1) 如果前面 cache_node 已经命中缓存，这里就不再生成答案
    if state.get("cache_hit") is True:
        debug_info["answer_status"] = "skipped_due_to_cache_hit"
        state["debug_info"] = debug_info
        return state

    # 2) 空问题兜底
    if not question:
        state["final_answer"] = "问题不能为空。"
        debug_info["answer_status"] = "empty_question"
        state["debug_info"] = debug_info
        return state

    # 3) 优先使用 reranked_docs，其次 retrieved_docs
    reranked_docs: List[Dict[str, Any]] = state.get("reranked_docs", [])
    retrieved_docs: List[Dict[str, Any]] = state.get("retrieved_docs", [])

    context_docs = reranked_docs if reranked_docs else retrieved_docs

    # 4) 没有上下文时，给出兜底回答
    if not context_docs:
        state["final_answer"] = "当前知识库中没有检索到足够相关的内容，暂时无法给出可靠答案。"
        debug_info["answer_status"] = "no_context_docs"
        debug_info["context_doc_count"] = 0
        state["debug_info"] = debug_info
        return state

    # 5) 构造 prompt messages
    messages = build_messages(question, context_docs)

    # 6) 调用 LLM 生成回答
    answer = generate_answer(messages)

    # 7) 写回 state
    state["final_answer"] = answer
    debug_info["answer_status"] = "success"
    debug_info["context_doc_count"] = len(context_docs)
    debug_info["used_context"] = "reranked_docs" if reranked_docs else "retrieved_docs"
    debug_info["answer_chars"] = len(answer)
    state["debug_info"] = debug_info

    # 8) 写入 agent cache，方便 exact cache / semantic cache 复用
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