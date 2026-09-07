"""FastAPI application entrypoint.

Wires routers, CORS (restricted to configured origins — never '*'), request
size limits, structured logging with a request id, and safe error handling
(no secrets or stack traces leaked to clients).
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routers import (
    ask,
    documents,
    explore,
    exports,
    health,
    ingestion,
    notes,
    providers,
    search,
    settings_router,
    stats,
)
from app.config import get_settings
from app.logging_config import configure_logging, get_logger

configure_logging()
log = get_logger("api")
settings = get_settings()

MAX_BODY_BYTES = 5 * 1024 * 1024  # 5 MB cap on JSON request bodies

app = FastAPI(
    title="Takshashila Archive Intelligence API",
    version=__version__,
    description="Provenance-first archival intelligence & grounded RAG research API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,   # explicit allowlist, never "*"
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    # Enforce a request body size limit (defence-in-depth).
    cl = request.headers.get("content-length")
    if cl and int(cl) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "request body too large"})
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001
        log.error("unhandled_error", request_id=request_id, path=str(request.url.path), error=str(exc))
        return JSONResponse(status_code=500, content={"detail": "internal server error", "request_id": request_id})
    response.headers["x-request-id"] = request_id
    return response


for r in (
    health.router, stats.router, documents.router, search.router, ask.router,
    providers.router, ingestion.router, explore.router, notes.router,
    exports.router, settings_router.router,
):
    app.include_router(r)


@app.on_event("startup")
def _startup():
    # In non-migration environments, ensure schema + registry exist.
    from app.bootstrap import init_db, seed_registry
    from app.db.base import SessionLocal

    try:
        init_db()
        db = SessionLocal()
        try:
            seed_registry(db)
        finally:
            db.close()
        log.info("startup_complete", version=__version__)
    except Exception as exc:  # pragma: no cover
        log.error("startup_failed", error=str(exc))


@app.get("/")
def root():
    return {"service": "Takshashila Archive Intelligence API", "version": __version__, "docs": "/docs"}
