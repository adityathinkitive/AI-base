import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

from aibase.audit import AuditSink, FileAuditSink, MemoryAuditSink
from aibase.core.context import request_id_var
from aibase.core.errors import AppError, PayloadTooLarge, RateLimited
from aibase.core.logging import configure_logging
from aibase.core.settings import Settings
from aibase.observability.tracing import setup_tracing
from aibase.phi.guard import make_log_scrubber
from aibase.providers.factory import Providers, build_phi_guard, build_providers

logger = logging.getLogger(__name__)
ReadinessCheck = Callable[[], Awaitable[bool]]


def _error_response(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    body = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id_var.get(),
        }
    }
    return JSONResponse(body, status_code=status, headers={"X-Request-ID": request_id_var.get()})


class _FixedWindowLimiter:
    def __init__(self, per_minute: int) -> None:
        self._limit = per_minute
        self._windows: dict[str, tuple[int, int]] = {}

    def hit(self, key: str) -> bool:
        window = int(time.time() // 60)
        w, count = self._windows.get(key, (window, 0))
        if w != window:
            w, count = window, 0
        self._windows[key] = (w, count + 1)
        return count + 1 <= self._limit


def create_app(
    settings: Settings,
    *,
    title: str,
    routers: list[APIRouter],
    providers: Providers | None = None,
    audit: AuditSink | None = None,
    readiness: list[ReadinessCheck] | None = None,
) -> FastAPI:
    guard = build_phi_guard(settings)
    configure_logging(settings.log_level, make_log_scrubber(guard))
    setup_tracing(settings.service_name, settings.otel.endpoint)

    registry = CollectorRegistry()
    requests_total = Counter(
        "http_requests_total", "HTTP requests", ["method", "route", "status"], registry=registry
    )
    latency = Histogram("http_request_seconds", "Request latency", ["route"], registry=registry)
    limiter = _FixedWindowLimiter(settings.limits.rate_limit_per_minute)

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
        logger.info("starting", extra={"service": settings.service_name, "env": settings.env})
        yield
        logger.info("shutting down")

    in_prod = settings.env in ("staging", "production")
    app = FastAPI(
        title=title,
        lifespan=lifespan,
        docs_url=None if in_prod else "/docs",
        redoc_url=None,
        openapi_url=None if in_prod else "/openapi.json",
    )
    app.state.settings = settings
    app.state.providers = providers or build_providers(settings)
    app.state.audit = audit or (
        MemoryAuditSink() if settings.env == "test" else FileAuditSink(settings.audit.path)
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_pipeline(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        started = time.perf_counter()
        try:
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > settings.limits.max_body_bytes:
                return _error_response(413, PayloadTooLarge.code, "request body too large")
            client = request.client.host if request.client else "unknown"
            if request.url.path not in ("/healthz", "/readyz", "/metrics") and not limiter.hit(
                client
            ):
                return _error_response(429, RateLimited.code, "rate limit exceeded")
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled error")
            response = _error_response(500, "internal_error", "internal server error")
        route = getattr(request.scope.get("route"), "path", "unmatched")
        elapsed = time.perf_counter() - started
        requests_total.labels(request.method, route, str(response.status_code)).inc()
        latency.labels(route).observe(elapsed)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        request_id_var.reset(token)
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("app error", extra={"code": exc.code})
        return _error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Default FastAPI echoes the offending input back, which can be PHI. Strip it.
        errors = [{"loc": e["loc"], "type": e["type"], "msg": e["msg"]} for e in exc.errors()]
        return _error_response(
            422, "validation_error", "request validation failed", {"errors": errors}
        )

    health = APIRouter()

    @health.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @health.get("/readyz", include_in_schema=False)
    async def readyz() -> JSONResponse:
        results = [await check() for check in readiness or []]
        ok = all(results)
        return JSONResponse(
            {"status": "ready" if ok else "not_ready"}, status_code=200 if ok else 503
        )

    @health.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    app.include_router(health)
    for router in routers:
        app.include_router(router)
    return app
