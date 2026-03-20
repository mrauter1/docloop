from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    AuthContext,
    clear_login_csrf,
    clear_session_cookie,
    create_session,
    get_db_session,
    get_optional_auth_context,
    get_settings,
    get_templates,
    issue_login_csrf,
    require_auth_context,
    require_session_csrf,
    set_session_cookie,
    template_context,
    validate_login_csrf,
)
from shared.models import User, UserRole
from shared.security import normalize_email, verify_password


router = APIRouter()


@router.get("/login")
def login_page(
    request: Request,
    auth: AuthContext | None = Depends(get_optional_auth_context),
):
    if auth:
        redirect_url = "/app" if auth.user.role == UserRole.REQUESTER.value else "/ops"
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    settings = get_settings(request)
    templates = get_templates(request)
    response = templates.TemplateResponse(
        request,
        "login.html",
        template_context(
            request,
            auth=auth,
            error=request.query_params.get("error"),
            ops_pending=request.query_params.get("ops_pending") == "1",
        ),
    )
    if auth is None:
        csrf_token = issue_login_csrf(response, settings)
        response.context["csrf_token"] = csrf_token
    return response


@router.post("/login")
async def login_submit(
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext | None = Depends(get_optional_auth_context),
):
    if auth:
        redirect_url = "/app" if auth.user.role == UserRole.REQUESTER.value else "/ops"
        return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    form = await request.form()
    settings = get_settings(request)
    templates = get_templates(request)
    email = normalize_email(str(form.get("email", "")))
    password = str(form.get("password", ""))
    remember_me = str(form.get("remember_me", "")).lower() in {"1", "true", "on", "yes"}
    submitted_csrf = str(form.get("csrf_token", ""))

    if not validate_login_csrf(request, submitted_csrf, settings):
        response = templates.TemplateResponse(
            request,
            "login.html",
            template_context(request, auth=None, error="Invalid login form session."),
            status_code=status.HTTP_403_FORBIDDEN,
        )
        response.context["csrf_token"] = issue_login_csrf(response, settings)
        return response

    user = db.scalar(
        select(User).where(
            User.email == email,
            User.is_active.is_(True),
        )
    )
    if user is None or not verify_password(user.password_hash, password):
        response = templates.TemplateResponse(
            request,
            "login.html",
            template_context(request, auth=None, error="Invalid email or password."),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
        response.context["csrf_token"] = issue_login_csrf(response, settings)
        return response

    _, raw_token = create_session(
        db,
        user=user,
        settings=settings,
        remember_me=remember_me,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    redirect_url = "/app" if user.role == UserRole.REQUESTER.value else "/ops"
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, settings=settings, raw_token=raw_token, remember_me=remember_me)
    clear_login_csrf(response, settings)
    return response


@router.post("/logout")
async def logout_submit(
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_auth_context),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    db.delete(auth.session_record)
    db.commit()

    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    clear_session_cookie(response, settings=get_settings(request))
    return response
