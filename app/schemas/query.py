# 请求/响应定义
from pydantic import BaseModel, Field
from typing import List, Optional


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User question")
    top_k: int = Field(5, ge=1, le=20, description="How many chunks to retrieve")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "什么是深度学习？",
                    "top_k": 5
                },
                {
                    "query": "总结这篇文档的关键要点",
                    "top_k": 8
                }
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
                    "text": "深度学习是机器学习的一个分支，通常使用多层神经网络进行特征学习。",
                    "document_id": 1,
                    "score": 0.87,
                    "rerank_score": 0.63
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
                    "query": "什么是深度学习？",
                    "results": [
                        {
                            "text": "深度学习是机器学习的一个分支，通常使用多层神经网络进行特征学习。",
                            "document_id": 1,
                            "score": 0.87,
                            "rerank_score": 0.63
                        },
                        {
                            "text": "深度学习在计算机视觉、语音识别、自然语言处理等领域有广泛应用。",
                            "document_id": 2,
                            "score": 0.81,
                            "rerank_score": 0.58
                        }
                    ]
                }
            ]
        }
    }
