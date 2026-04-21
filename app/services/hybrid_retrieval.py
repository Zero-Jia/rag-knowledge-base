from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.auto_merge_service import auto_merge_chunks
from app.services.cache_service import get_cache, make_cache_key, set_cache
from app.services.keyword_search import bm25_rerank, looks_overview_query
from app.services.retrieval_service import retrieve_all_chunks, retrieve_chunks
from app.schemas.rag_trace import (
    elapsed_ms,
    ensure_rag_trace,
    now_ms,
    record_auto_merge_steps,
    record_initial_chunks,
    record_merged_chunks,
    record_timing,
    set_cache_hit,
)

logger = logging.getLogger("rag.perf")

HYBRID_CACHE_VERSION = "hybrid_v4_auto_merge"


def _build_search_cache_key(
    *,
    query: str,
    user_id: Optional[int] = None,
    mode: str = "hybrid",
    top_k: int = settings.TOP_K,
    enable_auto_merge: bool = True,
) -> str:
    q = (query or "").strip()
    raw = (
        f"v={HYBRID_CACHE_VERSION}"
        f"|user={user_id}"
        f"|mode={mode}"
        f"|topk={top_k}"
        f"|auto_merge={int(enable_auto_merge)}"
        f"|q={q}"
    )
    return make_cache_key("search", raw)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _normalize(values: List[float]) -> List[float]:
    """Min-max normalize scores to [0, 1]."""
    if not values:
        return []

    min_value = min(values)
    max_value = max(values)
    if max_value == min_value:
        return [0.0 for _ in values]

    return [(value - min_value) / (max_value - min_value) for value in values]


def _chunk_key(item: Dict[str, Any]) -> str:
    doc_id = item.get("document_id")
    chunk_id = item.get("chunk_id")
    chunk_index = item.get("chunk_index")

    if chunk_id:
        return f"chunk_id:{chunk_id}"
    if doc_id is not None and chunk_index is not None:
        return f"doc:{doc_id}:chunk:{chunk_index}"
    return f"doc:{doc_id}:text:{hash(item.get('text', ''))}"


