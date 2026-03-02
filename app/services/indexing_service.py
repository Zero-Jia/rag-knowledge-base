from __future__ import annotations

import logging
import time
from typing import List

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document import Document, DocumentStatus
from app.services.document_parser import parse_document
from app.services.text_processing import process_text
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

# =========================
# Day26 工程参数（可调）
# =========================
MAX_CHUNKS = 500
EMBED_BATCH_SIZE = 32

# ✅ Day26：模型/向量库实例尽量复用（避免每次后台任务都重新加载模型）
# 注意：如果你未来做多进程/多 worker，每个进程仍会各自初始化一次，这是正常的。
_embedder_singleton: EmbeddingService | None = None
_store_singleton: VectorStore | None = None


def get_embedder() -> EmbeddingService:
    global _embedder_singleton
    if _embedder_singleton is None:
        _embedder_singleton = EmbeddingService()
        logger.info("EmbeddingService initialized (singleton)")
    return _embedder_singleton


def get_store() -> VectorStore:
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = VectorStore()
        logger.info("VectorStore initialized (singleton)")
    return _store_singleton


def index_document_chunks(
    document_id: int,
    chunks: List[str],
    embedder: EmbeddingService,
    store: VectorStore,
) -> None:
    """
    把某个 document 的 chunk 列表：
    - 批量 embed 成向量
    - 写入向量库（带 metadata 和唯一 ids）
    """
    if not chunks:
        return

    # ✅ Day26：批量 embedding + 显式 batch_size
    embeddings = embedder.embed_texts(chunks, batch_size=EMBED_BATCH_SIZE)

    metadatas = [{"document_id": document_id, "chunk_index": i} for i in range(len(chunks))]
    ids = [f"doc{document_id}_chunk{i}" for i in range(len(chunks))]

    store.add_texts(
        texts=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )


def index_document_pipeline(document_id: int) -> None:
    """
    后台任务：文档 -> parse -> chunk -> embedding -> 向量库
    并维护 Document.status 状态机
    """
    db: Session = SessionLocal()

    start_total = time.time()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return

        # 1) 状态：PROCESSING
        doc.status = DocumentStatus.PROCESSING
        db.commit()

        # 2) parse
        t0 = time.time()
        raw_text = parse_document(doc.file_path, doc.content_type)
        t1 = time.time()

        # 3) chunk
        chunks = process_text(raw_text)
        t2 = time.time()

        # ✅ Day26：大文档保护（先截断，避免卡死）
        original_chunks = len(chunks)
        if original_chunks > MAX_CHUNKS:
            logger.warning(
                "Document too large, truncating | doc_id=%s | chunks=%s > %s",
                document_id, original_chunks, MAX_CHUNKS
            )
            chunks = chunks[:MAX_CHUNKS]

        # 4) embedding + store（复用单例）
        embedder = get_embedder()
        store = get_store()

        t3 = time.time()
        index_document_chunks(
            document_id=doc.id,
            chunks=chunks,
            embedder=embedder,
            store=store,
        )
        t4 = time.time()

        # ✅ Day26：性能日志（面试加分）
        logger.info(
            "Indexing performance | doc_id=%s | chunks=%s | "
            "parse=%.2fs | chunking=%.2fs | embed+store=%.2fs | total=%.2fs",
            document_id,
            len(chunks),
            (t1 - t0),
            (t2 - t1),
            (t4 - t3),
            (t4 - start_total),
        )

        # 5) 状态：DONE
        doc.status = DocumentStatus.DONE
        db.commit()

    except Exception:
        # 标记失败（不要把异常抛到请求线程，让后台任务安静失败即可）
        try:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = DocumentStatus.FAILED
                db.commit()
        finally:
            logger.exception("index_document failed: document_id=%s", document_id)

    finally:
        db.close()