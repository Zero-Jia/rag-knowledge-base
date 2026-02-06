# 文件上传 router（核心）
import os
import shutil
from fastapi import APIRouter,UploadFile,File,Depends,Query,BackgroundTasks,Request
from sqlalchemy.orm import Session

from app.services.text_processing import process_text
from app.services.document_parser import parse_document
from app.services.indexing_service import index_document_pipeline
from app.services.document_service import get_document_by_id,list_documents
from app.database import get_db
from app.models.document import Document,DocumentStatus
from app.security import get_current_user
from app.schemas.common import APIResponse
from app.exceptions import AppError

UPLOAD_ROOT = "storage/uploads"

router = APIRouter(prefix="/documents",tags=["documents"])

@router.get("/{document_id}/text", response_model=APIResponse)
def get_document_text(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
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
            "text_preview": text[:1000],
            "text_length": len(text),
        },
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get("/{document_id}/chunks", response_model=APIResponse)
def get_document_chunks(
    document_id: int,
    request: Request,
    chunk_size: int = Query(500, ge=100, le=5000),
    overlap: int = Query(100, ge=0, le=1000),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
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
            "items": chunks[:3],  # 你这里是 preview，所以叫 items 更统一
            "total": len(chunks),
        },
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.post("/upload", response_model=APIResponse)
def upload_document(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
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

    save_path = os.path.join(UPLOAD_ROOT, f"{doc.id}_{file.filename}")

    try:
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise AppError(code="FILE_SAVE_FAILED", message="Failed to save file", status_code=500, details=str(e))

    doc.file_path = save_path
    db.commit()

    background_tasks.add_task(index_document_pipeline, doc.id)

    return APIResponse(
        success=True,
        data={
            "document_id": doc.id,
            "status": doc.status.value,
            "message": "uploaded, indexing started",
        },
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get("/{document_id}/status", response_model=APIResponse)
def get_document_status(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    doc = get_document_by_id(db, document_id=document_id, user_id=current_user.id)

    return APIResponse(
        success=True,
        data={"document_id": doc.id, "status": doc.status.value},
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )

@router.get("", response_model=APIResponse)
def get_documents(
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    total, docs = list_documents(db=db, user_id=current_user.id, limit=50, offset=0)

    items = [
        {
            "document_id": d.id,
            "filename": d.filename,
            "content_type": d.content_type,
            "status": d.status.value,
        }
        for d in docs
    ]

    return APIResponse(
        success=True,
        data={"items": items, "total": total},
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )

