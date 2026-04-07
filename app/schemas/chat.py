from typing import List, Optional, Literal

from pydantic import BaseModel, Field

from app.core.config import settings


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="User question")
    retrieval_mode: Literal["vector", "hybrid", "rerank"] = Field(
        default=settings.RETRIEVAL_MODE,
        description="Retrieval mode used for cache scope and future extensibility",
    )
    top_k: int = Field(
        default=settings.TOP_K,
        ge=settings.TOP_K_MIN,
        le=settings.TOP_K_MAX,
        description="How many chunks to retrieve",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question": "什么是深度学习？",
                    "retrieval_mode": "hybrid",
                    "top_k": 5,
                },
                {
                    "question": "请解释一下 RAG 的原理",
                    "retrieval_mode": "hybrid",
                    "top_k": 5,
                },
            ]
        }
    }


class ChatChunk(BaseModel):
    text: str = Field(..., description="Retrieved chunk text")
    document_id: int = Field(..., description="Source document id")
    score: Optional[float] = Field(None, description="Retrieval/fusion score")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "text": "深度学习是机器学习的一个分支，通常使用多层神经网络进行特征学习。",
                    "document_id": 1,
                    "score": 0.87,
                }
            ]
        }
    }


class ChatResponseData(BaseModel):
    question: str = Field(..., description="User question")
    answer: str = Field(..., description="Final answer")
    chunks: List[ChatChunk] = Field(default_factory=list, description="Retrieved chunks used to answer")

    cache_hit: bool = Field(..., description="Whether any cache was hit")
    cache_type: Literal["exact", "semantic", "none"] = Field(
        ...,
        description="Which cache layer served the response",
    )
    semantic_similarity: Optional[float] = Field(
        None,
        description="Semantic similarity when semantic cache hits",
    )
    matched_cached_question: Optional[str] = Field(
        None,
        description="Matched historical question in semantic cache",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question": "什么是深度学习？",
                    "answer": "深度学习是机器学习的一个分支，通常通过多层神经网络从数据中自动学习特征。",
                    "chunks": [
                        {
                            "text": "深度学习是机器学习的一个分支，通常使用多层神经网络进行特征学习。",
                            "document_id": 1,
                            "score": 0.87,
                        }
                    ],
                    "cache_hit": False,
                    "cache_type": "none",
                    "semantic_similarity": None,
                    "matched_cached_question": None,
                },
                {
                    "question": "请解释一下深度学习",
                    "answer": "深度学习是机器学习的一个分支，通常通过多层神经网络从数据中自动学习特征。",
                    "chunks": [],
                    "cache_hit": True,
                    "cache_type": "semantic",
                    "semantic_similarity": 0.947,
                    "matched_cached_question": "什么是深度学习？",
                },
            ]
        }
    }