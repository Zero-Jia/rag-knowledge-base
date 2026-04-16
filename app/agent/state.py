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

    final_answer: Optional[str]

    need_retry: bool

    # 第9天新增：是否需要进入 fallback
    need_fallback: bool
    fallback_reason: Optional[str]

    debug_info: Dict[str, Any]