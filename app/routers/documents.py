# 文件上传 router（核心）
import os
from fastapi import APIRouter,UploadFile,File,Depends,HTTPException
from sqlalchemy.orm import Session

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