def _looks_definition_query(query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return False

    return looks_overview_query(q) or any(
        pattern in q
        for pattern in (
            "作用是什么",
            "含义是什么",
            "定义是什么",
            "起什么作用",
            "what is",
            "define",
        )
    )


def _is_l3_chunk(item: Dict[str, Any]) -> bool:
    """
    New hierarchical chunks have chunk_level=3 in Chroma.
    Old indexed chunks do not have chunk_level, so treat missing level as L3
    to preserve backward compatibility.
    """
    level = item.get("chunk_level")
    if level is None:
        return True
    try:
        return int(level) == 3
    except Exception:
        return True


def _keyword_recall(query: str, top_k: int) -> List[Dict[str, Any]]:
    """
    Keyword recall over vector-store leaf chunks.

    For hierarchical indexing this recalls L3 only. For old data without
    chunk_level metadata, chunks are treated as L3-compatible.
    """
    max_keyword_pool = int(getattr(settings, "HYBRID_KEYWORD_POOL_LIMIT", 2000))
    all_chunks = [item for item in retrieve_all_chunks(limit=max_keyword_pool) if _is_l3_chunk(item)]
    if not all_chunks:
        return []

    scored = bm25_rerank(query, all_chunks)
    scored.sort(key=lambda x: _safe_float(x.get("keyword_score"), 0.0), reverse=True)

    keyword_k = max(top_k * int(getattr(settings, "RECALL_MULTIPLIER", 2)), top_k)
    return [
        item
        for item in scored[:keyword_k]
        if _safe_float(item.get("keyword_score"), 0.0) > 0.0
    ]


def _merge_candidates(
    vector_results: List[Dict[str, Any]],
    keyword_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}

    for item in vector_results:
        if not _is_l3_chunk(item):
            continue
        copied = dict(item)
        copied["retrieval_sources"] = ["vector"]
        copied["vector_score"] = _safe_float(copied.get("score"), 1e9)
        copied.setdefault("auto_merged", False)
        merged[_chunk_key(copied)] = copied

    for item in keyword_results:
        if not _is_l3_chunk(item):
            continue
        key = _chunk_key(item)
        if key in merged:
            merged[key].update(
                {
                    "keyword_score": _safe_float(item.get("keyword_score"), 0.0),
                    "bm25_score": _safe_float(item.get("bm25_score"), 0.0),
                    "exact_match_score": _safe_float(item.get("exact_match_score"), 0.0),
                    "query_tokens": item.get("query_tokens"),
                    "focus_terms": item.get("focus_terms"),
                }
            )
            if "keyword" not in merged[key]["retrieval_sources"]:
                merged[key]["retrieval_sources"].append("keyword")
        else:
            copied = dict(item)
            copied["retrieval_sources"] = ["keyword"]
            copied.setdefault("auto_merged", False)
            merged[key] = copied

    return list(merged.values())


def _fuse_scores(query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        reranked_candidates = bm25_rerank(query, candidates)
    except Exception as exc:
        logger.warning("bm25_rerank_failed | err=%s", exc)
        reranked_candidates = []
        for item in candidates:
            copied = dict(item)
            copied.setdefault("keyword_score", 0.0)
            copied.setdefault("bm25_score", 0.0)
            copied.setdefault("exact_match_score", 0.0)
            reranked_candidates.append(copied)

    dense_scores: List[float] = []
    for item in reranked_candidates:
        has_vector_score = "vector_score" in item or "score" in item
        raw_distance = _safe_float(item.get("vector_score", item.get("score")), 1e9)
        if has_vector_score:
            item["vector_score"] = raw_distance

        dense_score = 1.0 / (1.0 + max(raw_distance, 0.0)) if has_vector_score else 0.0
        dense_scores.append(dense_score)

    keyword_scores: List[float] = []
    for item in reranked_candidates:
        item["bm25_score"] = _safe_float(item.get("bm25_score"), 0.0)
        item["exact_match_score"] = _safe_float(item.get("exact_match_score"), 0.0)
        item["keyword_score"] = _safe_float(item.get("keyword_score"), 0.0)
        keyword_scores.append(item["keyword_score"])

    normalized_vector_scores = _normalize(dense_scores)
    normalized_keyword_scores = _normalize(keyword_scores)

    if _looks_definition_query(query):
        vector_weight = 0.35
        keyword_weight = 0.65
    else:
        vector_weight = 0.60
        keyword_weight = 0.40

    final_results: List[Dict[str, Any]] = []
    for item, vector_score, keyword_score in zip(
        reranked_candidates,
        normalized_vector_scores,
        normalized_keyword_scores,
    ):
        result = dict(item)
        final_score = vector_weight * vector_score + keyword_weight * keyword_score

        result["normalized_vector_score"] = float(vector_score)
        result["normalized_bm25_score"] = float(keyword_score)
        result["normalized_keyword_score"] = float(keyword_score)
        result["final_score"] = float(final_score)
        result["score"] = float(final_score)
        result["vector_weight"] = vector_weight
        result["bm25_weight"] = keyword_weight
        result["keyword_weight"] = keyword_weight
        result.setdefault("chunk_level", 3)
        result.setdefault("auto_merged", False)

        final_results.append(result)

    final_results.sort(key=lambda x: _safe_float(x.get("score"), 0.0), reverse=True)
    return final_results


def _apply_auto_merge(
    chunks: List[Dict[str, Any]],
    *,
    top_k: int,
    enable_auto_merge: bool,
) -> List[Dict[str, Any]]:
    if not enable_auto_merge:
        return chunks[:top_k]

    merged_chunks = auto_merge_chunks(chunks, top_k=top_k)
    for item in merged_chunks:
        item.setdefault("auto_merged", False)
    return merged_chunks


def hybrid_retrieve(
    query: str,
    top_k: int = settings.TOP_K,
    *,
    user_id: Optional[int] = None,
    mode: str = "hybrid",
    enable_auto_merge: bool = True,
    rag_trace: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval over L3 chunks, with optional auto-merging.

    Flow:
    1. Recall L3 chunks from vector search.
    2. Recall L3 chunks from keyword/BM25 search.
    3. Fuse dense and keyword scores.
    4. If enabled, merge multiple sibling L3 hits into their parent chunk.

    Return value remains a list of chunks for existing routers and agent tools.
    When auto-merge is enabled, the returned list is `merged_chunks`.
    """
    q = (query or "").strip()
    if not q:
        return []

    trace = ensure_rag_trace(
        rag_trace,
        original_query=q,
        retrieval_mode=mode,
    )

    cache_key = _build_search_cache_key(
        query=q,
        user_id=user_id,
        mode=mode,
        top_k=top_k,
        enable_auto_merge=enable_auto_merge,
    )

    try:
        cached = get_cache(cache_key)
    except Exception as exc:
        logger.warning("search cache_get_failed | key=%s | err=%s", cache_key, exc)
        cached = None

    if cached is not None:
        logger.info("search cache_hit | key=%s | q_len=%s | top_k=%s", cache_key, len(q), top_k)
        set_cache_hit(trace, True)
        record_merged_chunks(trace, cached if isinstance(cached, list) else [])
        return cached

    set_cache_hit(trace, False)

    logger.info(
        "search cache_miss | key=%s | q_len=%s | top_k=%s | auto_merge=%s",
        cache_key,
        len(q),
        top_k,
        enable_auto_merge,
    )

    candidate_k = max(top_k * settings.RECALL_MULTIPLIER, top_k)

    # Important: first-stage recall must stay at L3. Do not merge before scoring
    # or rerank candidates will receive parent text too early.
    vector_start = now_ms()
    vector_results = retrieve_chunks(q, candidate_k, auto_merge=False) or []
    record_timing(trace, "vector_recall_ms", elapsed_ms(vector_start))

    try:
        keyword_start = now_ms()
        keyword_results = _keyword_recall(q, candidate_k)
        record_timing(trace, "keyword_recall_ms", elapsed_ms(keyword_start))
    except Exception as exc:
        logger.warning("keyword_recall_failed | err=%s", exc)
        record_timing(trace, "keyword_recall_ms", elapsed_ms(keyword_start))
        keyword_results = []

    candidates = _merge_candidates(vector_results, keyword_results)
    if not candidates:
        return []

    fusion_start = now_ms()
    scored_l3_chunks = _fuse_scores(q, candidates)
    record_timing(trace, "score_fusion_ms", elapsed_ms(fusion_start))
    record_initial_chunks(trace, scored_l3_chunks)

    merge_start = now_ms()
    merged_chunks = _apply_auto_merge(
        scored_l3_chunks,
        top_k=top_k,
        enable_auto_merge=enable_auto_merge,
    )
    record_timing(trace, "auto_merge_ms", elapsed_ms(merge_start))
    record_merged_chunks(trace, merged_chunks)
    record_auto_merge_steps(
        trace,
        before_chunks=scored_l3_chunks,
        after_chunks=merged_chunks,
    )

    try:
        preview = [
            {
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
                "chunk_level": item.get("chunk_level"),
                "score": item.get("score"),
                "auto_merged": item.get("auto_merged", False),
                "merged_child_count": item.get("merged_child_count"),
                "sources": item.get("retrieval_sources"),
            }
            for item in merged_chunks[:3]
        ]
        logger.info("hybrid preview | query=%s | top_results=%s", q, preview)
    except Exception:
        pass

    try:
        set_cache(cache_key, merged_chunks)
    except Exception as exc:
        logger.warning("search cache_set_failed | key=%s | err=%s", cache_key, exc)

    return merged_chunks
