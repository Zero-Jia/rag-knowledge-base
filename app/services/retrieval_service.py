# 实现 Retrieval Service（核心：把 raw results 变成 chunks 列表）
# Query embedding 和 document embedding 必须同源（同一个模型/同一个向量空间）
from typing import List,Dict,Any,Optional

from app.core.config import settings
from app.services.auto_merge_service import auto_merge_chunks
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

def _metadata_to_chunk(text: str, meta: Optional[Dict[str, Any]], score: float | None = None) -> Dict[str, Any]:
    meta = meta or {}
    chunk: Dict[str, Any] = {
        "text": text,
        "document_id": int(meta.get("document_id")) if meta.get("document_id") is not None else None,
    }
    if "chunk_index" in meta:
        chunk["chunk_index"] = int(meta.get("chunk_index"))
    for key in (
        "chunk_id",
        "chunk_level",
        "parent_chunk_id",
        "root_chunk_id",
        "sibling_index",
        "sibling_count",
        "root_child_count",
        "user_id",
    ):
        value = meta.get(key)
        if value is not None:
            chunk[key] = value
    if score is not None:
        chunk["score"] = float(score)
    return chunk


def retrieve_chunks(
    query: str,
    top_k: int = settings.TOP_K,
    *,
    auto_merge: bool = True,
) -> List[Dict[str, Any]]:
    embedder = EmbeddingService()
    store = VectorStore()

    if hasattr(embedder,"embed_query"):
        query_vec = embedder.embed_query(query)
    else:
        query_vec = embedder.embed_texts(query)

    results = store.search(query_vec,top_k)

    documents = results.get("documents",[[]])[0]
    metadatas = results.get("metadatas",[[]])[0]
    distances = results.get("distances",[[]])[0]

    chunks:List[Dict[str,Any]] = []
    for text,meta,dist in zip(documents,metadatas,distances):
        # dist 可能是“距离”，数值越小越相近
        # 先原样返回为 score，Day 11/调参时再决定要不要转换为 similarity
        chunks.append(_metadata_to_chunk(text=text, meta=meta, score=float(dist)))
    if auto_merge:
        return auto_merge_chunks(chunks, top_k=top_k)
    return chunks


def retrieve_all_chunks(limit: int | None = None) -> List[Dict[str, Any]]:
    store = VectorStore()
    payload = store.get_texts(limit=limit)

    documents = payload.get("documents", []) or []
    metadatas = payload.get("metadatas", []) or []

    chunks: List[Dict[str, Any]] = []
    for text, meta in zip(documents, metadatas):
        if not text:
            continue
        try:
            chunks.append(_metadata_to_chunk(text=text, meta=meta))
        except Exception:
            continue
    return chunks
