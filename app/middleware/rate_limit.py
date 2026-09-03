# 单机内存限流（sliding window）
# middleware 里抛 HTTPException 会绕过 FastAPI 的 exception_handler，
# 导致 429 变成 500；改为直接返回 JSONResponse 确保响应正确。
import time
from typing import Dict, List

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette import status

from app.core.config import settings

RATE_LIMIT = settings.RATE_LIMIT_COUNT
WINDOW_SECONDS = settings.RATE_LIMIT_WINDOW_SECONDS

request_log: Dict[str, List[float]] = {}


async def rate_limit_middleware(request: Request, call_next):
    # 用 Authorization 区分用户；没有就当 anonymous
    user = request.headers.get("authorization", "anonymous")

    now = time.time()
    timestamps = request_log.get(user, [])
    # 清理窗口外的旧时间戳
    timestamps = [t for t in timestamps if now - t < WINDOW_SECONDS]

    if len(timestamps) >= RATE_LIMIT:
        body = {
            "success": False,
            "data": None,
            "error": {
                "code": "RATE_LIMITED",
                "message": f"Too many requests ({RATE_LIMIT}/{WINDOW_SECONDS}s), please retry later.",
                "details": {"limit": RATE_LIMIT, "window_seconds": WINDOW_SECONDS},
            },
            "trace_id": getattr(request.state, "trace_id", None),
        }
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=body,
        )

    timestamps.append(now)
    request_log[user] = timestamps

    return await call_next(request)
