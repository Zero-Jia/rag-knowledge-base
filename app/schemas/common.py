# 统一响应模型
from typing import Any, Optional
from pydantic import BaseModel, Field

class APIError(BaseModel):
    code: str = Field(..., description="Business error code, stable for frontend")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Any] = Field(None, description="Optional extra error info")

class APIResponse(BaseModel):
    success: bool = Field(..., description="true if business success")
    data: Optional[Any] = Field(None, description="Payload when success=true")
    error: Optional[APIError] = Field(None, description="Error when success=false")
    trace_id: Optional[str] = Field(None, description="Trace id for debugging")
