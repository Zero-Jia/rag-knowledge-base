from typing import Any, Dict, List, Optional

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
