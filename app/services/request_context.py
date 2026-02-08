# 给每个请求加 “请求级追踪 ID”（让一次 /chat 的日志能串起来）
from contextvars import ContextVar

request_id_ctx: ContextVar[str] = ContextVar("request_id",default="-")

def get_request_id()->str:
    return request_id_ctx.get()

def set_request_id(rid:str):
    request_id_ctx.set(rid)