from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import SessionLocal
from app.models.document import Document, DocumentStatus
from app.models.document_job import DocumentJobStage
from app.models.parent_chunk import ParentChunk
from app.services.document_parser import parse_document
from app.services.document_job_service import (
    ensure_document_job,
    mark_job_done,
    mark_stage_done,
    mark_stage_failed,
    mark_stage_processing,
)
from app.services.embedding_service import EmbeddingService
from app.services.text_processing import HierarchicalChunk, process_text, process_text_hierarchy
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


def _sanitize_index_payload(
    chunks: List[str],
    metadatas: Optional[List[Dict[str, Any]]] = None,
    ids: Optional[List[str]] = None,
) -> Tuple[List[str], Optional[List[Dict[str, Any]]], Optional[List[str]]]:
    cleaned_chunks: List[str] = []
    cleaned_metadatas: List[Dict[str, Any]] = []
    cleaned_ids: List[str] = []
    max_chars = getattr(settings, "CHUNK_SIZE", 500) * 4

    for idx, chunk in enumerate(chunks or []):
        if not isinstance(chunk, str):
            continue
        text = chunk.strip()
        if not text:
            continue
        if len(text) > max_chars:
            text = text[:max_chars]
        cleaned_chunks.append(text)
        if metadatas is not None:
            cleaned_metadatas.append(dict(metadatas[idx]))
        if ids is not None:
            cleaned_ids.append(ids[idx])

    return (
        cleaned_chunks,
        cleaned_metadatas if metadatas is not None else None,
        cleaned_ids if ids is not None else None,
    )


def _parent_chunk_row(chunk: HierarchicalChunk, *, document_id: int, user_id: int) -> ParentChunk:
    return ParentChunk(
        user_id=user_id,
        document_id=document_id,
        chunk_id=chunk.chunk_id,
        parent_chunk_id=chunk.parent_chunk_id,
        root_chunk_id=chunk.root_chunk_id,
        chunk_level=chunk.chunk_level,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        metadata_json=dict(chunk.metadata or {}),
    )


def _replace_parent_chunks(
    db: Session,
    *,
    document_id: int,
    user_id: int,
    parent_chunks: List[HierarchicalChunk],
) -> None:
    """
    Replace SQL parent chunks for a document.

    Do not commit here. The caller owns the indexing transaction so document
    status and parent chunk rows move together.
    """
    db.query(ParentChunk).filter(ParentChunk.document_id == document_id).delete(
        synchronize_session=False
    )
    if parent_chunks:
        db.add_all(
            [
                _parent_chunk_row(chunk, document_id=document_id, user_id=user_id)
                for chunk in parent_chunks
            ]
        )
    db.flush()


