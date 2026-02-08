# scripts/test_index_resnet50.py
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore
from app.services.indexing_service import index_document_chunks
from app.services.text_processing import process_text


def main():
    # 模拟一个新文档
    document_id = 2

    raw_text = (
        "ResNet-50 是一种经典的深度卷积神经网络结构，"
        "由 Microsoft Research 在 2015 年提出。"
        "ResNet 的核心思想是残差连接（Residual Connection），"
        "通过引入 shortcut 结构缓解深层网络中的梯度消失问题。\n\n"

        "ResNet-50 包含 50 层可训练网络层，"
        "在 ImageNet 图像分类任务上取得了显著效果，"
        "并成为许多计算机视觉模型的 backbone。\n\n"

        "在工程实践中，ResNet-50 常被用于特征提取、"
        "迁移学习以及作为目标检测和分割模型的基础网络。"
    )

    # 切 chunk（刻意让 ResNet-50 成为明显 token）
    chunks = process_text(
        raw_text,
        chunk_size=200,
        overlap=50,
    )

    embedder = EmbeddingService()
    store = VectorStore()

    # 入库
    index_document_chunks(
        document_id=document_id,
        chunks=chunks,
        embedder=embedder,
        store=store,
    )

    # ========= 对比测试 =========
    test_queries = [
        "ResNet-50 是什么？",
        "残差连接有什么作用？",
        "ImageNet 分类模型",
    ]

    for query in test_queries:
        qvec = embedder.embed_query(query)
        result = store.search(qvec, k=5)

        print("\n==============================")
        print("Query:", query)

        for i, doc in enumerate(result["documents"][0]):
            dist = result["distances"][0][i]
            meta = result["metadatas"][0][i]
            print(f"{i+1}. dist={dist:.4f} doc_id={meta['document_id']}")
            print(doc[:120], "...")
    

if __name__ == "__main__":
    main()
