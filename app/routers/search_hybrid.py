# Hybrid Search API
from fastapi import APIRouter, Depends

from app.security import get_current_user
from app.services.hybrid_retrieval import hybrid_retrieve
from app.schemas.query import QueryRequest, QueryResponse

router = APIRouter(prefix="/search/hybrid", tags=["search"])


@router.post(
    "/",
    summary="Hybrid search (vector + keyword)",
    description=(
        "Perform hybrid retrieval combining vector similarity search and keyword matching.\n\n"
        "- Auth required\n"
        "- Uses vector search to retrieve candidate chunks\n"
        "- Re-ranks candidates with keyword-based scoring\n"
        "- Suitable when both semantic relevance and exact keyword match matter"
    ),
    response_model=QueryResponse,
    responses={
        200: {
            "description": "Hybrid search results",
            "content": {
                "application/json": {
                    "example": {
                        "query": "深度学习的主要应用场景是什么？",
                        "results": [
                            {
                                "text": "深度学习广泛应用于计算机视觉、语音识别、自然语言处理、推荐系统等领域。",
                                "document_id": 2,
                                "score": 0.86,
                            },
                            {
                                "text": "在计算机视觉任务中，深度学习常用于图像分类、目标检测、语义分割等。",
                                "document_id": 1,
                                "score": 0.79,
                            },
                        ],
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized (missing/invalid token)",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Not authenticated"
                    }
                }
            },
        },
    },
)
def hybrid_search(
    req: QueryRequest,
    current_user=Depends(get_current_user),
):
    results = hybrid_retrieve(req.query, req.top_k)
    return {
        "query": req.query,
        "results": results,
    }
