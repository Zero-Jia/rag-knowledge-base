from sqlalchemy.orm import Session
from app.exceptions import AppError
from app.services.retrieval_service import retrieve_chunks

def search_chunks(db: Session, user_id: int, query: str, top_k: int):
    q = (query or "").strip()
    if not q:
        raise AppError(code="EMPTY_QUERY", message="Query cannot be empty", status_code=400)

    if top_k < 1 or top_k > 20:
        raise AppError(code="INVALID_TOP_K", message="top_k must be between 1 and 20", status_code=400)

    chunks = retrieve_chunks(q, top_k)

    # ✅ 统一列表协议：items/total
    return {
        "query": q,
        "items": chunks,
        "total": len(chunks),
    }
