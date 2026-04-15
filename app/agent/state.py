from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    """
    Agent 运行时状态

    说明：
    - total=False 表示这些字段都不是强制每一步都必须存在
    - 后续每个 node 都可以逐步往 state 里补充内容
    """

    # 用户原始问题
    question: str

    # 会话 id，用于多轮对话
    session_id: str

    # 历史消息，后续可用于 follow-up 问题处理
    chat_history: List[Dict[str, str]]

    # 问题分类结果，例如:
    # "chat" / "kb_qa" / "followup"
    route: str

    # 是否命中缓存
    cache_hit: bool

    # 缓存中的答案
    cached_answer: Optional[str]

    # 改写后的问题
    rewritten_question: Optional[str]

    # 检索到的原始文档列表
    retrieved_docs: List[Dict[str, Any]]

    # rerank 后的文档列表
    reranked_docs: List[Dict[str, Any]]

    # 最终回答
    final_answer: Optional[str]

    # 是否需要再次检索或重试
    need_retry: bool

    # 调试信息 / 日志信息
    debug_info: Dict[str, Any]