def index_document_chunks(
    document_id: int,
    chunks: List[str],
    embedder: EmbeddingService,
    store: VectorStore,
    metadatas: Optional[List[Dict[str, Any]]] = None,
    ids: Optional[List[str]] = None,
) -> None:
    if not chunks:
        logger.warning("No valid chunks to embed | doc_id=%s", document_id)
        return
    if metadatas is not None and len(metadatas) != len(chunks):
        raise ValueError("chunks / metadatas length must match")
    if ids is not None and len(ids) != len(chunks):
        raise ValueError("chunks / ids length must match")

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

    if metadatas is None:
        metadatas = [{"document_id": document_id, "chunk_index": i} for i in range(len(chunks))]
    if ids is None:
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
        job = None

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
        job = ensure_document_job(db, document_id=doc.id, user_id=doc.user_id)
        db.commit()

        # 解析文档
        t0 = time.time()
        mark_stage_processing(
            db,
            job=job,
            stage=DocumentJobStage.PARSE,
            details={
                "file_path": doc.file_path,
                "content_type": doc.content_type,
            },
        )
        db.commit()
        raw_text = parse_document(doc.file_path, doc.content_type)
        t1 = time.time()

        if not raw_text or not str(raw_text).strip():
            logger.warning("Parsed empty text | doc_id=%s", document_id)
            doc.status = DocumentStatus.FAILED
            mark_stage_failed(
                db,
                job=job,
                stage=DocumentJobStage.PARSE,
                error_message="Parsed empty text",
                error_code="PARSED_EMPTY_TEXT",
            )
            db.commit()
            return

        mark_stage_done(
            db,
            job=job,
            stage=DocumentJobStage.PARSE,
            details={
                "text_length": len(raw_text),
                "parse_seconds": round(t1 - t0, 3),
            },
        )
        db.commit()

        embedder = get_embedder()
        store = get_store()

        try:
            store.delete(where={"document_id": doc.id})
        except Exception:
            logger.warning("Failed to cleanup old vectors | doc_id=%s", doc.id, exc_info=True)

        # chunk
        t2_start = time.time()
        leaf_metadatas: Optional[List[Dict[str, Any]]] = None
        leaf_ids: Optional[List[str]] = None

        if settings.HIERARCHICAL_CHUNKING_ENABLED:
            hierarchy = process_text_hierarchy(
                raw_text,
                document_id=doc.id,
                user_id=doc.user_id,
            )
            mark_stage_processing(
                db,
                job=job,
                stage=DocumentJobStage.PARENT_STORE,
                details={
                    "parent_chunks": len(hierarchy.parent_chunks),
                    "leaf_chunks": len(hierarchy.leaf_chunks),
                },
            )
            _replace_parent_chunks(
                db,
                document_id=doc.id,
                user_id=doc.user_id,
                parent_chunks=hierarchy.parent_chunks,
            )
            mark_stage_done(
                db,
                job=job,
                stage=DocumentJobStage.PARENT_STORE,
                details={
                    "parent_chunks": len(hierarchy.parent_chunks),
                    "leaf_chunks": len(hierarchy.leaf_chunks),
                },
            )
            chunks_raw = [chunk.text for chunk in hierarchy.leaf_chunks]
            leaf_metadatas = [dict(chunk.metadata) for chunk in hierarchy.leaf_chunks]
            leaf_ids = [chunk.chunk_id for chunk in hierarchy.leaf_chunks]
        else:
            mark_stage_processing(
                db,
                job=job,
                stage=DocumentJobStage.PARENT_STORE,
                details={"hierarchical_chunking": False},
            )
            db.query(ParentChunk).filter(ParentChunk.document_id == doc.id).delete(
                synchronize_session=False
            )
            db.flush()
            mark_stage_done(
                db,
                job=job,
                stage=DocumentJobStage.PARENT_STORE,
                details={
                    "hierarchical_chunking": False,
                    "parent_chunks": 0,
                },
            )
            chunks_raw = process_text(raw_text)
        t2 = time.time()

        # ✅ 关键：清洗 chunks，确保都是可 encode 的 string
        if leaf_metadatas is not None or leaf_ids is not None:
            chunks, leaf_metadatas, leaf_ids = _sanitize_index_payload(
                chunks_raw,
                metadatas=leaf_metadatas,
                ids=leaf_ids,
            )
        else:
            chunks = _sanitize_chunks(chunks_raw)

        if not chunks:
            logger.warning(
                "No valid chunks after sanitize | doc_id=%s | raw_chunks=%s",
                document_id,
                0 if chunks_raw is None else len(chunks_raw),
            )
            doc.status = DocumentStatus.FAILED
            mark_stage_failed(
                db,
                job=job,
                stage=DocumentJobStage.VECTOR_STORE,
                error_message="No valid chunks after sanitize",
                error_code="NO_VALID_CHUNKS",
                details={
                    "raw_chunks": 0 if chunks_raw is None else len(chunks_raw),
                },
            )
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
            if leaf_metadatas is not None:
                leaf_metadatas = leaf_metadatas[: settings.MAX_CHUNKS]
            if leaf_ids is not None:
                leaf_ids = leaf_ids[: settings.MAX_CHUNKS]

        # embeddings + vector store
        t3 = time.time()
        mark_stage_processing(
            db,
            job=job,
            stage=DocumentJobStage.VECTOR_STORE,
            details={
                "chunks": len(chunks),
                "embedding_batch_size": settings.EMBED_BATCH_SIZE,
            },
        )
        db.commit()
        index_document_chunks(
            document_id=doc.id,
            chunks=chunks,
            embedder=embedder,
            store=store,
            metadatas=leaf_metadatas,
            ids=leaf_ids,
        )
        t4 = time.time()
        mark_stage_done(
            db,
            job=job,
            stage=DocumentJobStage.VECTOR_STORE,
            details={
                "chunks": len(chunks),
                "embedding_batch_size": settings.EMBED_BATCH_SIZE,
                "vector_store_seconds": round(t4 - t3, 3),
            },
        )

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
        mark_job_done(db, job=job)
        db.commit()

    except Exception:
        try:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = DocumentStatus.FAILED
                if "job" in locals() and job is not None:
                    stage = job.current_stage or DocumentJobStage.VECTOR_STORE
                    mark_stage_failed(
                        db,
                        job=job,
                        stage=stage,
                        error_message="index_document failed",
                        error_code="INDEX_DOCUMENT_FAILED",
                    )
                db.commit()
        finally:
            logger.exception("index_document failed: document_id=%s", document_id)

    finally:
        db.close()
