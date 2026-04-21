import logging
import time
from typing import Any, Dict, Optional

from app.core.config import settings
from app.schemas.rag_trace import (
    ensure_rag_trace,
    record_initial_chunks,
    record_merged_chunks,
    record_timing,
    set_fallback_reason,
)
from app.services.advanced_retrieval import retrieve_with_rerank
from app.services.hybrid_retrieval import hybrid_retrieve
from app.services.request_context import get_request_id
from app.services.retrieval_service import retrieve_chunks

logger = logging.getLogger("rag.retrieval")


def rag_retrieve(query: str, rag_trace: Optional[Dict[str, Any]] = None):
    """
    Unified RAG retrieval entrypoint.

    `rag_trace` is optional to preserve existing callers. When provided, this
    function mutates it in-place so the answer stage can return the full trace.
    """
    rid = get_request_id()
    start = time.time()

    mode = settings.RETRIEVAL_MODE
    top_k = settings.TOP_K
    trace = ensure_rag_trace(
        rag_trace,
        original_query=query,
        retrieval_mode=mode,
    )

    logger.info(
        "Retrieval start | rid=%s | mode=%s | top_k=%s | query='%s'",
        rid,
        mode,
        top_k,
        query,
    )

    try:
        if mode == "vector":
            results = retrieve_chunks(query, top_k)
            record_initial_chunks(trace, results)
            record_merged_chunks(trace, results)

        elif mode == "hybrid":
            results = hybrid_retrieve(query, top_k, rag_trace=trace)

        elif mode == "rerank":
            results = retrieve_with_rerank(
                query=query,
                top_k=top_k,
                rag_trace=trace,
            )

        else:
            raise ValueError(f"Unknown retrieval mode: {mode}")

        elapsed = time.time() - start
        record_timing(trace, "retrieval_total_ms", elapsed * 1000.0)
        logger.info(
            "Retrieval done  | rid=%s | mode=%s | chunks=%s | time=%.3fs",
            rid,
            mode,
            len(results),
            elapsed,
        )
        return results

    except Exception as e:
        elapsed = time.time() - start
        set_fallback_reason(trace, str(e))
        record_timing(trace, "retrieval_total_ms", elapsed * 1000.0)
        logger.error(
            "Retrieval fail  | rid=%s | mode=%s | time=%.3fs | error=%s",
            rid,
            mode,
            elapsed,
            e,
        )
        raise
