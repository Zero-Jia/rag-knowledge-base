# 统一响应模型
from pydantic import BaseModel
from typing import Any,Optional,Dict

class APIResponse(BaseModel):
    success:bool
    data:Optional[Any] = None
    error:Optional[Dict[str,Any]] = None
    trace_id:Optional[str] = None