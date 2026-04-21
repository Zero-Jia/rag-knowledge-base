# 文件上传 router（核心）
"""
Documents Router (Frontend-facing)

Core endpoints (used by frontend):
- POST   /documents/upload
  Upload a PDF/TXT. Indexing runs asynchronously in background.
- GET    /documents
  List my uploaded documents (id/filename/type/status).
- GET    /documents/{document_id}/status
  Poll indexing status until ready (e.g. PENDING/PROCESSING/INDEXED/FAILED).
- GET    /documents/{document_id}/text
  Get parsed text preview for display/debug (first 1000 chars).

Optional / Debug endpoints:
- GET    /documents/{document_id}/chunks?chunk_size=<CHUNK_SIZE>&overlap=<CHUNK_OVERLAP>
  Preview chunking result (returns first 3 chunks + total).

Recommended frontend flow:
1) POST /documents/upload  -> get document_id
2) GET /documents/{id}/status (poll) until indexed
3) POST /search or /chat using the indexed content

Auth:
- All endpoints require Authorization: Bearer <token>
"""

import os
import shutil
from fastapi import APIRouter, UploadFile, File, Depends, Query, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.services.text_processing import process_text
from app.services.document_parser import parse_document
from app.services.indexing_service import index_document_pipeline
from app.services.document_service import get_document_by_id, list_documents
from app.services.document_delete_service import delete_document_full
from app.services.document_job_service import (
    create_document_job,
    get_latest_document_job,
    mark_stage_done,
    mark_stage_failed,
    mark_stage_processing,
    serialize_document_job,
)
from app.database import get_db
from app.models.document import Document, DocumentStatus
from app.models.document_job import DocumentJobStage
from app.security import get_current_user
from app.schemas.common import APIResponse
from app.exceptions import AppError
from app.core.config import settings

UPLOAD_ROOT = "storage/uploads"

# =========================
# Day26 Task4: 文件大小限制
# =========================
MAX_FILE_SIZE = 10 * 1024 * 1024   # 10MB
COPY_CHUNK_SIZE = 1024 * 1024      # 1MB

router = APIRouter(prefix="/documents", tags=["documents"])


def save_upload_with_limit(upload: UploadFile, dst_path: str, max_bytes: int) -> int:
    """
    把 UploadFile 保存到 dst_path，同时限制最大字节数。
    超限会删除已写入的半截文件，并抛 AppError(FILE_TOO_LARGE, 400)。
    返回实际写入大小（bytes）。
    """
    total = 0
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    try:
        with open(dst_path, "wb") as f:
            while True:
                buf = upload.file.read(COPY_CHUNK_SIZE)
                if not buf:
                    break
                total += len(buf)
                if total > max_bytes:
                    # 先关闭再删
                    f.close()
                    try:
                        os.remove(dst_path)
                    except Exception:
                        pass
                    raise AppError(
                        code="FILE_TOO_LARGE",
                        message=f"File exceeds {max_bytes // (1024 * 1024)}MB",
                        status_code=400,
                        details={"max_bytes": max_bytes, "received_bytes": total},
                    )
                f.write(buf)
    finally:
        # 保险：把文件指针复位（虽然这里保存后不会再读，但不影响）
        try:
            upload.file.seek(0)
        except Exception:
            pass

    return total


