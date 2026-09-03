from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    """
    Agent 运行时状态
    """

    question: str
    session_id: str
    chat_history: List[Dict[str, str]]

    route: str

    # P1-2 新增：三层漏斗路由 —— 是否前置升级 ReAct（规则命中 OR classify LLM 判定）
    need_react: bool
    # P1-2 新增：ReAct 链路是否已执行过（防循环护栏，保证 ReAct 最多执行一次）
    react_attempted: bool
    # P1-2 新增：升级 ReAct 的原因（rule_* / llm_complex / evidence_insufficient / grounding_failed_retry）
    react_reason: Optional[str]

    cache_hit: bool
    cached_answer: Optional[str]

    rewritten_question: Optional[str]

    retrieved_docs: List[Dict[str, Any]]
    reranked_docs: List[Dict[str, Any]]
    initial_query: str
    initial_retrieved_docs: List[Dict[str, Any]]
    initial_reranked_docs: List[Dict[str, Any]]
    evidence_grade: str
    grade_reason: Optional[str]
    grade_metrics: Dict[str, Any]
    need_query_expansion: bool
    expanded_queries: List[str]
    query_expansion_strategy: List[str]
    expanded_retrieved_docs: List[Dict[str, Any]]
    combined_retrieved_docs: List[Dict[str, Any]]
    expanded_reranked_docs: List[Dict[str, Any]]
    expansion_attempted: bool
    retrieval_attempts: List[Dict[str, Any]]

    final_answer: Optional[str]
    # P0-1 新增：答案内联引用溯源 [{index, chunk_id, text, source, score}]
    citations: List[Dict[str, Any]]
    # P0-2 新增：groundedness 校验结果
    grounding_passed: bool
    grounding_reason: Optional[str]
    rag_trace: Dict[str, Any]

    need_retry: bool

    # 第9天新增：是否需要进入 fallback
    need_fallback: bool
    fallback_reason: Optional[str]

    debug_info: Dict[str, Any]
