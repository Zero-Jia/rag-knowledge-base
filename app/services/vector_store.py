from __future__ import annotations

from typing import Any, Dict, List, Optional
import chromadb
import os
import uuid

from app.core.config import settings


class VectorStore:
    """
    负责：向量持久化存储 + 相似度检索
    """

    def __init__(
        self,
        persist_dir: str = settings.SEMANTIC_CACHE_PERSIST_DIR,
        collection_name: str = "document_chunks",
        collection_metadata: Optional[Dict[str, Any]] = None,
    ):
        os.makedirs(persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_dir)

        if collection_metadata is not None:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata=collection_metadata,
            )
        else:
            self.collection = self.client.get_or_create_collection(name=collection_name)

    def add_texts(
        self,
        texts: List[str],
        embeddings: List[List[float]],
        metadatas: Optional[List[Dict[str, Any]]],
        ids: Optional[List[str]] = None,
    ) -> None:
        if metadatas is None:
            metadatas = [{} for _ in texts]

        if len(texts) != len(embeddings) or len(texts) != len(metadatas):
            raise ValueError("texts / embeddings / metadatas 长度必须一致")

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]

        self.collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )

    def search(
        self,
        query_embedding: List[float],
        k: int = settings.TOP_K,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        include = include or ["documents", "metadatas", "distances"]
        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": k,
            "include": include,
        }
        if where:
            kwargs["where"] = where

        return self.collection.query(**kwargs)

    def delete(self, *, ids: Optional[List[str]] = None, where: Optional[Dict[str, Any]] = None) -> None:
        kwargs: Dict[str, Any] = {}
        if ids:
            kwargs["ids"] = ids
        if where:
            kwargs["where"] = where
        if not kwargs:
            return
        self.collection.delete(**kwargs)