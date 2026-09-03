import json
from typing import Annotated, Any, Dict, List

from langchain_core.tools import StructuredTool
from pydantic import Field

from app.agent.tools._common import (
    DEFAULT_TEXT_LIMIT,
    format_chunks_for_llm,
    format_tool_error,
)
from app.services.rerank_service import RerankService


def rerank_tool(question: str, docs: List[Dict[str, Any]], top_n: int = 3) -> List[Dict[str, Any]]:
    """
    Agent 的 rerank 工具

    说明：
    - 直接复用现有 RerankService
    - 输入 docs 应至少包含 text 字段
    - 返回按 rerank_score 排序后的前 top_n 条
    """
    q = (question or "").strip()
    if not q:
        return []

    if not docs:
        return []

    service = RerankService()
    reranked = service.rerank(q, docs)

    normalized_results: List[Dict[str, Any]] = []
    for item in reranked[:top_n]:
        normalized_results.append(
            {
                "text": item.get("text", ""),
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
                "chunk_index": item.get("chunk_index"),
                "chunk_level": item.get("chunk_level"),
                "parent_chunk_id": item.get("parent_chunk_id"),
                "root_chunk_id": item.get("root_chunk_id"),
                "auto_merged": item.get("auto_merged", False),
                "merged_child_count": item.get("merged_child_count"),
                "score": item.get("score"),
                "final_score": item.get("final_score"),
                "vector_score": item.get("vector_score"),
                "bm25_score": item.get("bm25_score"),
                "rerank_score": item.get("rerank_score"),
                "source": item.get("source", "unknown"),
            }
        )

    return normalized_results


def _parse_docs_arg(raw: str) -> List[Dict[str, Any]]:
    """
    解析 LLM 传入的 docs 参数（JSON 字符串）。

    兼容两种形态：
    - 检索工具的完整返回：``{"count": N, "chunks": [...]}``
    - 裸片段数组：``[{"chunk_id": ..., "text": ...}, ...]``
    仅保留含 text 字段的 dict 元素。
    """
    data = json.loads(raw or "[]")
    if isinstance(data, dict) and isinstance(data.get("chunks"), list):
        data = data["chunks"]
    if not isinstance(data, list):
        raise ValueError("docs 必须是片段数组或检索工具返回的 JSON")
    return [item for item in data if isinstance(item, dict) and item.get("text")]


def make_rerank_tool(text_limit: int = DEFAULT_TEXT_LIMIT) -> StructuredTool:
    """
    构造 rerank 精排 LangChain Tool（P1-1）。

    - 纯函数 ``rerank_tool`` 保持不变，graph quick path（rerank_node）继续直接调用
    - cross-encoder 为本地模型推理，不调用 LLM、无 token 消耗、无租户数据访问
      （user_id 隔离已在上游检索环节完成），因此无需闭包注入 user_id
    - ``text_limit`` 控制返回片段正文截断长度
    - 典型 ReAct 用法：先 hybrid_search 取候选 → 把返回 JSON 作为 docs 传入精排
    """

    def rerank(
        query: Annotated[str, Field(description="检索查询，自然语言问题")],
        docs: Annotated[
            str,
            Field(
                description=(
                    "待精排的候选片段 JSON 字符串，直接传入检索工具"
                    "（hybrid_search/vector_search/keyword_search）的返回内容，"
                    '格式为 {"count": N, "chunks": [{"chunk_id": ..., "text": ...}]}'
                )
            ),
        ],
        top_n: Annotated[int, Field(description="精排后保留的片段数量，默认 3")] = 3,
    ) -> str:
        """对候选知识库片段按与问题的相关性做 cross-encoder 精排。"""
        q = (query or "").strip()
        if not q:
            return format_tool_error("query 不能为空")

        try:
            candidate_docs = _parse_docs_arg(docs)
        except Exception as exc:
            return format_tool_error(
                f"docs 参数解析失败：{exc}；请直接传入检索工具返回的 JSON 字符串"
            )

        if not candidate_docs:
            return format_tool_error("docs 中没有可用的候选片段（每个片段需含 text 字段）")

        try:
            reranked = rerank_tool(q, candidate_docs, top_n=top_n)
        except Exception as exc:  # Tool 不抛异常，返回错误让 agent 自纠
            return format_tool_error(f"精排失败：{exc}")

        return format_chunks_for_llm(reranked, text_limit=text_limit)

    return StructuredTool.from_function(
        rerank,
        name="rerank",
        description=(
            "对检索到的候选知识库片段做 cross-encoder 相关性精排。"
            "当检索返回片段较多、需要按与问题的相关程度重新排序取最相关的几条时使用。"
            "输入问题和候选片段 JSON（来自 hybrid_search/keyword_search/vector_search "
            "的返回），返回精排后的片段 JSON。"
        ),
    )
