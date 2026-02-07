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
- GET    /documents/{document_id}/chunks?chunk_size=500&overlap=100
  Preview chunking result (returns first 3 chunks + total).

Recommended frontend flow:
1) POST /documents/upload  -> get document_id
2) GET  /documents/{id}/status (poll) until indexed
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
from app.database import get_db
from app.models.document import Document, DocumentStatus
from app.security import get_current_user
from app.schemas.common import APIResponse
from app.exceptions import AppError

UPLOAD_ROOT = "storage/uploads"

router = APIRouter(prefix="/documents", tags=["documents"])


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
    responses={
        200: {
            "description": "Parsed text preview",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "document_id": 1,
                            "content_type": "application/pdf",
                            "text_preview": "深度学习是机器学习的一个分支……（前 1000 字）",
                            "text_length": 52340,
                        },
                        "error": None,
                        "trace_id": "a1b2c3d4e5f6",
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized (missing/invalid token)",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {"code": "UNAUTHORIZED", "message": "Not authenticated", "details": None},
                        "trace_id": "cafe1234dead",
                    }
                }
            },
        },
        415: {
            "description": "Unsupported document type",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "UNSUPPORTED_DOCUMENT_TYPE",
                            "message": "Unsupported content type: application/msword",
                            "details": None,
                        },
                        "trace_id": "f00dbabe0001",
                    }
                }
            },
        },
        500: {
            "description": "Document parse failed",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "DOCUMENT_PARSE_FAILED",
                            "message": "Parse failed",
                            "details": "Exception details...",
                        },
                        "trace_id": "deadbeef0001",
                    }
                }
            },
        },
    },
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
            "text_preview": text[:1000],
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
    responses={
        200: {
            "description": "Chunk preview",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "document_id": 1,
                            "chunk_size": 500,
                            "overlap": 100,
                            "items": [
                                "chunk-0: ……",
                                "chunk-1: ……",
                                "chunk-2: ……",
                            ],
                            "total": 42,
                        },
                        "error": None,
                        "trace_id": "a1b2c3d4e5f6",
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized (missing/invalid token)",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {"code": "UNAUTHORIZED", "message": "Not authenticated", "details": None},
                        "trace_id": "cafe1234dead",
                    }
                }
            },
        },
        415: {
            "description": "Unsupported document type",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "UNSUPPORTED_DOCUMENT_TYPE",
                            "message": "Unsupported content type: application/msword",
                            "details": None,
                        },
                        "trace_id": "f00dbabe0002",
                    }
                }
            },
        },
        500: {
            "description": "Document parse failed",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "DOCUMENT_PARSE_FAILED",
                            "message": "Parse failed",
                            "details": "Exception details...",
                        },
                        "trace_id": "deadbeef0002",
                    }
                }
            },
        },
    },
)
def get_document_chunks(
    document_id: int,
    request: Request,
    chunk_size: int = Query(500, ge=100, le=5000, description="Chunk size in characters"),
    overlap: int = Query(100, ge=0, le=1000, description="Overlap size in characters"),
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
    responses={
        200: {
            "description": "Upload accepted, indexing started",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "document_id": 12,
                            "status": "pending",
                            "message": "uploaded, indexing started",
                        },
                        "error": None,
                        "trace_id": "a1b2c3d4e5f6",
                    }
                }
            },
        },
        400: {
            "description": "Empty filename",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {"code": "EMPTY_FILENAME", "message": "Empty filename", "details": None},
                        "trace_id": "badf00d00001",
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized (missing/invalid token)",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {"code": "UNAUTHORIZED", "message": "Not authenticated", "details": None},
                        "trace_id": "cafe1234dead",
                    }
                }
            },
        },
        500: {
            "description": "Failed to save file",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "FILE_SAVE_FAILED",
                            "message": "Failed to save file",
                            "details": "Permission denied",
                        },
                        "trace_id": "deadbeef0003",
                    }
                }
            },
        },
    },
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

    save_path = os.path.join(UPLOAD_ROOT, f"{doc.id}_{file.filename}")

    try:
        with open(save_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise AppError(code="FILE_SAVE_FAILED", message="Failed to save file", status_code=500, details=str(e))

    doc.file_path = save_path
    db.commit()

    # async indexing
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


@router.get(
    "/{document_id}/status",
    summary="Get document indexing status",
    description=(
        "Return the current indexing status for a document.\n\n"
        "- Auth required\n"
        "- Use this endpoint to poll until status becomes `indexed` (or `failed`)"
    ),
    response_model=APIResponse,
    responses={
        200: {
            "description": "Current document status",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {"document_id": 12, "status": "indexed"},
                        "error": None,
                        "trace_id": "a1b2c3d4e5f6",
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized (missing/invalid token)",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {"code": "UNAUTHORIZED", "message": "Not authenticated", "details": None},
                        "trace_id": "cafe1234dead",
                    }
                }
            },
        },
        500: {
            "description": "Internal error",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "DOCUMENT_STATUS_FAILED",
                            "message": "Failed to get document status",
                            "details": "Unexpected error",
                        },
                        "trace_id": "deadbeef0004",
                    }
                }
            },
        },
    },
)
def get_document_status(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    doc = get_document_by_id(db, document_id=document_id, user_id=current_user.id)

    return APIResponse(
        success=True,
        data={"document_id": doc.id, "status": doc.status.value},
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )


@router.get(
    "",
    summary="List my documents",
    description=(
        "List documents uploaded by the current user.\n\n"
        "- Auth required\n"
        "- Returns basic metadata: id, filename, content_type, status"
    ),
    response_model=APIResponse,
    responses={
        200: {
            "description": "Document list",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "items": [
                                {
                                    "document_id": 12,
                                    "filename": "deep_learning_intro.pdf",
                                    "content_type": "application/pdf",
                                    "status": "indexed",
                                },
                                {
                                    "document_id": 13,
                                    "filename": "notes.txt",
                                    "content_type": "text/plain",
                                    "status": "pending",
                                },
                            ],
                            "total": 2,
                        },
                        "error": None,
                        "trace_id": "a1b2c3d4e5f6",
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized (missing/invalid token)",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {"code": "UNAUTHORIZED", "message": "Not authenticated", "details": None},
                        "trace_id": "cafe1234dead",
                    }
                }
            },
        },
    },
)
def get_documents(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
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
