from typing import Any, Dict, List

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
                "score": item.get("score"),
                "final_score": item.get("final_score"),
                "vector_score": item.get("vector_score"),
                "bm25_score": item.get("bm25_score"),
                "rerank_score": item.get("rerank_score"),
                "source": item.get("source", "unknown"),
            }
        )

    return normalized_results