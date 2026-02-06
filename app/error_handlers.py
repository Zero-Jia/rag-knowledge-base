# 全局异常处理
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.exceptions import AppError

logger = logging.getLogger("app.errors")

def register_exception_handlers(app):
    @app.exception_handler(AppError)
    async def app_error_handler(request:Request,exc:AppError):
        trace_id = getattr(request.state,"trace_id",None)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "data": None,
                "error": {"code": exc.code, "message": exc.message},
                "trace_id": trace_id,
            },
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        trace_id = getattr(request.state, "trace_id", None)
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "data": None,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request",
                    "detail": exc.errors(),
                },
                "trace_id": trace_id,
            },
        )
    
    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        trace_id = getattr(request.state, "trace_id", None)
        logger.exception(f"Unhandled error | trace_id={trace_id} | path={request.url.path}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "data": None,
                "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"},
                "trace_id": trace_id,
            },
        )