from typing import List, Optional

from pydantic import BaseModel, Field

from app.core.config import settings


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User question")
    top_k: int = Field(
        settings.TOP_K,
        ge=settings.TOP_K_MIN,
        le=settings.TOP_K_MAX,
        description="How many chunks to retrieve",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "What is deep learning?", "top_k": settings.TOP_K},
                {"query": "Summarize key points", "top_k": min(settings.TOP_K_MAX, 8)},
            ]
        }
    }


class RetrievedChunk(BaseModel):
    text: str
    document_id: int
    score: Optional[float] = None
    rerank_score: Optional[float] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": "Deep learning is a branch of machine learning.",
                    "document_id": 1,
                    "score": 0.87,
                    "rerank_score": 0.63,
                }
            ]
        }
    }


class QueryResponse(BaseModel):
    query: str
    results: List[RetrievedChunk]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "What is deep learning?",
                    "results": [
                        {
                            "text": "Deep learning is a branch of machine learning.",
                            "document_id": 1,
                            "score": 0.87,
                            "rerank_score": 0.63,
                        },
                        {
                            "text": "It is widely used in vision and NLP.",
                            "document_id": 2,
                            "score": 0.81,
                            "rerank_score": 0.58,
                        },
                    ],
                }
            ]
        }
    }
