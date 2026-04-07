from __future__ import annotations

import logging
import hashlib
import re
import time
from typing import Any, Dict, Optional

from app.core.config import settings
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

logger = logging.getLogger("rag.semantic_cache")

_embedder_singleton: EmbeddingService | None = None
_semantic_store_singleton: VectorStore | None = None


def get_semantic_cache_embedder() -> EmbeddingService:
    global _embedder_singleton
    if _embedder_singleton is None:
        _embedder_singleton = EmbeddingService()
        logger.info("Semantic cache embedder initialized")
    return _embedder_singleton


def get_semantic_cache_store() -> VectorStore:
    global _semantic_store_singleton
    if _semantic_store_singleton is None:
        _semantic_store_singleton = VectorStore(
            persist_dir=settings.SEMANTIC_CACHE_PERSIST_DIR,
            collection_name=settings.SEMANTIC_CACHE_COLLECTION_NAME,
            collection_metadata={"hnsw:space": "cosine"},
        )
        logger.info("Semantic cache vector store initialized")
    return _semantic_store_singleton


def normalize_question(question: str) -> str:
    """
    轻量标准化：
    - strip
    - lower
    - 合并多空格
    - 去掉首尾常见标点带来的噪音
    """
    q = (question or "").strip().lower()
    q = re.sub(r"\s+", " ", q)
    q = q.strip(" \n\t\r,，。！？!?；;：:")
    return q


def should_use_semantic_cache(question: str) -> bool:
    if not settings.SEMANTIC_CACHE_ENABLED:
        return False

    q = normalize_question(question)
    q_len = len(q)

    if q_len < settings.SEMANTIC_CACHE_MIN_QUESTION_LENGTH:
        return False

    if q_len > settings.SEMANTIC_CACHE_MAX_QUESTION_LENGTH:
        return False

    return True


def _build_semantic_cache_id(
    *,
    question: str,
    user_id: Optional[int],
    retrieval_mode: Optional[str],
) -> str:
    raw = f"user={user_id}|mode={retrieval_mode}|q={normalize_question(question)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _distance_to_similarity(distance: float) -> float:
    """
    semantic_cache collection 使用 cosine 空间时，
    Chroma 返回的是 distance，通常可近似转成 similarity = 1 - distance。
    再裁剪到 [0, 1]。
    """
    sim = 1.0 - float(distance)
    if sim < 0.0:
        sim = 0.0
    if sim > 1.0:
        sim = 1.0
    return sim


def _build_where_filter(
    *,
    user_id: Optional[int],
    retrieval_mode: Optional[str],
) -> Optional[Dict[str, Any]]:
    conditions = []

    if settings.SEMANTIC_CACHE_REQUIRE_SAME_USER and user_id is not None:
        conditions.append({"user_id": int(user_id)})

    if settings.SEMANTIC_CACHE_REQUIRE_SAME_MODE and retrieval_mode:
        conditions.append({"retrieval_mode": str(retrieval_mode)})

    if not conditions:
        return None

    if len(conditions) == 1:
        return conditions[0]

    return {"$and": conditions}


def find_semantic_cached_answer(
    question: str,
    *,
    user_id: Optional[int] = None,
    retrieval_mode: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not should_use_semantic_cache(question):
        return None

    q = normalize_question(question)

    try:
        embedder = get_semantic_cache_embedder()
        store = get_semantic_cache_store()

        query_vec = embedder.embed_query(q)
        where = _build_where_filter(user_id=user_id, retrieval_mode=retrieval_mode)

        results = store.search(
            query_embedding=query_vec,
            k=settings.SEMANTIC_CACHE_TOP_K,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not documents:
            return None

        best_doc = documents[0]
        best_meta = metadatas[0] or {}
        best_distance = float(distances[0]) if distances else 1.0
        best_similarity = _distance_to_similarity(best_distance)

        logger.info(
            "semantic cache search | q_len=%s | similarity=%.4f | threshold=%.4f",
            len(q),
            best_similarity,
            settings.SEMANTIC_CACHE_THRESHOLD,
        )

        if best_similarity < settings.SEMANTIC_CACHE_THRESHOLD:
            return None

        return {
            "question": question,
            "answer": best_meta.get("answer", ""),
            "chunks": [],
            "cache_hit": True,
            "cache_type": "semantic",
            "semantic_similarity": best_similarity,
            "matched_cached_question": best_doc,
        }

    except Exception as e:
        logger.warning(f"semantic cache find failed | err={e}")
        return None


def save_semantic_cache(
    question: str,
    answer: str,
    *,
    user_id: Optional[int] = None,
    retrieval_mode: Optional[str] = None,
) -> None:
    if not should_use_semantic_cache(question):
        return

    q = normalize_question(question)
    ans = (answer or "").strip()
    if not ans:
        return

    try:
        embedder = get_semantic_cache_embedder()
        store = get_semantic_cache_store()

        q_vec = embedder.embed_query(q)

        doc_id = _build_semantic_cache_id(
            question=q,
            user_id=user_id,
            retrieval_mode=retrieval_mode,
        )

        metadata = {
            "user_id": int(user_id) if user_id is not None else -1,
            "retrieval_mode": retrieval_mode or "",
            "answer": ans,
            "created_at": int(time.time()),
        }

        # 同 id 重复写入时，先删再加，避免重复 id 冲突
        store.delete(ids=[doc_id])

        store.add_texts(
            texts=[q],
            embeddings=[q_vec],
            metadatas=[metadata],
            ids=[doc_id],
        )

        logger.info(
            "semantic cache saved | q_len=%s | user_id=%s | mode=%s",
            len(q),
            user_id,
            retrieval_mode,
        )

    except Exception as e:
        logger.warning(f"semantic cache save failed | err={e}")