@router.get(
    "/{document_id}/text",
    summary="Get document text preview",
    description=(
        "Parse the uploaded document and return a text preview.\n\n"
        "- Auth required\n"
        "- Returns only first 1000 characters as `text_preview`\n"
        "- Useful for debugging / showing quick preview in frontend"
    ),
    response_model=APIResponse,
)
def get_document_text(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    doc = get_document_by_id(db, document_id=document_id, user_id=current_user.id)

    try:
        text = parse_document(doc.file_path, doc.content_type)
    except ValueError as e:
        raise AppError(code="UNSUPPORTED_DOCUMENT_TYPE", message=str(e), status_code=415)
    except Exception as e:
        raise AppError(code="DOCUMENT_PARSE_FAILED", message="Parse failed", status_code=500, details=str(e))

    return APIResponse(
        success=True,
        data={
            "document_id": doc.id,
            "content_type": doc.content_type,
            "text_preview": text[: settings.TEXT_PREVIEW_CHARS],
            "text_length": len(text),
        },
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get(
    "/{document_id}/chunks",
    summary="Preview chunking result",
    description=(
        "Parse the document and run chunking, then return a preview of chunks.\n\n"
        "- Auth required\n"
        "- Query params: `chunk_size` and `overlap`\n"
        "- Returns first 3 chunks in `items` and the full chunk count in `total`\n"
        "- Debug/preview endpoint (frontend usually doesn't need it in production)"
    ),
    response_model=APIResponse,
)
def get_document_chunks(
    document_id: int,
    request: Request,
    chunk_size: int = Query(
        settings.CHUNK_SIZE,
        ge=settings.CHUNK_SIZE_MIN,
        le=settings.CHUNK_SIZE_MAX,
        description="Chunk size in characters",
    ),
    overlap: int = Query(
        settings.CHUNK_OVERLAP,
        ge=settings.OVERLAP_MIN,
        le=settings.OVERLAP_MAX,
        description="Overlap size in characters",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    doc = get_document_by_id(db, document_id=document_id, user_id=current_user.id)

    try:
        raw_text = parse_document(doc.file_path, doc.content_type)
    except ValueError as e:
        raise AppError(code="UNSUPPORTED_DOCUMENT_TYPE", message=str(e), status_code=415)
    except Exception as e:
        raise AppError(code="DOCUMENT_PARSE_FAILED", message="Parse failed", status_code=500, details=str(e))

    if not raw_text or not raw_text.strip():
        return APIResponse(
            success=True,
            data={
                "document_id": doc.id,
                "chunk_size": chunk_size,
                "overlap": overlap,
                "items": [],
                "total": 0,
            },
            error=None,
            trace_id=getattr(request.state, "trace_id", None),
        )

    chunks = process_text(raw_text, chunk_size, overlap)

    return APIResponse(
        success=True,
        data={
            "document_id": doc.id,
            "chunk_size": chunk_size,
            "overlap": overlap,
            "items": chunks[:3],  # preview only
            "total": len(chunks),
        },
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.post(
    "/upload",
    summary="Upload a document",
    description=(
        "Upload a PDF/TXT document and start asynchronous indexing for RAG.\n\n"
        "- Auth required\n"
        "- Indexing runs in background task\n"
        "- Check progress via `GET /documents/{document_id}/status`"
    ),
    response_model=APIResponse,
)
def upload_document(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(..., description="PDF/TXT file"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not file.filename:
        raise AppError(code="EMPTY_FILENAME", message="Empty filename", status_code=400)

    os.makedirs(UPLOAD_ROOT, exist_ok=True)

    doc = Document(
        user_id=current_user.id,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        file_path="",
        status=DocumentStatus.PENDING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    job = create_document_job(
        db,
        document_id=doc.id,
        user_id=current_user.id,
        metadata={
            "filename": file.filename,
            "content_type": file.content_type or "application/octet-stream",
        },
    )
    mark_stage_processing(
        db,
        job=job,
        stage=DocumentJobStage.UPLOAD,
        details={"filename": file.filename},
    )
    db.commit()
    db.refresh(job)

    save_path = os.path.join(UPLOAD_ROOT, f"{doc.id}_{file.filename}")

    try:
        # ✅ Day26 Task4：保存时限制大小
        _written_size = save_upload_with_limit(file, save_path, MAX_FILE_SIZE)
        mark_stage_done(
            db,
            job=job,
            stage=DocumentJobStage.UPLOAD,
            details={
                "file_path": save_path,
                "file_size": _written_size,
            },
        )
    except AppError:
        # 建议：保存失败/超限时标记 FAILED，避免前端一直看到 pending
        doc.status = DocumentStatus.FAILED
        mark_stage_failed(
            db,
            job=job,
            stage=DocumentJobStage.UPLOAD,
            error_message="File upload failed",
            error_code="UPLOAD_FAILED",
        )
        db.commit()
        raise
    except Exception as e:
        doc.status = DocumentStatus.FAILED
        mark_stage_failed(
            db,
            job=job,
            stage=DocumentJobStage.UPLOAD,
            error_message=str(e),
            error_code="FILE_SAVE_FAILED",
        )
        db.commit()
        raise AppError(code="FILE_SAVE_FAILED", message="Failed to save file", status_code=500, details=str(e))

    doc.file_path = save_path
    db.commit()

    # async indexing
    background_tasks.add_task(index_document_pipeline, doc.id)

    return APIResponse(
        success=True,
        data={
            "document_id": doc.id,
            "job_id": job.id,
            "status": doc.status.value,
            "message": "uploaded, indexing started",
            # 可选：把文件大小返回给前端（调试方便）
            # "file_size": _written_size,
        },
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get(
    "/{document_id}/status",
    summary="Get document indexing status",
    description=(
        "Return the current indexing status for a document.\n\n"
        "- Auth required\n"
        "- Use this endpoint to poll until status becomes `done` (or `failed`)"
    ),
    response_model=APIResponse,
)
def get_document_status(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    doc = get_document_by_id(db, document_id=document_id, user_id=current_user.id)
    job = get_latest_document_job(db, document_id=document_id)

    return APIResponse(
        success=True,
        data={
            "document_id": doc.id,
            "status": doc.status.value,
            "job": serialize_document_job(job),
        },
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get(
    "",
    summary="List my documents",
    description=(
        "List documents uploaded by the current user.\n\n"
        "- Auth required\n"
        "- Returns basic metadata: id, filename, content_type, status\n"
        "- Adds `display_id` (1..N) for UI display without changing DB primary key"
    ),
    response_model=APIResponse,
)
def get_documents(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    total, docs = list_documents(
        db=db,
        user_id=current_user.id,
        limit=settings.DOCUMENT_LIST_LIMIT,
        offset=0,
    )

    # ✅ display_id: 根据当前排序（id desc）从 1 开始
    items = [
        {
            "display_id": idx + 1,          # ✅ 新增：展示用连续序号
            "document_id": d.id,            # ✅ 真实 id（用于删除/调试）
            "filename": d.filename,
            "content_type": d.content_type,
            "status": d.status.value,
        }
        for idx, d in enumerate(docs)
    ]

    return APIResponse(
        success=True,
        data={"items": items, "total": total},
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.delete(
    "/{document_id}",
    summary="Delete document",
    description="Delete document file + embeddings + database record",
    response_model=APIResponse,
)
def delete_document_api(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    delete_document_full(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )

    return APIResponse(
        success=True,
        data={
            "document_id": document_id,
            "deleted": True,
        },
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )
