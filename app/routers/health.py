from fastapi import APIRouter

# router 就像一个“路由集合”，专门装这一类接口
router = APIRouter()

@router.get("/ping")
def ping():
    # 健康检查：后端常用来让运维/负载均衡判断服务是否存活
    return {"message":"pong"}
