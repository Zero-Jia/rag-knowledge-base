from fastapi import APIRouter, Depends

from app.security import get_current_user
from app.schemas.query import QueryRequest, QueryResponse
from app.services.advanced_retrieval import retrieve_with_rerank

router = APIRouter(prefix="/search/rerank", tags=["search"])


@router.post(
    "/",
    summary="Search with rerank model",
    description=(
        "Retrieve candidate chunks and re-rank them using a cross-encoder rerank model.\n\n"
        "- Auth required\n"
        "- First-stage retrieval provides candidates\n"
        "- Rerank model scores candidates with higher precision\n"
        "- Suitable when answer quality is more important than latency"
    ),
    response_model=QueryResponse,
    responses={
        200: {
            "description": "Reranked search results",
            "content": {
                "application/json": {
                    "example": {
                        "query": "什么是深度学习？",
                        "results": [
                            {
                                "text": "深度学习是机器学习的一个分支，通常使用多层神经网络进行特征学习。",
                                "document_id": 1,
                                "score": 0.87,
                                "rerank_score": 0.63,
                            },
                            {
                                "text": "深度学习在计算机视觉、语音识别、自然语言处理等领域有广泛应用。",
                                "document_id": 2,
                                "score": 0.81,
                                "rerank_score": 0.58,
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
def rerank_search(
    req: QueryRequest,
    current_user=Depends(get_current_user),
):
    results = retrieve_with_rerank(req.query, req.top_k)
    return {
        "query": req.query,
        "results": results,
    }
