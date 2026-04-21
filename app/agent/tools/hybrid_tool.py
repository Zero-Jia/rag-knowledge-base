from typing import Any, Dict, List, Optional

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
