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


def index_document_chunks(
    document_id: int,
    chunks: List[str],
    embedder: EmbeddingService,
    store: VectorStore,
) -> None:
    if not chunks:
        return

    embeddings = embedder.embed_texts(chunks, batch_size=settings.EMBED_BATCH_SIZE)
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
        if not doc:
            return

        doc.status = DocumentStatus.PROCESSING
        db.commit()

        t0 = time.time()
        raw_text = parse_document(doc.file_path, doc.content_type)
        t1 = time.time()

        chunks = process_text(raw_text)
        t2 = time.time()

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

        t3 = time.time()
        index_document_chunks(
            document_id=doc.id,
            chunks=chunks,
            embedder=embedder,
            store=store,
        )
        t4 = time.time()

        logger.info(
            "Indexing performance | doc_id=%s | chunks=%s | parse=%.2fs | chunking=%.2fs | "
            "embed+store=%.2fs | total=%.2fs",
            document_id,
            len(chunks),
            (t1 - t0),
            (t2 - t1),
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
