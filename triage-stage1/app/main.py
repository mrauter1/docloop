from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, sessionmaker

from app.auth import get_optional_auth_context
from app.routes_auth import router as auth_router
from app.routes_ops import router as ops_router
from app.routes_requester import router as requester_router
from shared.config import Settings, get_settings
from shared.db import make_session_factory


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

    return app
