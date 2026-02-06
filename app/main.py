import time
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.models import user, document
from app.routers import health, users, auth, documents, search, chat, search_hybrid, search_rerank

from app.middleware.rate_limit import rate_limit_middleware
from app.middleware.trace import trace_id_middleware
from app.error_handlers import register_exception_handlers
from app.logging_config import setup_logging
from app.services.request_context import set_request_id

# 设置日志
setup_logging()

app = FastAPI(
    title="RAG Knowledge Base backend",
    version="0.1.0",
)

# CORS（为 React 预热）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 1) Trace ID 放最外层：保证任何异常都有 trace_id
app.middleware("http")(trace_id_middleware)

# ✅ 2) 请求级日志：直接复用 trace_id（避免两套 id）
api_logger = logging.getLogger("api")

@app.middleware("http")
async def request_log_middleware(request: Request, call_next):
    # trace_id_middleware 已经先执行，所以这里一定拿得到
    rid = getattr(request.state, "trace_id", None)
    if rid:
        set_request_id(rid)

    start = time.time()
    api_logger.info(f"request start | rid={rid} | {request.method} {request.url.path}")

    try:
        resp = await call_next(request)
        elapsed = time.time() - start
        api_logger.info(f"request done  | rid={rid} | status={resp.status_code} | time={elapsed:.3f}s")
        return resp
    except Exception as e:
        elapsed = time.time() - start
        api_logger.error(f"request fail  | rid={rid} | time={elapsed:.3f}s | error={e}")
        raise

# ✅ 3) rate limit 放在 log 之后：被限流也会有完整日志 + trace_id
app.middleware("http")(rate_limit_middleware)

# ✅ 4) 注册全局异常 handler（输出统一 APIResponse）
register_exception_handlers(app)

# 建表
Base.metadata.create_all(bind=engine)

# 路由
app.include_router(health.router)
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(search_hybrid.router)
app.include_router(search_rerank.router)

'''
# 例子解释：
# app.get("/ping")：当有人用 HTTP GET 方法访问 /ping 这个路径时，把请求交给下面这个函数处理。
# def ping()：这是处理 /ping 请求的“控制器/处理器
# return {"message": "pong"}： 你返回的是一个 Python dict，FastAPI 会自动做两件事。
# 1.把 dict 转成 JSON（序列化） 2.设置 HTTP 响应为 application/json

# /ping 通常叫健康检查接口：你部署到服务器后，运维或负载均衡器会定期请求它，如果它能返回 pong，说明服务活着
@app.get("/ping")
def ping():
    return{"message":"pong"}

# @app.get("/")：根路径接口
@app.get("/")
def root():
    return {"message":"Welcome to RAG Knowledge Base Backend"}
'''
