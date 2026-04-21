import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.database import Base, engine
from app.error_handlers import register_exception_handlers
from app.logging_config import setup_logging
from app.middleware.rate_limit import rate_limit_middleware
from app.middleware.trace import trace_id_middleware
from app.models import chat_session, document, document_job, parent_chunk, user
from app.routers import auth, chat, documents, health, search, search_hybrid, search_rerank, users
from app.services.request_context import set_request_id

setup_logging()

root_logger = logging.getLogger()
if not root_logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

app = FastAPI(
    title="RAG Knowledge Base backend",
    version="0.1.0",
    summary="Backend API for document upload, indexing, search and Agentic RAG chat.",
    description=(
        "Workflow: Register/Login -> Upload -> Check Status -> Search -> Chat.\n\n"
        "Auth: use `Authorization: Bearer <token>` for protected endpoints."
    ),
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        summary=app.summary,
        description=app.description,
        routes=app.routes,
    )
    schema.setdefault("components", {})
    schema["components"].setdefault("securitySchemes", {})
    schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(trace_id_middleware)

api_logger = logging.getLogger("api")


@app.middleware("http")
async def request_log_middleware(request: Request, call_next):
    rid = getattr(request.state, "trace_id", None)
    if rid:
        set_request_id(rid)

    start = time.time()
    api_logger.info("request start | rid=%s | %s %s", rid, request.method, request.url.path)

    try:
        response = await call_next(request)
        elapsed = time.time() - start
        api_logger.info(
            "request done  | rid=%s | status=%s | time=%.3fs",
            rid,
            response.status_code,
            elapsed,
        )
        return response
    except Exception as exc:
        elapsed = time.time() - start
        api_logger.error("request fail  | rid=%s | time=%.3fs | error=%s", rid, elapsed, exc)
        raise


app.middleware("http")(rate_limit_middleware)
register_exception_handlers(app)

Base.metadata.create_all(bind=engine)

app.include_router(health.router)
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(chat.router)
app.include_router(search_hybrid.router)
app.include_router(search_rerank.router)
