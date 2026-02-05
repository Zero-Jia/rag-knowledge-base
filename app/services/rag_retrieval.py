from app.config import settings

from app.services.retrieval_service import retrieve_chunks
from app.services.hybrid_retrieval import hybrid_retrieve
from app.services.advanced_retrieval import retrieve_with_rerank

def rag_retrieve(query:str):
    """
    统一 RAG 检索入口：由配置决定策略
    """
    mode = settings.rag.retrieval_mode
    top_k = settings.rag.top_k

    if mode == "vector":
        return retrieve_chunks(query, top_k)
    if mode == "hybrid":
        return hybrid_retrieve(query, top_k)
    if mode == "rerank":
        # rerank 里一般会用 rerank_candidates
        # 如果你的 retrieve_with_rerank 支持该参数，建议传进去
        try:
            return retrieve_with_rerank(
                query=query,
                top_k=top_k,
                rerank_candidates=settings.rag.rerank_candidates,
            )
        except TypeError:
            # 保底兼容你旧签名
            return retrieve_with_rerank(query, top_k)
    raise ValueError(f"Unknown retrieval mode: {mode}")
    