# scripts/test_vector_search.py
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

def main():
    texts = [
        "机器学习是人工智能的一个分支",
        "今天的天气很好",
        "深度学习依赖神经网络",
    ]

    embedder = EmbeddingService()
    vectors = embedder.embed_texts(texts)

    store = VectorStore()

    store.add_texts(
        texts=texts,
        embeddings=vectors,
        metadatas=[{"source": "test"}] * len(texts),
    )

    query = "什么是深度学习？"
    query_vec = embedder.embed_query(query)

    result = store.search(query_vec, k=3)
    print("Query:", query)
    print("Top results:")
    for i, doc in enumerate(result["documents"][0]):
        dist = result["distances"][0][i]
        meta = result["metadatas"][0][i]
        print(f"{i+1}. dist={dist:.4f} meta={meta} doc={doc}")

if __name__ == "__main__":
    main()
