from fastapi import FastAPI

# 创建一个FastAPI应用实例，名字叫app
app = FastAPI(
    title="RAG Knowledge Base backend",
    version="0.1.0",
)

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