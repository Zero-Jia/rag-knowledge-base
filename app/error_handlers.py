# 全局异常处理
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import AppError
from app.schemas.common import APIResponse, APIError

logger = logging.getLogger("app.errors")

def _trace_id(request: Request):
    return getattr(request.state, "trace_id", None)

def register_exception_handlers(app):
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        body = APIResponse(
            success=False,
            data=None,
            error=APIError(
                code=exc.code,
                message=exc.message,
                details=getattr(exc, "details", None),  # ✅ Day19: 透传 details
            ),
            trace_id=_trace_id(request),
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    # ✅ 推荐：把 HTTPException 也统一掉（否则前端还要兼容两套格式）
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        body = APIResponse(
            success=False,
            data=None,
            error=APIError(
                code="HTTP_EXCEPTION",
                message=str(exc.detail),
                details={"status_code": exc.status_code},
            ),
            trace_id=_trace_id(request),
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        body = APIResponse(
            success=False,
            data=None,
            error=APIError(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                details=exc.errors(),  # ✅ 统一用 details（不要用 detail）
            ),
            trace_id=_trace_id(request),
        )
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        trace_id = _trace_id(request)
        logger.exception(f"Unhandled error | trace_id={trace_id} | path={request.url.path}")

        body = APIResponse(
            success=False,
            data=None,
            error=APIError(
                code="INTERNAL_ERROR",
                message="Internal server error",
                details=None,  # 生产环境别把异常细节直接透出
            ),
            trace_id=trace_id,
        )
        return JSONResponse(status_code=500, content=body.model_dump())
