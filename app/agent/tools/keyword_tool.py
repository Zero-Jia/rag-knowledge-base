"""P1-1: 关键词/BM25 检索 Tool。

- ``keyword_search_tool``：纯函数，返回统一结构的 dict list，graph 节点可直接调用
- ``make_keyword_search_tool``：LangChain ``StructuredTool`` 工厂，
  ``user_id`` 在服务端闭包绑定（不作为 LLM 可填参数，防越权），
  供 P1-2 ReAct agent 自主调用
"""

from typing import Annotated, Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import Field

from app.agent.tools._common import (
    DEFAULT_TEXT_LIMIT,
    format_chunks_for_llm,
    format_tool_error,
)
from app.services.hybrid_retrieval import keyword_recall


def keyword_search_tool(
    question: str,
    top_k: int = 5,
    *,
    user_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Agent 关键词/BM25 检索工具（纯函数）

    说明：
    - 复用 hybrid_retrieval.keyword_recall（与 hybrid 内部词法召回同一实现）
    - 仅做 L3 leaf chunk 的 BM25 词法召回，不做向量融合 / auto-merge
    - 底层召回池按 RECALL_MULTIPLIER 放大（供融合阶段使用），
      独立工具出口切 [:top_k] 保证返回条数符合工具语义
    - P0-3: user_id 非 None 时按租户过滤
    """
    q = (question or "").strip()
    if not q:
        return []

    results = (keyword_recall(q, top_k=top_k, user_id=user_id) or [])[:top_k]

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
                "keyword_score": item.get("keyword_score"),
                "bm25_score": item.get("bm25_score"),
                "exact_match_score": item.get("exact_match_score"),
                "score": item.get("keyword_score"),
                "source": "keyword",
            }
        )

    return normalized_results


def make_keyword_search_tool(
    *,
    user_id: Optional[int] = None,
    text_limit: int = DEFAULT_TEXT_LIMIT,
) -> StructuredTool:
    """
    构造关键词检索 LangChain Tool。

    安全约束：``user_id`` 由服务端（chat 入口）闭包注入，绝不由 LLM 填写，
    避免 agent 被诱导跨租户检索（P0-3 租户隔离在 Tool 层同样生效）。
    ``text_limit`` 控制返回片段正文截断长度。
    """

    def keyword_search(
        query: Annotated[str, Field(description="检索查询，自然语言问题或关键词")],
        top_k: Annotated[int, Field(description="返回的知识库片段数量，默认 5")] = 5,
    ) -> str:
        """关键词/BM25 词法检索知识库片段。"""
        q = (query or "").strip()
        if not q:
            return format_tool_error("query 不能为空")

        try:
            chunks = keyword_search_tool(q, top_k=top_k, user_id=user_id)
        except Exception as exc:  # Tool 不抛异常，返回错误让 agent 自纠
            return format_tool_error(f"关键词检索失败：{exc}")

        if not chunks:
            return format_tool_error(
                "未检索到关键词匹配的知识库片段，可换用 hybrid_search 或调整查询词"
            )

        return format_chunks_for_llm(chunks, text_limit=text_limit)

    return StructuredTool.from_function(
        keyword_search,
        name="keyword_search",
        description=(
            "关键词/BM25 词法检索知识库，适合精确术语、专有名词、编号、错误码、"
            "配置项等字面匹配场景。输入查询内容，返回最相关的知识库片段 JSON。"
            "语义模糊或需要理解同义表述的问题优先使用 hybrid_search。"
        ),
    )
