from fastapi import FastAPI
from app.database import engine,Base
from app.models import user,document # from app.models import user 是为了让 User 这个 model 被 import 到内存里，否则 metadata 里可能没表
from app.routers import health,users,auth,documents,search,chat,search_hybrid,search_rerank
from app.middleware.rate_limit import rate_limit_middleware

# 创建一个FastAPI应用实例，名字叫app
app = FastAPI(
    title="RAG Knowledge Base backend",
    version="0.1.0",
)

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
