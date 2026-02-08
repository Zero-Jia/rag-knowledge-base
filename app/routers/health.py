from fastapi import APIRouter

# router 就像一个“路由集合”，专门装这一类接口
router = APIRouter(tags=["health"])


@router.get(
    "/ping",
    summary="Health check",
    description=(
        "Lightweight endpoint to verify the service is running.\n\n"
        "- No authentication required\n"
        "- Used by load balancers / monitoring systems to check liveness"
    ),
    responses={
        200: {
            "description": "Service is alive",
            "content": {
                "application/json": {
                    "example": {
                        "message": "pong"
                    }
                }
            },
        }
    },
)
def ping():
    # 健康检查：后端常用来让运维/负载均衡判断服务是否存活
    return {"message": "pong"}
