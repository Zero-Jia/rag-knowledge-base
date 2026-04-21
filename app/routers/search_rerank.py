from fastapi import APIRouter, Depends

from app.schemas.query import QueryRequest, QueryResponse
from app.security import get_current_user
from app.services.advanced_retrieval import retrieve_with_rerank

router = APIRouter(prefix="/search/rerank", tags=["search"])


@router.post(
    "/",
    summary="Hybrid search with rerank",
    response_model=QueryResponse,
)
def rerank_search(
    req: QueryRequest,
    current_user=Depends(get_current_user),
):
    results = retrieve_with_rerank(req.query, req.top_k, user_id=current_user.id)
    return {
        "query": req.query,
        "results": results,
    }
