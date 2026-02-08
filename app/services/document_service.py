from sqlalchemy.orm import Session
from app.models.document import Document
from app.exceptions import AppError

def get_document_by_id(db:Session,document_id:int,user_id:int)->Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise AppError(code="DOCUMENT_NOT_FOUND", message="Document not found", status_code=404)
    if doc.user_id != user_id:
        raise AppError(code="DOCUMENT_FORBIDDEN", message="No permission to access this document", status_code=403)
    return doc

def list_documents(db: Session, user_id: int, limit: int = 50, offset: int = 0):
    q = (
        db.query(Document)
        .filter(Document.user_id == user_id)
        .order_by(Document.id.desc())
    )

    total = q.count()
    docs = q.offset(offset).limit(limit).all()
    return total, docs