from __future__ import annotations

import logging
from pathlib import Path
import time

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, sessionmaker

from app.auth import get_optional_auth_context
from app.routes_auth import router as auth_router
from app.routes_ops import router as ops_router
from app.routes_requester import router as requester_router
from shared.bootstrap import check_database_readiness, workspace_readiness_issues
from shared.config import Settings, get_settings
from shared.db import make_session_factory
from shared.logging import log_event


LOGGER = logging.getLogger("triage-stage1.web")


def create_app(
    *,
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_session_factory = session_factory or make_session_factory(settings=resolved_settings)

    app = FastAPI(title="Stage 1 AI Triage MVP")
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

    app.state.settings = resolved_settings
    app.state.session_factory = resolved_session_factory
    app.state.templates = templates

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        started = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            log_event(
                LOGGER,
                service="web",
                event="http_request",
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                error_text=str(exc),
            )
            raise
        finally:
            if response is not None:
                log_event(
                    LOGGER,
                    service="web",
                    event="http_request",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                )

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(auth_router)
    app.include_router(requester_router)
    app.include_router(ops_router)

    @app.get("/")
    def home(
        auth=Depends(get_optional_auth_context),
    ):
        if auth is None:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        if auth.user.role == "requester":
            return RedirectResponse(url="/app", status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(url="/ops", status_code=status.HTTP_303_SEE_OTHER)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz():
        issues = workspace_readiness_issues(resolved_settings)
        database_issue = check_database_readiness(resolved_session_factory)
        if database_issue:
            issues.insert(0, f"database not ready: {database_issue}")
        if issues:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_ready", "issues": issues},
            )
        return {"status": "ok"}

    return app
