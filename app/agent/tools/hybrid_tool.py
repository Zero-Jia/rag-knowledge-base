from typing import Annotated, Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import Field

from app.agent.tools._common import (
    DEFAULT_TEXT_LIMIT,
    format_chunks_for_llm,
    format_tool_error,
)
from app.services.hybrid_retrieval import hybrid_retrieve


def hybrid_search_tool(
    question: str,
    top_k: int = 5,
    user_id: Optional[int] = None,
    rag_trace: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Agent 混合检索工具

    说明：
    - 直接复用现有 hybrid_retrieve
    - 返回统一结构的文档列表
    """
    q = (question or "").strip()
    if not q:
        return []

    results = hybrid_retrieve(
        query=q,
        top_k=top_k,
        user_id=user_id,
        mode="hybrid",
        rag_trace=rag_trace,
    ) or []

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
                "retrieval_sources": item.get("retrieval_sources"),
                "score": item.get("score"),
                "final_score": item.get("final_score"),
                "vector_score": item.get("vector_score"),
                "bm25_score": item.get("bm25_score"),
                "normalized_vector_score": item.get("normalized_vector_score"),
                "normalized_bm25_score": item.get("normalized_bm25_score"),
                "source": "hybrid",
            }
        )

    return normalized_results


def make_hybrid_search_tool(
    *,
    user_id: Optional[int] = None,
    rag_trace: Optional[Dict[str, Any]] = None,
    text_limit: int = DEFAULT_TEXT_LIMIT,
) -> StructuredTool:
    """
    构造混合检索 LangChain Tool（P1-1，ReAct agent 的首选检索工具）。

    - 纯函数 ``hybrid_search_tool`` 保持不变，graph quick path 继续直接调用
    - ``user_id`` 服务端闭包绑定，不暴露给 LLM（租户隔离防越权）
    - ``rag_trace`` 可选透传，hybrid_retrieve 内部继续记录 timing / cache_hit
    - ``text_limit`` 控制返回片段正文截断长度（ReAct 链路可调大以保留完整证据）
    - 检索/融合/auto-merge 均不调用 LLM，无 token 消耗，P0-6 统计无需特殊处理
    """

    def hybrid_search(
        query: Annotated[str, Field(description="检索查询，自然语言问题")],
        top_k: Annotated[int, Field(description="返回的知识库片段数量，默认 5")] = 5,
    ) -> str:
        """混合检索（向量+BM25 关键词融合）知识库片段。"""
        q = (query or "").strip()
        if not q:
            return format_tool_error("query 不能为空")

        try:
            chunks = hybrid_search_tool(
                question=q,
                top_k=top_k,
                user_id=user_id,
                rag_trace=rag_trace,
            )
        except Exception as exc:  # Tool 不抛异常，返回错误让 agent 自纠
            return format_tool_error(f"混合检索失败：{exc}")

        if not chunks:
            return format_tool_error(
                "混合检索无结果，可换用 keyword_search / vector_search 或改写查询"
            )

        return format_chunks_for_llm(chunks, text_limit=text_limit)

    return StructuredTool.from_function(
        hybrid_search,
        name="hybrid_search",
        description=(
            "知识库混合检索工具（向量语义检索 + BM25 关键词检索融合，推荐首选）。"
            "输入自然语言问题，返回最相关的知识库片段 JSON（含 chunk_id / 正文 / 分数）。"
            "回答知识库相关问题时应优先调用本工具；需要精确术语匹配可搭配 keyword_search，"
            "拿到候选片段后如需精排可调用 rerank。"
        ),
    )
