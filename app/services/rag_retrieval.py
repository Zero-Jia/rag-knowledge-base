import logging
import time

from app.config import settings
from app.services.retrieval_service import retrieve_chunks
from app.services.hybrid_retrieval import hybrid_retrieve
from app.services.advanced_retrieval import retrieve_with_rerank
from app.services.request_context import get_request_id

logger = logging.getLogger("rag.retrieval")

def rag_retrieve(query:str):
    """
    统一 RAG 检索入口：由配置决定策略
    """
    rid = get_request_id()
    start = time.time()

    mode = settings.rag.retrieval_mode
    top_k = settings.rag.top_k

    logger.info(f"Retrieval start | rid={rid} | mode={mode} | top_k={top_k} | query='{query}'")

    try:
        if mode == "vector":
            results = retrieve_chunks(query, top_k)

        elif mode == "hybrid":
            results = hybrid_retrieve(query, top_k)

        elif mode == "rerank":
            # rerank 里一般会用 rerank_candidates
            # 如果你的 retrieve_with_rerank 支持该参数，建议传进去
            try:
                results = retrieve_with_rerank(
                    query=query,
                    top_k=top_k,
                    rerank_candidates=settings.rag.rerank_candidates,
                )
            except TypeError:
                # 保底兼容你旧签名
                results = retrieve_with_rerank(query, top_k)
        else:
            raise ValueError(f"Unknown retrieval mode: {mode}")

        # 结束日志 + 耗时
        elapsed = time.time() - start
        logger.info(
            f"Retrieval done  | rid={rid} | mode={mode} | chunks={len(results)} | time={elapsed:.3f}s"
        )
        return results

    except Exception as e:
        # 失败日志 + 耗时
        elapsed = time.time() - start
        logger.error(
            f"Retrieval fail  | rid={rid} | mode={mode} | time={elapsed:.3f}s | error={e}"
        )
        raise