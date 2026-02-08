# scripts/test_index_pipeline.py
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore
from app.services.indexing_service import index_document_chunks

# 这里假设你 Day7 有这个函数
from app.services.text_processing import process_text

def main():
    document_id = 1
    raw_text = (
        "深度学习是一种机器学习方法，通常使用神经网络。\n\n"
        "关键词搜索依赖词面匹配，语义检索依赖向量相似。\n\n"
        "今天天气不错，适合散步。"
    )

    chunks = process_text(raw_text, chunk_size=200, overlap=50)

    embedder = EmbeddingService()
    store = VectorStore()

    index_document_chunks(
        document_id=document_id,
        chunks=chunks,
        embedder=embedder,
        store=store,
    )

    query = "语义检索是什么？"
    qvec = embedder.embed_query(query)
    result = store.search(qvec, k=5)

    print("Query:", query)
    for i, doc in enumerate(result["documents"][0]):
        dist = result["distances"][0][i]
        meta = result["metadatas"][0][i]
        print(f"{i+1}. dist={dist:.4f} meta={meta} doc={doc}")

if __name__ == "__main__":
    main()
