from fastapi import APIRouter, Depends

from app.schemas.query import QueryRequest, QueryResponse
from app.security import get_current_user
from app.services.hybrid_retrieval import hybrid_retrieve

router = APIRouter(prefix="/search/hybrid", tags=["search"])


@router.post(
    "/",
    summary="Hybrid search",
    response_model=QueryResponse,
)
def hybrid_search(
    req: QueryRequest,
    current_user=Depends(get_current_user),
):
    results = hybrid_retrieve(req.query, req.top_k, user_id=current_user.id)
    return {
        "query": req.query,
        "results": results,
    }
