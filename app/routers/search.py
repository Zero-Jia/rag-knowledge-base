# 新增检索 Router：POST /search
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.schemas.query import QueryRequest
from app.schemas.common import APIResponse
from app.database import get_db
from app.security import get_current_user
from app.services.search_service import search_chunks

router = APIRouter(prefix="/search", tags=["search"])

@router.post("/", response_model=APIResponse)
def semantic_search(
    req: QueryRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    data = search_chunks(db=db, user_id=current_user.id, query=req.query, top_k=req.top_k)

    return APIResponse(
        success=True,
        data=data,
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )
