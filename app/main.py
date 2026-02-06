import uuid
import time
import logging

from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine,Base
from app.models import user,document # from app.models import user 是为了让 User 这个 model 被 import 到内存里，否则 metadata 里可能没表
from app.routers import health,users,auth,documents,search,chat,search_hybrid,search_rerank
from app.middleware.rate_limit import rate_limit_middleware
from app.middleware.trace import trace_id_middleware
from app.error_handlers import register_exception_handlers
from app.logging_config import setup_logging
from app.services.request_context import set_request_id

# 设置日志
setup_logging()

# 创建一个FastAPI应用实例，名字叫app
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

# 注册全局异常 handler
register_exception_handlers(app)

# 请求级日志 + request_id 串联整条链路
api_logger = logging.getLogger("api")

@app.middleware("http")
async def request_log_middleware(request:Request,call_next):
    rid = uuid.uuid4().hex[:8]
    set_request_id(rid)

    start = time.time()
    api_logger.info(f"request start | rid={rid} | {request.method} {request.url.path}")

    try:
        resp = await call_next(request)
        elapsed = time.time()-start
        api_logger.info(f"request done  | rid={rid} | status={resp.status_code} | time={elapsed:.3f}s")
        return resp
    except Exception as e:
        elapsed = time.time()-start
        api_logger.error(f"request fail  | rid={rid} | time={elapsed:.3f}s | error={e}")
        raise

# 注册 Trace ID Middleware（让每个响应头都有 X-Trace-Id）
app.middleware("http")(trace_id_middleware)

# 注册 Middleware
app.middleware("http")(rate_limit_middleware)

Base.metadata.create_all(bind=engine)

# include_router 的含义：把 health.py 里的所有路由挂到主 app 上
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
