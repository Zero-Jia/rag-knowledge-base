"""Agent 工具集。

两套入口并存（P1-1）：

1. 纯函数（``xxx_tool``）：返回 dict list，graph quick path 的节点直接调用，
   行为与 P0 阶段完全一致；
2. LangChain ``StructuredTool``（``make_xxx_tool`` / ``build_retrieval_tools``）：
   返回紧凑 JSON 字符串，供 P1-2 ReAct agent 通过 Tool Calling 自主调用。

安全约束：``user_id`` 由服务端在工厂处闭包绑定，不作为 LLM 可填写的工具参数，
确保租户隔离（P0-3）在 Tool 层同样生效。
"""

from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool

from app.agent.tools.hybrid_tool import (
    hybrid_search_tool,
    make_hybrid_search_tool,
)
from app.agent.tools.keyword_tool import (
    keyword_search_tool,
    make_keyword_search_tool,
)
from app.agent.tools.rerank_tool import make_rerank_tool, rerank_tool
from app.agent.tools.vector_tool import (
    make_vector_search_tool,
    vector_search_tool,
)

__all__ = [
    # 纯函数（graph quick path 使用）
    "vector_search_tool",
    "hybrid_search_tool",
    "keyword_search_tool",
    "rerank_tool",
    # LangChain Tool 工厂（P1-2 ReAct agent 使用）
    "build_retrieval_tools",
    "make_vector_search_tool",
    "make_hybrid_search_tool",
    "make_keyword_search_tool",
    "make_rerank_tool",
]


def build_retrieval_tools(
    user_id: Optional[int] = None,
    *,
    rag_trace: Optional[Dict[str, Any]] = None,
    text_limit: Optional[int] = None,
) -> List[StructuredTool]:
    """
    构造供 ReAct agent 使用的检索工具集（P1-2 接入）。

    - ``user_id``：服务端闭包绑定（租户隔离），LLM 无法通过工具参数越权
    - ``rag_trace``：可选透传给 hybrid_search，延续 P0 的 timing / cache_hit 记录
    - ``text_limit``：工具返回片段正文截断长度；None 时用各工厂默认值
      （ReAct 链路传 settings.REACT_TOOL_TEXT_LIMIT 保留更完整证据）
    - 返回顺序即推荐优先级：hybrid（融合主力）> vector（语义兜底）
      > keyword（精确词法）> rerank（候选精排）
    """
    common_kwargs: Dict[str, Any] = {}
    if text_limit is not None:
        common_kwargs["text_limit"] = text_limit

    return [
        make_hybrid_search_tool(user_id=user_id, rag_trace=rag_trace, **common_kwargs),
        make_vector_search_tool(user_id=user_id, **common_kwargs),
        make_keyword_search_tool(user_id=user_id, **common_kwargs),
        make_rerank_tool(**common_kwargs),
    ]
