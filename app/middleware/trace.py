import uuid
from fastapi import Request

TRACE_HEADER = "X-Trace-Id"

async def trace_id_middleware(request: Request, call_next):
    # ✅ 1) 优先使用上游传来的 Trace-Id（方便链路追踪）
    incoming = request.headers.get(TRACE_HEADER)

    trace_id = (incoming or uuid.uuid4().hex)[:12]
    request.state.trace_id = trace_id

    # ✅ 2) 确保响应一定有 X-Trace-Id
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        if response is not None:
            response.headers[TRACE_HEADER] = trace_id
