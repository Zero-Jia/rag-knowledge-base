# 实现 Retrieval Service（核心：把 raw results 变成 chunks 列表）
# Query embedding 和 document embedding 必须同源（同一个模型/同一个向量空间）
from typing import List,Dict,Any

from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

def retrieve_chunks(query:str,top_k:int = 5)-> List[Dict[str,Any]]:
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
        chunks.append(
            {
                "text": text,
                "document_id": int(meta.get("document_id")),
                "score": float(dist),
            }
        )
    return chunks