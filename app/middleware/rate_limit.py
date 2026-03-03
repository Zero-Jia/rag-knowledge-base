# 一个最简单的单机内存限流
# 同一个用户（用 Authorization header 区分）
# Sliding-window in-memory limiter
# 超过返回 429 Too Many Requests
import time
from typing import Dict,List
from fastapi import Request,HTTPException
from app.core.config import settings

RATE_LIMIT = settings.RATE_LIMIT_COUNT
WINDOW_SECONDS = settings.RATE_LIMIT_WINDOW_SECONDS

# 单机内存：多进程/多实例会失效（Day13 先这样）
request_log:Dict[str,List[float]] = {}

async def rate_limit_middleware(request:Request,call_next):
    # 用 Authorization 区分用户；没有就当 anonymous
    user = request.headers.get("authorization","anonymous")

    now = time.time()

    timestamps = request_log.get(user,[])
    timestamps = [ t for t in timestamps if now - t < WINDOW_SECONDS]

    if len(timestamps)>=RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests")
    
    timestamps.append(now)
    request_log[user] = timestamps

    return await call_next(request)
