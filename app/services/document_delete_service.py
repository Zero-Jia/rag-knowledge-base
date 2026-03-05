import os
from sqlalchemy.orm import Session

from app.exceptions import AppError
from app.models.document import Document
from app.services.vector_store import VectorStore


def delete_document_full(db: Session, document_id: int, user_id: int):
    """
    删除 document：
    1 删除磁盘文件
    2 删除 chroma embeddings
    3 删除数据库记录
    """

    doc = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not doc:
        raise AppError(
            code="DOCUMENT_NOT_FOUND",
            message="Document not found",
            status_code=404,
        )

    if doc.user_id != user_id:
        raise AppError(
            code="DOCUMENT_FORBIDDEN",
            message="No permission to delete this document",
            status_code=403,
        )

    # -------------------------
    # 1 删除磁盘文件
    # -------------------------
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception as e:
            raise AppError(
                code="FILE_DELETE_FAILED",
                message="Failed to delete file",
                status_code=500,
                details=str(e),
            )

    # -------------------------
    # 2 删除 Chroma embeddings
    # -------------------------
    try:
        store = VectorStore()

        store.collection.delete(
            where={"document_id": document_id}
        )

    except Exception as e:
        raise AppError(
            code="VECTOR_DELETE_FAILED",
            message="Failed to delete vectors",
            status_code=500,
            details=str(e),
        )

    # -------------------------
    # 3 删除数据库
    # -------------------------
    try:
        db.delete(doc)
        db.commit()
    except Exception as e:
        db.rollback()
        raise AppError(
            code="DOCUMENT_DELETE_FAILED",
            message="Failed to delete document",
            status_code=500,
            details=str(e),
        )

    return True