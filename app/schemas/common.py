# 统一响应模型
from typing import Any, Optional
from pydantic import BaseModel, Field


class APIError(BaseModel):
    code: str = Field(..., description="Business error code, stable for frontend")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Any] = Field(None, description="Optional extra error info")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "code": "DOCUMENT_PARSE_FAILED",
                    "message": "Parse failed",
                    "details": "ValueError: unsupported PDF encoding"
                },
                {
                    "code": "UNAUTHORIZED",
                    "message": "Not authenticated",
                    "details": None
                }
            ]
        }
    }


class APIResponse(BaseModel):
    success: bool = Field(..., description="true if business success")
    data: Optional[Any] = Field(None, description="Payload when success=true")
    error: Optional[APIError] = Field(None, description="Error when success=false")
    trace_id: Optional[str] = Field(None, description="Trace id for debugging")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "data": {
                        "items": [
                            {
                                "text": "深度学习是机器学习的一个分支…",
                                "document_id": 1,
                                "score": 0.87
                            }
                        ],
                        "total": 1
                    },
                    "error": None,
                    "trace_id": "a1b2c3d4e5f6"
                },
                {
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "EMPTY_QUESTION",
                        "message": "question cannot be empty",
                        "details": None
                    },
                    "trace_id": "f6e5d4c3b2a1"
                }
            ]
        }
    }
