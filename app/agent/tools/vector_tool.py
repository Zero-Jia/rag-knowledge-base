from typing import Annotated, Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import Field

from app.agent.tools._common import (
    DEFAULT_TEXT_LIMIT,
    format_chunks_for_llm,
    format_tool_error,
)
from app.services.retrieval_service import retrieve_chunks


def vector_search_tool(
    question: str,
    top_k: int = 5,
    *,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Agent 向量检索工具

    说明：
    - 直接复用现有 retrieval_service.retrieve_chunks
    - 返回统一的文档列表结构
    - P0-3: user_id 非 None 时按租户过滤
    """
    q = (question or "").strip()
    if not q:
        return []

    results = retrieve_chunks(q, top_k=top_k, user_id=user_id) or []

    normalized_results: List[Dict[str, Any]] = []
    for item in results:
        normalized_results.append(
            {
                "text": item.get("text", ""),
                "document_id": item.get("document_id"),
                "chunk_index": item.get("chunk_index"),
                "chunk_id": item.get("chunk_id"),
                "chunk_level": item.get("chunk_level"),
                "parent_chunk_id": item.get("parent_chunk_id"),
                "root_chunk_id": item.get("root_chunk_id"),
                "auto_merged": item.get("auto_merged", False),
                "merged_child_count": item.get("merged_child_count"),
                "score": item.get("score"),
                "source": "vector",
            }
        )

    return normalized_results


def make_vector_search_tool(
    *,
    user_id: Optional[int] = None,
    text_limit: int = DEFAULT_TEXT_LIMIT,
) -> StructuredTool:
    """
    构造向量检索 LangChain Tool（P1-1）。

    - 纯函数 ``vector_search_tool`` 保持不变，graph quick path 继续直接调用
    - ``user_id`` 服务端闭包绑定，不暴露给 LLM（租户隔离防越权）
    - ``text_limit`` 控制返回片段正文截断长度
    - Tool 版本返回紧凑 JSON 字符串，供 P1-2 ReAct agent 的 ToolMessage 消费
    """

    def vector_search(
        query: Annotated[str, Field(description="检索查询，自然语言问题")],
        top_k: Annotated[int, Field(description="返回的知识库片段数量，默认 5")] = 5,
    ) -> str:
        """向量语义检索知识库片段。"""
        q = (query or "").strip()
        if not q:
            return format_tool_error("query 不能为空")

        try:
            chunks = vector_search_tool(q, top_k=top_k, user_id=user_id)
        except Exception as exc:  # Tool 不抛异常，返回错误让 agent 自纠
            return format_tool_error(f"向量检索失败：{exc}")

        if not chunks:
            return format_tool_error(
                "向量检索无结果，可换用 keyword_search 或调整查询表述"
            )

        return format_chunks_for_llm(chunks, text_limit=text_limit)

    return StructuredTool.from_function(
        vector_search,
        name="vector_search",
        description=(
            "向量语义检索知识库，适合同义/近义表述、概念性问题的语义匹配。"
            "输入自然语言问题，返回最相似的知识库片段 JSON。"
            "常规知识库问答优先使用 hybrid_search（向量+关键词融合，效果更稳）；"
            "本工具适合混合检索无结果时的语义兜底，或需要纯语义相似度的场景。"
        ),
    )
