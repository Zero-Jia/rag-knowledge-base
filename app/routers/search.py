# 新增检索 Router：POST /search
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.schemas.query import QueryRequest
from app.schemas.common import APIResponse
from app.database import get_db
from app.security import get_current_user
from app.services.search_service import search_chunks

router = APIRouter(prefix="/search", tags=["search"])


@router.post(
    "/",
    summary="Vector search",
    description=(
        "Retrieve top relevant chunks using vector similarity search.\n\n"
        "- Auth required\n"
        "- Input: `query` + `top_k`\n"
        "- Output: a list of matched chunks and scores (wrapped by APIResponse)\n"
        "- Use `/search/hybrid` for keyword+vector, or `/search/rerank` for higher precision"
    ),
    response_model=APIResponse,
    responses={
        200: {
            "description": "Search results (APIResponse)",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "items": [
                                {
                                    "text": "深度学习是机器学习的一个分支，通常使用多层神经网络进行特征学习。",
                                    "document_id": 1,
                                    "score": 0.87,
                                },
                                {
                                    "text": "深度学习在计算机视觉、语音识别、自然语言处理等领域有广泛应用。",
                                    "document_id": 2,
                                    "score": 0.81,
                                },
                            ],
                            "total": 2,
                        },
                        "error": None,
                        "trace_id": "a1b2c3d4e5f6",
                    }
                }
            },
        },
        400: {
            "description": "Bad request (e.g. empty query)",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "EMPTY_QUERY",
                            "message": "query cannot be empty",
                            "details": None,
                        },
                        "trace_id": "f0e1d2c3b4a5",
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized (missing/invalid token)",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "UNAUTHORIZED",
                            "message": "Not authenticated",
                            "details": None,
                        },
                        "trace_id": "cafe1234dead",
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "error": {
                            "code": "SEARCH_INTERNAL_ERROR",
                            "message": "Internal search error",
                            "details": "Unexpected error",
                        },
                        "trace_id": "deadbeef1234",
                    }
                }
            },
        },
    },
)
def semantic_search(
    req: QueryRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = search_chunks(db=db, user_id=current_user.id, query=req.query, top_k=req.top_k)

    return APIResponse(
        success=True,
        data=data,
        error=None,
        trace_id=getattr(request.state, "trace_id", None),
    )
