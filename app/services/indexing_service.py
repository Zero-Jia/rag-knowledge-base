from __future__ import annotations

import logging
import time
from typing import List

from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import SessionLocal
from app.models.document import Document, DocumentStatus
from app.services.document_parser import parse_document
from app.services.embedding_service import EmbeddingService
from app.services.text_processing import process_text
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

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


def _sanitize_chunks(chunks: List[object]) -> List[str]:
    """
    ✅ 关键修复：SentenceTransformer 只接受 List[str]
    - 去掉 None / 非 str
    - 去掉空串/全空白
    - 可选：对超长 chunk 截断（避免 tokenizer 异常或极慢）
    """
    cleaned: List[str] = []
    max_chars = getattr(settings, "CHUNK_SIZE", 500)  # 没有就默认 500

    for c in chunks or []:
        if not isinstance(c, str):
            continue
        s = c.strip()
        if not s:
            continue
        # 可选：截断超长 chunk（防止极端 PDF 解析出巨长段）
        if len(s) > max_chars * 4:
            s = s[: max_chars * 4]
        cleaned.append(s)

    return cleaned


def index_document_chunks(
    document_id: int,
    chunks: List[str],
    embedder: EmbeddingService,
    store: VectorStore,
) -> None:
    if not chunks:
        logger.warning("No valid chunks to embed | doc_id=%s", document_id)
        return

    try:
        embeddings = embedder.embed_texts(
            chunks,
            batch_size=settings.EMBED_BATCH_SIZE,
        )
    except Exception as e:
        # 打印一些上下文，便于定位到底是哪些 chunk 有问题
        preview = []
        for x in chunks[:3]:
            preview.append({"type": type(x).__name__, "len": len(x)})
        logger.error(
            "Embedding failed | doc_id=%s | chunks=%s | preview=%s | err=%s",
            document_id,
            len(chunks),
            preview,
            e,
        )
        raise

    metadatas = [{"document_id": document_id, "chunk_index": i} for i in range(len(chunks))]
    ids = [f"doc{document_id}_chunk{i}" for i in range(len(chunks))]

    store.add_texts(
        texts=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )


def index_document_pipeline(document_id: int) -> None:
    db: Session = SessionLocal()
    start_total = time.time()

    try:
        doc = db.query(Document).filter(Document.id == document_id).first()

        # 如果 document 已删除
        if not doc:
            logger.warning("Document not found, stop indexing | doc_id=%s", document_id)
            return

        # 如果 document 已经失败
        if doc.status == DocumentStatus.FAILED:
            logger.warning("Document already failed, stop indexing | doc_id=%s", document_id)
            return

        # 标记为 processing
        doc.status = DocumentStatus.PROCESSING
        db.commit()

        # 解析文档
        t0 = time.time()
        raw_text = parse_document(doc.file_path, doc.content_type)
        t1 = time.time()

        if not raw_text or not str(raw_text).strip():
            logger.warning("Parsed empty text | doc_id=%s", document_id)
            doc.status = DocumentStatus.FAILED
            db.commit()
            return

        # chunk
        t2_start = time.time()
        chunks_raw = process_text(raw_text)
        t2 = time.time()

        # ✅ 关键：清洗 chunks，确保都是可 encode 的 string
        chunks = _sanitize_chunks(chunks_raw)

        if not chunks:
            logger.warning(
                "No valid chunks after sanitize | doc_id=%s | raw_chunks=%s",
                document_id,
                0 if chunks_raw is None else len(chunks_raw),
            )
            doc.status = DocumentStatus.FAILED
            db.commit()
            return

        # 限制最大 chunks 数
        original_chunks = len(chunks)
        if original_chunks > settings.MAX_CHUNKS:
            logger.warning(
                "Document too large, truncating | doc_id=%s | chunks=%s > %s",
                document_id,
                original_chunks,
                settings.MAX_CHUNKS,
            )
            chunks = chunks[: settings.MAX_CHUNKS]

        embedder = get_embedder()
        store = get_store()

        # embeddings + vector store
        t3 = time.time()
        index_document_chunks(
            document_id=doc.id,
            chunks=chunks,
            embedder=embedder,
            store=store,
        )
        t4 = time.time()

        logger.info(
            "Indexing performance | doc_id=%s | chunks=%s | parse=%.2fs | chunking=%.2fs | embed+store=%.2fs | total=%.2fs",
            document_id,
            len(chunks),
            (t1 - t0),
            (t2 - t2_start),
            (t4 - t3),
            (t4 - start_total),
        )

        doc.status = DocumentStatus.DONE
        db.commit()

    except Exception:
        try:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = DocumentStatus.FAILED
                db.commit()
        finally:
            logger.exception("index_document failed: document_id=%s", document_id)

    finally:
        db.close()