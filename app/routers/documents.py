# 文件上传 router（核心）
import os
import shutil
from fastapi import APIRouter,UploadFile,File,Depends,HTTPException,Query,BackgroundTasks,Request
from sqlalchemy.orm import Session

from app.services.text_processing import process_text
from app.services.document_parser import parse_document
from app.services.indexing_service import index_document_pipeline
from app.database import get_db
from app.models.document import Document,DocumentStatus
from app.security import get_current_user
from app.schemas.common import APIResponse
from app.exceptions import AppError

UPLOAD_ROOT = "storage/uploads"

router = APIRouter(prefix="/documents",tags=["documents"])

@router.get("/{document_id}/text")
def get_document_text(
    document_id:int,
    db:Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    doc = (
        db.query(Document)
        .filter(Document.id == document_id,Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404,detail="Document not found")
    
    try: 
        text = parse_document(doc.file_path,doc.content_type)
    except ValueError as e:
        raise HTTPException(status_code=415,detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500,detail=f"Parse failed: {e}")
    
    return {
        "document_id":doc.id,
        "content_type":doc.content_type,
        "text_preview":text[:1000],
        "text_length":len(text),
    }

@router.get("/{document_id}/chunks")
def get_document_chunks(
    document_id:int,
    chunk_size:int = Query(500,ge=100,le=5000),
    overlap:int = Query(100,ge=0,le=1000),
    db:Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # 1) 查文档 + 校验权限（只能看自己的）
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not doc:
        raise HTTPException(status_code=404,detail="Document not found")
    
    # 2) 从文件解析出原始文本
    raw_text = parse_document(doc.file_path,doc.content_type)
    if not raw_text or not raw_text.strip():
        return{
            "document_id": doc.id,
            "chunk_size": chunk_size,
            "overlap": overlap,
            "chunk_count": 0,
            "chunks_preview": []
        }
    
    # 3) 清洗 + 分块
    chunks = process_text(raw_text,chunk_size,overlap)

    # 4) 返回预览（先不入库，Day 8 再做 embedding）
    return {
        "document_id": doc.id,
        "chunk_size": chunk_size,
        "overlap": overlap,
        "chunk_count": len(chunks),
        "chunks_preview": chunks[:3]
    }

@router.post("/upload")
def upload_document(
    background_tasks:BackgroundTasks,
    file:UploadFile = File(...),
    db:Session =  Depends(get_db),
    current_user = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename")
    
    os.makedirs(UPLOAD_ROOT,exist_ok=True)

    # 1) 先落库拿 doc.id
    doc = Document(
        user_id = current_user.id,
        filename = file.filename,
        content_type = file.content_type or "application/octet-stream",
        file_path = "",
        status = DocumentStatus.PENDING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    # 2) 保存文件到磁盘（用 doc.id 组织目录/文件名）
    save_path = os.path.join(UPLOAD_ROOT,f"{doc.id}_{file.filename}")
    with open(save_path,"wb") as f:
        shutil.copyfileobj(file.file,f)
    # 3) 更新 file_path
    doc.file_path = save_path
    db.commit()
    # 4) 触发后台索引（立刻返回，不阻塞）
    background_tasks.add_task(index_document_pipeline,doc.id)
    return {
        "document_id":doc.id,
        "status":doc.status.value,
        "message":"uploaded, indexing started"
    }

@router.get("/{document_id}/status")
def get_document_status(
    document_id:int,
    request:Request,
    db:Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id
    ).first()

    if not doc:
        raise AppError("DOC_NOT_FOUND", "Document not found", 404)
    # 成功返回统一结构（success/data/error/trace_id）
    return APIResponse(
        success=True,
        data={"document_id": doc.id, "status": doc.status.value},
        trace_id=getattr(request.state, "trace_id", None),
    )