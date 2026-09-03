"""Request correlation and structured logging.

Every request is tagged with an id that appears in each log line it produces and
is returned to the client in ``X-Request-ID``. When a user reports a failure,
that one value retrieves the whole server-side story — which is the difference
between a diagnosable incident and a guess.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Context-local so concurrent requests never read each other's id.
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON for log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(debug: bool, json_logs: bool) -> None:
    """Install the formatter and request-id filter on the root logger."""
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        JsonFormatter()
        if json_logs
        else logging.Formatter("%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s")
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # Uvicorn installs its own handlers; route them through ours so every line
    # carries the request id.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request id, time the request, and log its completion."""

    def __init__(self, app: ASGIApp, logger_name: str = "app.request") -> None:
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)

    async def dispatch(self, request, call_next):
        # Honour an upstream id so a trace survives the reverse proxy hop.
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming or uuid.uuid4().hex[:16]
        token = request_id_var.set(request_id)
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            self.logger.exception(
                "%s %s failed after %.1f ms", request.method, request.url.path, duration_ms
            )
            raise
        finally:
            request_id_var.reset(token)

        duration_ms = (time.perf_counter() - started) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id
        # Health checks would otherwise dominate the log at one line per probe.
        if request.url.path != "/api/health":
            self.logger.info(
                "%s %s -> %s in %.1f ms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Set defensive response headers on the API itself.

    Nginx sets these for the static front end, but the API is frequently exposed
    directly (a different host, a mobile client, a compose port mapping), and a
    header only applied at one edge is not applied at all.
    """

    def __init__(self, app: ASGIApp, hsts: bool = False) -> None:
        super().__init__(app)
        self.hsts = hsts

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        # The API returns JSON and images, never HTML, so it needs no script
        # sources at all.
        headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'",
        )
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if self.hsts:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
