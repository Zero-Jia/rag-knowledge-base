# 实现 VectorStore（ChromaDB：持久化 + 检索）
from __future__ import annotations
from typing import Any,Dict,List,Optional
import chromadb
import os
import uuid

class VectorStore:
    """
    负责：向量的持久化存储 + 相似度检索
    """
    def __init__(
        self,
        persist_dir:str = "storage/chroma",
        collection_name:str = "document_chunks",
    ):
        os.makedirs(persist_dir,exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(name=collection_name)
    
    def add_texts(
        self,
        texts:List[str],
        embeddings:List[List[float]],
        metadatas:Optional[List[Dict[str,Any]]],
        ids:Optional[List[str]] = None,
    )-> None:
        # metadatas 允许 None，就给默认空 dict
        if metadatas is None:
            metadatas = [{} for _ in texts]

        if len(texts)!=len(embeddings) or len(texts) != len(metadatas):
            raise ValueError("texts / embeddings / metadatas 长度必须一致")
        
        if ids is None:
            # ✅ 防撞：uuid
            ids = [str(uuid.uuid4()) for _ in texts]
        
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