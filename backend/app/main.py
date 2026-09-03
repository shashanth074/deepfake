"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.config import settings
from app.database import init_db
from app.observability import (
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    configure_logging,
    request_id_var,
)
from app.routers import auth, health, history, jobs, uploads

IS_PRODUCTION = settings.environment.lower() == "production"

configure_logging(debug=settings.debug, json_logs=IS_PRODUCTION)
logger = logging.getLogger(__name__)

DESCRIPTION = """
Forensic analysis platform for detecting manipulated images, audio and video.

Upload media, receive a probability score with visual evidence, and download a
timestamped PDF report suitable for attaching to a cybercrime complaint.

**This platform produces a technical assessment only.** It does not file
complaints with any authority and is not a certified forensic opinion.
"""


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.ensure_directories()
    init_db()
    logger.info(
        "%s v%s started (env=%s, queue=%s)",
        settings.app_name,
        __version__,
        settings.environment,
        "celery" if settings.queue_enabled else "inline/eager",
    )
    yield


app = FastAPI(
    title=settings.app_name,
    description=DESCRIPTION,
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Report-SHA256", REQUEST_ID_HEADER],
)
app.add_middleware(SecurityHeadersMiddleware, hsts=IS_PRODUCTION)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Return deliberate HTTP errors unchanged, with the request id attached."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request_id_var.get()},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Report malformed input without echoing the raw body back."""
    return JSONResponse(
        status_code=422,  # the named constant was renamed across Starlette versions
        content={
            "detail": "Request validation failed.",
            "errors": [
                {"field": ".".join(str(part) for part in error["loc"][1:]), "message": error["msg"]}
                for error in exc.errors()
            ],
            "request_id": request_id_var.get(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log the full traceback server-side; return an opaque error to the client.

    Stack traces, file paths and library versions are reconnaissance. The client
    gets the request id instead, which is enough to locate the full trace in the
    logs without exposing anything.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal error occurred. Quote the request id when reporting this.",
            "request_id": request_id_var.get(),
        },
    )


@app.middleware("http")
async def enforce_content_length(request: Request, call_next):
    """Reject oversized uploads before reading the body."""
    if request.url.path.endswith("/upload"):
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > settings.max_upload_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": f"File exceeds the {settings.max_upload_mb} MB upload limit."},
            )
    return await call_next(request)


for router in (health.router, auth.router, uploads.router, jobs.router, history.router):
    app.include_router(router, prefix=settings.api_v1_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "name": settings.app_name,
        "version": __version__,
        "docs": "/docs",
        "api": settings.api_v1_prefix,
        "disclaimer": (
            "Automated technical assessment only. Not a certified forensic or legal opinion."
        ),
    }
