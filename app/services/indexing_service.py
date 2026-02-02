from __future__ import annotations

from typing import List

from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore


def index_document_chunks(
    document_id: int,
    chunks: List[str],
    embedder: EmbeddingService,
    store: VectorStore,
) -> None:
    """
    把某个 document 的 chunk 列表：
    - embed 成向量
    - 写入向量库（带 metadata 和唯一 ids）
    """
    if not chunks:
        return

    embeddings = embedder.embed_texts(chunks)
    metadatas = [{"document_id": document_id, "chunk_index": i} for i in range(len(chunks))]
    ids = [f"doc{document_id}_chunk{i}" for i in range(len(chunks))]

    store.add_texts(
        texts=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )
