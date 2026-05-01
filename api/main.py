"""FastAPI app entrypoint — Zecpath ATS API v1."""
from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from api.config import settings
from api.core.logging_config import configure_logging, get_logger
from api.core.middleware import RequestIDMiddleware, register_exception_handlers
from api.routes import resume as resume_routes
from api.routes import job as jd_routes
from api.routes import ats as ats_routes
from api.routes import jobs as async_jobs_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log = get_logger(__name__)
    log.info(f"Starting {settings.api_title} v{settings.api_version}")
    yield
    log.info("Shutting down")


def _patch_file_schemas(schema: dict[str, Any]) -> None:
    """Walk OpenAPI schema and convert OpenAPI 3.1's `contentMediaType` to
    OpenAPI 3.0's `format: binary` for any string fields representing files.

    Without this, Swagger UI shows a TEXT input for file array fields
    instead of a file picker. Affects /v1/resume/upload/batch in particular.
    """
    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            # Found a binary string node — normalize it
            if (
                node.get("type") == "string"
                and "contentMediaType" in node
                and "format" not in node
            ):
                node["format"] = "binary"
                # Drop contentMediaType (3.1-only) to avoid Swagger UI confusion
                node.pop("contentMediaType", None)
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)
    _walk(schema)


def _custom_openapi(app: FastAPI):
    """Generate OpenAPI 3.0 (not 3.1) so Swagger UI renders file inputs correctly."""
    def factory():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        # Pin to OpenAPI 3.0.3 so binary-format file fields render as pickers
        schema["openapi"] = "3.0.3"
        _patch_file_schemas(schema)
        app.openapi_schema = schema
        return app.openapi_schema
    return factory


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=lifespan,
        description=(
            "Zecpath ATS REST API — Day 16 deliverable.\n\n"
            "Endpoints handle multiple resumes & multiple JDs (single + batch). "
            "All async heavy-lifting runs through `/v1/jobs/*`."
        ),
    )

    # Middleware
    app.add_middleware(RequestIDMiddleware)
    register_exception_handlers(app)

    # Versioned routes
    base = settings.api_base_path
    app.include_router(resume_routes.router, prefix=base)
    app.include_router(jd_routes.router, prefix=base)
    app.include_router(ats_routes.router, prefix=base)
    app.include_router(async_jobs_routes.router, prefix=base)

    @app.get("/", tags=["Health"])
    async def root():
        return {"message": "Zecpath ATS API Running", "version": settings.api_version}

    @app.get(f"{base}/health", tags=["Health"])
    async def health():
        return {"status": "ok", "service": settings.service_name}

    # Override OpenAPI generator AFTER routes registered
    app.openapi = _custom_openapi(app)

    return app


app = create_app()
