"""FastAPI app entrypoint — Zecpath ATS API v1."""
from __future__ import annotations
from contextlib import asynccontextmanager

from fastapi import FastAPI

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

    return app


app = create_app()
