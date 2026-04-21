from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    """
    Agent 运行时状态
    """

    question: str
    session_id: str
    chat_history: List[Dict[str, str]]

    route: str

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
    rag_trace: Dict[str, Any]

    need_retry: bool

    # 第9天新增：是否需要进入 fallback
    need_fallback: bool
    fallback_reason: Optional[str]

    debug_info: Dict[str, Any]
