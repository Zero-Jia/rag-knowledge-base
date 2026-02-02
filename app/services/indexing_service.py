from __future__ import annotations

import logging
from typing import List

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document import Document,DocumentStatus
from app.services.document_parser import parse_document
from app.services.text_processing import process_text
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

def index_document_chunks(
    document_id: int,
    chunks: List[str],
    embedder: EmbeddingService,
    store: VectorStore,
) -> None:
    """
    把某个 document 的 chunk 列表：
    - embed 成向量
    - 写入向量库（带 metadata 和唯一 ids）
    """
    if not chunks:
        return

    embeddings = embedder.embed_texts(chunks)
    metadatas = [{"document_id": document_id, "chunk_index": i} for i in range(len(chunks))]
    ids = [f"doc{document_id}_chunk{i}" for i in range(len(chunks))]

    store.add_texts(
        texts=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
    )

def index_document_pipeline(document_id:int)->None:
    """
    Day9 新增：后台任务的“总编排”
    文档 -> parse -> chunk -> embedding -> 向量库
    并维护 Document.status 状态机
    """   
    db:Session = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return 
        
        # 1) 状态：PROCESSING
        doc.status = DocumentStatus.PROCESSING
        db.commit()
        # 2) parse -> chunk
        raw_text = parse_document(doc.file_path,doc.content_type)
        chunks = process_text(raw_text)
        # 3) embedding + store（复用 Day8 的函数）
        embedder = EmbeddingService()
        store = VectorStore()
        index_document_chunks(document_id=doc.id,chunks=chunks,embedder=embedder,store=store)
        # 4) 状态：DONE
        doc.status = DocumentStatus.DONE
        db.commit()
    except Exception:
        # 标记失败（不要把异常抛到请求线程，让后台任务安静失败即可）
        try:
            doc =db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = DocumentStatus.FAILED
                db.commit()
        finally:
            logger.exception("index_document failed: document_id=%s", document_id)
    finally:
        db.close()