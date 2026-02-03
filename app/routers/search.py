# 新增检索 Router：POST /search
from fastapi import APIRouter,Depends

from app.schemas.query import QueryRequest,QueryResponse
from app.services.retrieval_service import retrieve_chunks
from app.security import get_current_user

router = APIRouter(prefix="/search",tags=["search"])

@router.post("/",response_model=QueryResponse)
def semantic_search(
    req:QueryRequest,
    current_user = Depends(get_current_user)
):
    chunks = retrieve_chunks(req.query,req.top_k)
    return {
        "query":req.query,
        "results":chunks,
    }