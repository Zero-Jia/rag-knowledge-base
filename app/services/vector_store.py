# 实现 VectorStore（ChromaDB：持久化 + 检索）
from __future__ import annotations
from typing import Any,Dict,List,Optional
import chromadb
from chromadb.config import Settings

class VectorStore:
    """
    负责：向量的持久化存储 + 相似度检索
    """
    def __init__(
        self,
        persist_dir:str = "storage/chroma",
        collection_name:str = "document_chunks",
    ):
        self.client = chromadb.Client(
            Settings(
                persist_directory = persist_dir,
                anonymized_telemetry = False,
            )
        )
        self.collection = self.client.get_or_create_collection(name=collection_name)
    
    def add_texts(
        self,
        texts:List[str],
        embeddings:List[List[float]],
        metadatas:Optional[List[Dict[str,Any]]],
        ids:Optional[List[str]] = None,
    )-> None:
        if len(texts)!=len(embeddings) or len(texts) != len(metadatas):
            raise ValueError("texts / embeddings / metadatas 长度必须一致")
        
        if ids is None:
            # ⚠️ 真实项目里不建议用 chunk_0, chunk_1（不同文档会撞 id）
            # 下面只是为了 Day 8 本地验证先跑起来
            ids = [f"chunk_{i}" for i in range(len(texts))]
        
        self.collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
    
    def search(self,query_embedding:List[float],k:int = 5)->Dict[str,Any]:
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )