# Trace ID 中间件
import uuid
from fastapi import Request

async def trace_id_middleware(request:Request,call_next):
    request.state.trace_id = uuid.uuid4().hex[:12]
    response = await call_next(request)
    response.headers["X-Trace-Id"] = request.state.trace_id
    return response