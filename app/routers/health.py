from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get(
    "/ping",
    summary="Health check (ping/pong)",
    description=(
        "Lightweight endpoint to verify the service is running.\n\n"
        "- No authentication required\n"
        "- Used by load balancers / monitoring systems to check liveness"
    ),
    responses={
        200: {
            "description": "Service is alive",
            "content": {"application/json": {"example": {"message": "pong"}}},
        }
    },
)
def ping():
    return {"message": "pong"}

@router.get(
    "/health",
    summary="Health check (standard)",
    description=(
        "Standard health endpoint.\n\n"
        "- No authentication required\n"
        "- Used by Docker/Kubernetes health checks"
    ),
    responses={
        200: {
            "description": "Service is healthy",
            "content": {"application/json": {"example": {"status": "ok"}}},
        }
    },
)
def health():
    return {"status": "ok"}