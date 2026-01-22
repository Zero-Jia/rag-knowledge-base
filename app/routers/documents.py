# 文件上传 router（核心）
import os
from fastapi import APIRouter,UploadFile,File,Depends,HTTPException,Query
from sqlalchemy.orm import Session

from app.services.text_processing import process_text
from app.services.document_parser import parse_document
from app.database import get_db
from app.models.document import Document
from app.security import get_current_user

UPLOAD_ROOT = "storage/uploads"

router = APIRouter(prefix="/documents",tags=["documents"])

@router.post("/upload")
def upload_document(
    file:UploadFile = File(...),
    db:Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400,detail="Empty filename")
    
    # 1) 先落库拿到 doc.id
    doc = Document(
        user_id = current_user.id,
        filename = file.filename,
        content_type = file.content_type or "application/octet-stream",
        file_path = "",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 2) 构造目录
    user_dir = os.path.join(UPLOAD_ROOT,str(current_user.id))
    doc_dir = os.path.join(user_dir,str(doc.id))
    os.makedirs(doc_dir,exist_ok=True)

    file_path = os.path.join(doc_dir,file.filename)

    # 3) 写入磁盘
    try:
        with open(file_path,"wb") as f:
            f.write(file.file.read())
    except Exception:
        raise HTTPException(status_code=500,detail="Failed to save file")
    
    # 4) 更新 file_path
    doc.file_path = file_path
    db.commit()

    return{
        "id":doc.id,
        "filename":doc.filename,
        "message":"Upload successful",
    }

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