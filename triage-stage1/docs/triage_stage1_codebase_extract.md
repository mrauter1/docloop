├── .env.example
├── README.md
├── alembic.ini
├── app/
│   ├── __init__.py
│   ├── auth.py
│   ├── main.py
│   ├── render.py
│   ├── routes_auth.py
│   ├── routes_ops.py
│   ├── routes_requester.py
│   ├── static/
│   │   └── styles.css
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── ops/
│   │   │   ├── board.html
│   │   │   └── detail.html
│   │   └── tickets/
│   │       ├── detail.html
│   │       ├── list.html
│   │       └── new.html
│   └── uploads.py
├── docs/
│   ├── acceptance_matrix.md
│   ├── manual_verification.md
│   └── triage_stage1_codebase_extract.md
├── requirements.txt
├── scripts/
│   ├── __init__.py
│   ├── _common.py
│   ├── bootstrap_workspace.py
│   ├── create_admin.py
│   ├── create_user.py
│   ├── deactivate_user.py
│   ├── run_web.py
│   ├── run_worker.py
│   └── set_password.py
├── shared/
│   ├── __init__.py
│   ├── bootstrap.py
│   ├── config.py
│   ├── db.py
│   ├── logging.py
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 20260319_0001_initial.py
│   ├── models.py
│   ├── permissions.py
│   ├── security.py
│   ├── tickets.py
│   ├── user_admin.py
│   └── workspace_contract.py
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_ops_app.py
│   ├── test_phase5_operability.py
│   ├── test_requester_app.py
│   ├── test_security.py
│   ├── test_ticket_helpers.py
│   ├── test_uploads.py
│   └── test_worker_phase4.py
└── worker/
    ├── __init__.py
    ├── codex_runner.py
    ├── main.py
    ├── queue.py
    ├── ticket_loader.py
    └── triage.py

# File: .env.example
```text
APP_BASE_URL=http://localhost:8000
APP_SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=postgresql+psycopg://triage:triage@localhost:5432/triage

UPLOADS_DIR=/opt/triage/data/uploads
TRIAGE_WORKSPACE_DIR=/opt/triage/triage_workspace
REPO_MOUNT_DIR=/opt/triage/triage_workspace/app
MANUALS_MOUNT_DIR=/opt/triage/triage_workspace/manuals

CODEX_BIN=codex
CODEX_API_KEY=replace-with-codex-api-key
CODEX_MODEL=
CODEX_TIMEOUT_SECONDS=75
WORKER_POLL_SECONDS=10

AUTO_SUPPORT_REPLY_MIN_CONFIDENCE=0.85
AUTO_CONFIRM_INTENT_MIN_CONFIDENCE=0.90

MAX_IMAGES_PER_MESSAGE=3
MAX_IMAGE_BYTES=5242880

SESSION_DEFAULT_HOURS=12
SESSION_REMEMBER_DAYS=30

# Operational notes:
# - /readyz checks DATABASE_URL plus UPLOADS_DIR, TRIAGE_WORKSPACE_DIR,
#   REPO_MOUNT_DIR, MANUALS_MOUNT_DIR, TRIAGE_WORKSPACE_DIR/runs,
#   TRIAGE_WORKSPACE_DIR/AGENTS.md, and
#   TRIAGE_WORKSPACE_DIR/.agents/skills/stage1-triage/SKILL.md.
# - python scripts/bootstrap_workspace.py initializes the workspace git repo,
#   writes the exact agent artifacts, and records system_state.bootstrap_version.

```
# End of file: .env.example

# File: alembic.ini
```text
[alembic]
script_location = shared/migrations
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s

```
# End of file: alembic.ini

# File: requirements.txt
```text
fastapi
uvicorn
jinja2
sqlalchemy>=2.0
alembic
psycopg[binary]
pydantic>=2.0
pillow
markdown-it-py
bleach
argon2-cffi
httpx
python-multipart
pytest

```
# End of file: requirements.txt

# File: README.md
```markdown
# Stage 1 AI Triage MVP

This subproject contains the isolated implementation for the Stage 1 custom Python triage application described in the frozen PRD.

Current implementation coverage includes:
- FastAPI requester and Dev/TI UI surfaces with PostgreSQL-backed auth/session state
- worker queue processing and read-only Codex orchestration
- bootstrap and operability scripts for the mandated WSL workspace layout
- local CLI administration for user creation, password reset, and deactivation
- health/readiness endpoints, structured JSON logs, and worker heartbeat persistence

Additional acceptance artifacts:
- [docs/acceptance_matrix.md](/workspace/docloop/triage-stage1/docs/acceptance_matrix.md)
- [docs/manual_verification.md](/workspace/docloop/triage-stage1/docs/manual_verification.md)

**Local Setup**

Create an isolated Python 3.12 environment and install the Stage 1 dependencies:

```bash
cd triage-stage1
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

**Environment**

Copy `.env.example` and provide all required values. Recommended defaults already match the PRD for:
- `UPLOADS_DIR=/opt/triage/data/uploads`
- `TRIAGE_WORKSPACE_DIR=/opt/triage/triage_workspace`
- `REPO_MOUNT_DIR=/opt/triage/triage_workspace/app`
- `MANUALS_MOUNT_DIR=/opt/triage/triage_workspace/manuals`
- `CODEX_TIMEOUT_SECONDS=75`
- `WORKER_POLL_SECONDS=10`

The repo and manuals mounts must exist and be readable before `/readyz` will report ready.

**Database**

Apply the Alembic schema before bootstrapping the workspace:

```bash
alembic upgrade head
```

**Bootstrap**

Run the bootstrap script after migrations and before starting the services:

```bash
python scripts/bootstrap_workspace.py
```

It creates or validates:
- the uploads directory
- the workspace root and `runs/`
- the workspace Git repository and initial empty commit
- the exact `AGENTS.md` and `.agents/skills/stage1-triage/SKILL.md`
- the `system_state.bootstrap_version` marker

**Management commands**

```bash
python scripts/create_admin.py --email admin@example.com --display-name "Admin User" --password "change-me"
python scripts/create_user.py --email requester@example.com --display-name "Requester User" --password "change-me" --role requester
python scripts/set_password.py --email requester@example.com --password "new-secret"
python scripts/deactivate_user.py --email requester@example.com
```

**Run**

Start the web app and worker in separate shells after the database, mounts, and workspace bootstrap are ready:

```bash
python scripts/run_web.py --host 0.0.0.0 --port 8000
python scripts/run_worker.py
```

Health endpoints:
- `GET /healthz` returns process liveness
- `GET /readyz` verifies database reachability plus uploads/workspace/mount/agent artifact readiness

**Acceptance Coverage**

- Automated regression coverage lives under `tests/` and now includes session behavior, requester isolation, upload validation limits, unread tracking, worker queue invariants, draft handling, and non-leak safeguards.
- AC1-AC19 traceability is captured in [docs/acceptance_matrix.md](/workspace/docloop/triage-stage1/docs/acceptance_matrix.md).
- A concise operator smoke test is captured in [docs/manual_verification.md](/workspace/docloop/triage-stage1/docs/manual_verification.md).

```
# End of file: README.md

# File: app/routes_auth.py
```python
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

```
# End of file: app/routes_auth.py

# File: app/routes_requester.py
```python
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.auth import (
    AuthContext,
    get_db_session,
    get_settings,
    get_templates,
    require_auth_context,
    require_requester,
    require_session_csrf,
    template_context,
)
from app.render import markdown_to_plain_text, markdown_to_safe_html
from app.uploads import (
    UploadValidationError,
    cleanup_written_uploads,
    persist_validated_uploads,
    validate_public_image_uploads,
)
from shared.models import AttachmentVisibility, MessageVisibility, Ticket, TicketAttachment, TicketMessage, TicketView, TicketStatus
from shared.permissions import PermissionDeniedError, ensure_dev_ti, ensure_requester_attachment_access
from shared.tickets import (
    add_requester_reply,
    create_requester_ticket,
    mark_ticket_resolved,
    upsert_ticket_view,
)


router = APIRouter()


REQUESTER_STATUS_LABELS = {
    TicketStatus.NEW.value: "Reviewing",
    TicketStatus.AI_TRIAGE.value: "Reviewing",
    TicketStatus.WAITING_ON_USER.value: "Waiting for your reply",
    TicketStatus.WAITING_ON_DEV_TI.value: "Waiting on team",
    TicketStatus.RESOLVED.value: "Resolved",
}


def requester_status_label(status: str) -> str:
    return REQUESTER_STATUS_LABELS.get(status, status.replace("_", " ").title())


def _get_owned_ticket_or_404(db: Session, *, reference: str, user_id) -> Ticket:
    ticket = db.scalar(
        select(Ticket).where(
            Ticket.reference == reference,
            Ticket.created_by_user_id == user_id,
        )
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def _build_ticket_thread(
    db: Session,
    *,
    ticket_id,
) -> list[dict[str, object]]:
    messages = db.scalars(
        select(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.visibility == MessageVisibility.PUBLIC.value,
        )
        .order_by(TicketMessage.created_at.asc(), TicketMessage.id.asc())
    ).all()
    message_ids = [message.id for message in messages]
    attachments_by_message: dict[object, list[TicketAttachment]] = defaultdict(list)
    if message_ids:
        attachments = db.scalars(
            select(TicketAttachment)
            .where(
                TicketAttachment.message_id.in_(message_ids),
                TicketAttachment.visibility == AttachmentVisibility.PUBLIC.value,
            )
            .order_by(TicketAttachment.created_at.asc(), TicketAttachment.id.asc())
        ).all()
        for attachment in attachments:
            attachments_by_message[attachment.message_id].append(attachment)

    rendered: list[dict[str, object]] = []
    for message in messages:
        author_label = "You" if message.author_type == "requester" else message.author_type.replace("_", " ").title()
        rendered.append(
            {
                "id": str(message.id),
                "author_label": author_label,
                "created_at": message.created_at,
                "body_html": markdown_to_safe_html(message.body_markdown),
                "attachments": attachments_by_message.get(message.id, []),
            }
        )
    return rendered


def _render_ticket_detail(
    request: Request,
    *,
    auth: AuthContext,
    db: Session,
    ticket: Ticket,
    error: str | None = None,
    reply_body: str = "",
):
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "tickets/detail.html",
        template_context(
            request,
            auth=auth,
            ticket=ticket,
            requester_status=requester_status_label(ticket.status),
            thread=_build_ticket_thread(db, ticket_id=ticket.id),
            error=error,
            reply_body=reply_body,
        ),
    )


@router.get("/app")
def requester_home(
    auth: AuthContext = Depends(require_requester),
):
    return RedirectResponse(url="/app/tickets", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/app/tickets")
def ticket_list(
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    templates = get_templates(request)
    rows = db.execute(
        select(Ticket, TicketView.last_viewed_at)
        .outerjoin(
            TicketView,
            and_(
                TicketView.ticket_id == Ticket.id,
                TicketView.user_id == auth.user.id,
            ),
        )
        .where(Ticket.created_by_user_id == auth.user.id)
        .order_by(Ticket.updated_at.desc(), Ticket.id.desc())
    ).all()

    tickets = []
    for ticket, last_viewed_at in rows:
        tickets.append(
            {
                "reference": ticket.reference,
                "title": ticket.title,
                "status": requester_status_label(ticket.status),
                "urgent": ticket.urgent,
                "updated": last_viewed_at is None or ticket.updated_at > last_viewed_at,
                "updated_at": ticket.updated_at,
            }
        )

    return templates.TemplateResponse(
        request,
        "tickets/list.html",
        template_context(request, auth=auth, tickets=tickets),
    )


@router.get("/app/tickets/new")
def new_ticket_page(
    request: Request,
    auth: AuthContext = Depends(require_requester),
):
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "tickets/new.html",
        template_context(
            request,
            auth=auth,
            title_value="",
            description_value="",
            urgent=False,
            error=None,
        ),
    )


@router.post("/app/tickets")
async def create_ticket_submit(
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    settings = get_settings(request)
    templates = get_templates(request)
    form = await request.form(
        max_files=settings.max_images_per_message,
        max_part_size=settings.max_image_bytes,
    )
    require_session_csrf(auth, str(form.get("csrf_token", "")))

    title = str(form.get("title", "")).strip()
    description_markdown = str(form.get("description", "")).strip()
    urgent = str(form.get("urgent", "")).lower() in {"1", "true", "on", "yes"}
    if not description_markdown:
        return templates.TemplateResponse(
            request,
            "tickets/new.html",
            template_context(
                request,
                auth=auth,
                title_value=title,
                description_value=description_markdown,
                urgent=urgent,
                error="Description is required.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validated_uploads = await validate_public_image_uploads(form, settings)
    except UploadValidationError as exc:
        return templates.TemplateResponse(
            request,
            "tickets/new.html",
            template_context(
                request,
                auth=auth,
                title_value=title,
                description_value=description_markdown,
                urgent=urgent,
                error=str(exc),
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    written_paths = []
    description_text = markdown_to_plain_text(description_markdown)
    try:
        ticket, message, _ = create_requester_ticket(
            db,
            creator=auth.user,
            title=title or None,
            description_markdown=description_markdown,
            description_text=description_text,
            urgent=urgent,
        )
        db.flush()
        attachments, written_paths = persist_validated_uploads(
            validated_uploads,
            uploads_dir=settings.uploads_dir,
            ticket_id=ticket.id,
            message_id=message.id,
        )
        for attachment in attachments:
            db.add(attachment)
        db.commit()
    except Exception:
        db.rollback()
        cleanup_written_uploads(written_paths)
        raise

    return RedirectResponse(
        url=f"/app/tickets/{ticket.reference}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/app/tickets/{reference}")
def ticket_detail(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    ticket = _get_owned_ticket_or_404(db, reference=reference, user_id=auth.user.id)
    upsert_ticket_view(db, user_id=auth.user.id, ticket_id=ticket.id)
    db.commit()
    return _render_ticket_detail(request, auth=auth, db=db, ticket=ticket)


@router.post("/app/tickets/{reference}/reply")
async def ticket_reply(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    settings = get_settings(request)
    form = await request.form(
        max_files=settings.max_images_per_message,
        max_part_size=settings.max_image_bytes,
    )
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_owned_ticket_or_404(db, reference=reference, user_id=auth.user.id)

    body_markdown = str(form.get("body", "")).strip()
    try:
        validated_uploads = await validate_public_image_uploads(form, settings)
    except UploadValidationError as exc:
        return _render_ticket_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error=str(exc),
            reply_body=body_markdown,
        )

    if not body_markdown and not validated_uploads:
        return _render_ticket_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Reply text or an image is required.",
            reply_body=body_markdown,
        )

    written_paths = []
    try:
        message, _ = add_requester_reply(
            db,
            ticket=ticket,
            requester=auth.user,
            body_markdown=body_markdown,
            body_text=markdown_to_plain_text(body_markdown) if body_markdown else "",
        )
        db.flush()
        attachments, written_paths = persist_validated_uploads(
            validated_uploads,
            uploads_dir=settings.uploads_dir,
            ticket_id=ticket.id,
            message_id=message.id,
        )
        for attachment in attachments:
            db.add(attachment)
        db.commit()
    except Exception:
        db.rollback()
        cleanup_written_uploads(written_paths)
        raise

    return RedirectResponse(
        url=f"/app/tickets/{ticket.reference}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/app/tickets/{reference}/resolve")
async def ticket_resolve(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_owned_ticket_or_404(db, reference=reference, user_id=auth.user.id)
    mark_ticket_resolved(
        db,
        ticket=ticket,
        user=auth.user,
        changed_by_type="requester",
    )
    db.commit()
    return RedirectResponse(
        url=f"/app/tickets/{ticket.reference}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/attachments/{attachment_id}")
def download_attachment(
    attachment_id: str,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_auth_context),
):
    try:
        attachment_uuid = uuid.UUID(attachment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found") from exc

    attachment = db.get(TicketAttachment, attachment_uuid)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    ticket = db.get(Ticket, attachment.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    try:
        if auth.user.role == "requester":
            ensure_requester_attachment_access(auth.user, ticket, attachment)
        else:
            ensure_dev_ti(auth.user)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(
        Path(attachment.stored_path),
        media_type=attachment.mime_type,
        filename=attachment.original_filename,
    )

```
# End of file: app/routes_requester.py

# File: app/uploads.py
```python
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import hashlib
import uuid

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from starlette.datastructures import FormData, UploadFile as StarletteUploadFile

from shared.config import Settings
from shared.models import AttachmentVisibility, TicketAttachment


ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
}


class UploadValidationError(ValueError):
    """Raised when an uploaded file violates Stage 1 rules."""


@dataclass(frozen=True)
class ValidatedImageUpload:
    attachment_id: uuid.UUID
    original_filename: str
    mime_type: str
    data: bytes
    sha256: str
    size_bytes: int
    width: int
    height: int
    suffix: str


def extract_upload_files(form: FormData, *, field_name: str = "attachments") -> list[UploadFile]:
    files: list[UploadFile] = []
    for value in form.getlist(field_name):
        if isinstance(value, (UploadFile, StarletteUploadFile)) and value.filename:
            files.append(value)
    return files


async def validate_public_image_uploads(
    form: FormData,
    settings: Settings,
    *,
    field_name: str = "attachments",
) -> list[ValidatedImageUpload]:
    files = extract_upload_files(form, field_name=field_name)
    if len(files) > settings.max_images_per_message:
        raise UploadValidationError(
            f"You can upload at most {settings.max_images_per_message} images per message."
        )

    validated: list[ValidatedImageUpload] = []
    for upload in files:
        mime_type = (upload.content_type or "").lower()
        suffix = ALLOWED_IMAGE_TYPES.get(mime_type)
        if suffix is None:
            raise UploadValidationError("Only PNG and JPEG images are allowed.")

        data = await upload.read()
        await upload.close()
        size_bytes = len(data)
        if size_bytes > settings.max_image_bytes:
            raise UploadValidationError(
                f"Each image must be {settings.max_image_bytes} bytes or smaller."
            )
        if size_bytes == 0:
            raise UploadValidationError("Uploaded images must not be empty.")

        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
            with Image.open(BytesIO(data)) as image:
                width, height = image.size
        except (UnidentifiedImageError, OSError) as exc:
            raise UploadValidationError("Uploaded files must be valid images.") from exc

        validated.append(
            ValidatedImageUpload(
                attachment_id=uuid.uuid4(),
                original_filename=upload.filename or "image",
                mime_type=mime_type,
                data=data,
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=size_bytes,
                width=width,
                height=height,
                suffix=suffix,
            )
        )
    return validated


def persist_validated_uploads(
    uploads: list[ValidatedImageUpload],
    *,
    uploads_dir: Path,
    ticket_id: uuid.UUID,
    message_id: uuid.UUID,
) -> tuple[list[TicketAttachment], list[Path]]:
    attachments: list[TicketAttachment] = []
    written_paths: list[Path] = []

    target_dir = uploads_dir / str(ticket_id) / str(message_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    for upload in uploads:
        stored_path = target_dir / f"{upload.attachment_id}{upload.suffix}"
        with stored_path.open("wb") as handle:
            handle.write(upload.data)
        written_paths.append(stored_path)
        attachments.append(
            TicketAttachment(
                id=upload.attachment_id,
                ticket_id=ticket_id,
                message_id=message_id,
                visibility=AttachmentVisibility.PUBLIC.value,
                original_filename=upload.original_filename,
                stored_path=str(stored_path),
                mime_type=upload.mime_type,
                sha256=upload.sha256,
                size_bytes=upload.size_bytes,
                width=upload.width,
                height=upload.height,
            )
        )
    return attachments, written_paths


def cleanup_written_uploads(paths: list[Path]) -> None:
    for path in reversed(paths):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue
        parent = path.parent
        while parent.name and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

```
# End of file: app/uploads.py

# File: app/auth.py
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from shared.config import Settings
from shared.models import SessionRecord, User, UserRole
from shared.security import (
    LOGIN_CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    generate_csrf_token,
    generate_login_csrf_token,
    generate_session_token,
    hash_token,
    session_expires_at,
    session_max_age,
    should_use_secure_cookies,
    utcnow,
    validate_login_csrf_token,
)


@dataclass
class AuthContext:
    user: User
    session_record: SessionRecord


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_templates(request: Request):
    return request.app.state.templates


def get_db_session(request: Request) -> Iterator[Session]:
    session_factory = get_session_factory(request)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _get_session_record(db: Session, raw_token: str | None) -> SessionRecord | None:
    if not raw_token:
        return None
    return db.scalar(
        select(SessionRecord).where(SessionRecord.token_hash == hash_token(raw_token))
    )


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_optional_auth_context(
    request: Request,
    db: Session = Depends(get_db_session),
) -> AuthContext | None:
    record = _get_session_record(db, request.cookies.get(SESSION_COOKIE_NAME))
    if record is None:
        return None
    if _normalize_datetime(record.expires_at) <= utcnow():
        return None

    user = db.scalar(
        select(User).where(
            User.id == record.user_id,
            User.is_active.is_(True),
        )
    )
    if user is None:
        return None
    return AuthContext(user=user, session_record=record)


def require_auth_context(
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> AuthContext:
    if auth is None:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return auth


def require_requester(
    auth: AuthContext = Depends(require_auth_context),
) -> AuthContext:
    if auth.user.role != UserRole.REQUESTER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requester access required")
    return auth


def require_dev_ti(
    auth: AuthContext = Depends(require_auth_context),
) -> AuthContext:
    if auth.user.role not in {UserRole.DEV_TI.value, UserRole.ADMIN.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dev/TI access required")
    return auth


def create_session(
    db: Session,
    *,
    user: User,
    settings: Settings,
    remember_me: bool,
    user_agent: str | None,
    ip_address: str | None,
    now: datetime | None = None,
) -> tuple[SessionRecord, str]:
    now = now or utcnow()
    raw_token = generate_session_token()
    record = SessionRecord(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        csrf_token=generate_csrf_token(),
        remember_me=remember_me,
        expires_at=session_expires_at(settings, remember_me=remember_me, now=now),
        last_seen_at=now,
        created_at=now,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    user.last_login_at = now
    db.add(record)
    db.flush()
    return record, raw_token


def set_session_cookie(
    response: Response,
    *,
    settings: Settings,
    raw_token: str,
    remember_me: bool,
) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        raw_token,
        httponly=True,
        secure=should_use_secure_cookies(settings),
        samesite="lax",
        max_age=session_max_age(settings, remember_me=remember_me),
        path="/",
    )


def clear_session_cookie(response: Response, *, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=should_use_secure_cookies(settings),
        samesite="lax",
    )


def issue_login_csrf(response: Response, settings: Settings) -> str:
    token = generate_login_csrf_token(settings.app_secret_key)
    response.set_cookie(
        LOGIN_CSRF_COOKIE_NAME,
        token,
        httponly=True,
        secure=should_use_secure_cookies(settings),
        samesite="lax",
        path="/",
    )
    return token


def clear_login_csrf(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        LOGIN_CSRF_COOKIE_NAME,
        path="/",
        secure=should_use_secure_cookies(settings),
        samesite="lax",
    )


def validate_login_csrf(request: Request, submitted_token: str, settings: Settings) -> bool:
    cookie_token = request.cookies.get(LOGIN_CSRF_COOKIE_NAME, "")
    if not submitted_token or submitted_token != cookie_token:
        return False
    return validate_login_csrf_token(settings.app_secret_key, submitted_token)


def require_session_csrf(auth: AuthContext, submitted_token: str) -> None:
    if not submitted_token or submitted_token != auth.session_record.csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def template_context(
    request: Request,
    *,
    auth: AuthContext | None,
    csrf_token: str | None = None,
    **extra: object,
) -> dict[str, object]:
    context: dict[str, object] = {
        "request": request,
        "current_user": auth.user if auth else None,
        "session_csrf_token": auth.session_record.csrf_token if auth else "",
        "csrf_token": csrf_token if csrf_token is not None else (auth.session_record.csrf_token if auth else ""),
    }
    context.update(extra)
    return context

```
# End of file: app/auth.py

# File: app/main.py
```python
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

```
# End of file: app/main.py

# File: app/__init__.py
```python
"""Web application package for later phases."""

```
# End of file: app/__init__.py

# File: app/render.py
```python
from __future__ import annotations

import re

import bleach
from markdown_it import MarkdownIt
from markupsafe import Markup


_MARKDOWN = MarkdownIt("commonmark", {"html": False})
_ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS).union(
    {"p", "pre", "code", "br", "ul", "ol", "li", "strong", "em", "blockquote"}
)
_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
}


def normalize_plain_text(text: str) -> str:
    collapsed = text.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = re.sub(r"[ \t]+", " ", collapsed)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def markdown_to_plain_text(markdown: str) -> str:
    rendered = _MARKDOWN.render(markdown or "")
    text = bleach.clean(rendered, tags=[], strip=True)
    return normalize_plain_text(text)


def markdown_to_safe_html(markdown: str) -> Markup:
    rendered = _MARKDOWN.render(markdown or "")
    sanitized = bleach.clean(
        rendered,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        strip=True,
    )
    linkified = bleach.linkify(sanitized)
    return Markup(linkified)

```
# End of file: app/render.py

# File: app/routes_ops.py
```python
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session

from app.auth import (
    AuthContext,
    get_db_session,
    get_templates,
    require_dev_ti,
    require_session_csrf,
    template_context,
)
from app.render import markdown_to_plain_text, markdown_to_safe_html
from shared.models import (
    AiDraft,
    AiDraftStatus,
    AiRun,
    AttachmentVisibility,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    Ticket,
    TicketAttachment,
    TicketClass,
    TicketMessage,
    TicketStatus,
    TicketView,
    User,
    UserRole,
)
from shared.permissions import ensure_dev_ti
from shared.tickets import (
    InvalidDraftStateError,
    add_internal_note,
    add_public_reply,
    approve_ai_draft,
    request_manual_rerun,
    reject_ai_draft,
    set_ticket_assignment,
    set_ticket_status_for_ops,
    upsert_ticket_view,
)


router = APIRouter()


OPS_STATUS_ORDER = [
    TicketStatus.NEW.value,
    TicketStatus.AI_TRIAGE.value,
    TicketStatus.WAITING_ON_USER.value,
    TicketStatus.WAITING_ON_DEV_TI.value,
    TicketStatus.RESOLVED.value,
]
OPS_STATUS_LABELS = {
    TicketStatus.NEW.value: "New",
    TicketStatus.AI_TRIAGE.value: "AI Triage",
    TicketStatus.WAITING_ON_USER.value: "Waiting on User",
    TicketStatus.WAITING_ON_DEV_TI.value: "Waiting on Dev/TI",
    TicketStatus.RESOLVED.value: "Resolved",
}
REPLY_STATUS_OPTIONS = [
    TicketStatus.WAITING_ON_USER.value,
    TicketStatus.WAITING_ON_DEV_TI.value,
    TicketStatus.RESOLVED.value,
]


def ops_status_label(value: str) -> str:
    return OPS_STATUS_LABELS.get(value, value.replace("_", " ").title())


def _parse_bool(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "on", "yes"}


def _get_ticket_or_404(db: Session, *, reference: str) -> Ticket:
    ticket = db.scalar(select(Ticket).where(Ticket.reference == reference))
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def _get_draft_or_404(db: Session, *, draft_id: str) -> AiDraft:
    try:
        draft_uuid = uuid.UUID(draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found") from exc
    draft = db.get(AiDraft, draft_uuid)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return draft


def _load_ops_users(db: Session) -> list[User]:
    return db.scalars(
        select(User)
        .where(
            User.is_active.is_(True),
            User.role.in_([UserRole.DEV_TI.value, UserRole.ADMIN.value]),
        )
        .order_by(User.display_name.asc(), User.email.asc())
    ).all()


def _build_thread(
    db: Session,
    *,
    ticket_id: uuid.UUID,
    visibility: str,
) -> list[dict[str, object]]:
    messages = db.scalars(
        select(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.visibility == visibility,
        )
        .order_by(TicketMessage.created_at.asc(), TicketMessage.id.asc())
    ).all()
    attachments_by_message: dict[uuid.UUID, list[TicketAttachment]] = defaultdict(list)
    message_ids = [message.id for message in messages]
    if message_ids:
        attachments = db.scalars(
            select(TicketAttachment)
            .where(
                TicketAttachment.message_id.in_(message_ids),
                TicketAttachment.visibility
                == (
                    AttachmentVisibility.PUBLIC.value
                    if visibility == MessageVisibility.PUBLIC.value
                    else AttachmentVisibility.INTERNAL.value
                ),
            )
            .order_by(TicketAttachment.created_at.asc(), TicketAttachment.id.asc())
        ).all()
        for attachment in attachments:
            attachments_by_message[attachment.message_id].append(attachment)

    rendered: list[dict[str, object]] = []
    for message in messages:
        author_label = "AI" if message.author_type == MessageAuthorType.AI.value else message.author_type.replace("_", " ").title()
        if message.author_type == MessageAuthorType.DEV_TI.value and message.author_user_id:
            author = db.get(User, message.author_user_id)
            if author is not None:
                author_label = author.display_name
        if message.author_type == MessageAuthorType.REQUESTER.value and message.author_user_id:
            author = db.get(User, message.author_user_id)
            if author is not None:
                author_label = author.display_name
        rendered.append(
            {
                "id": str(message.id),
                "author_label": author_label,
                "source_label": message.source.replace("_", " ").title(),
                "created_at": message.created_at,
                "body_html": markdown_to_safe_html(message.body_markdown),
                "attachments": attachments_by_message.get(message.id, []),
            }
        )
    return rendered


def _load_relevant_paths(latest_run: AiRun | None) -> list[dict[str, str]]:
    if latest_run is None or not latest_run.final_output_path:
        return []
    output_path = Path(latest_run.final_output_path)
    if not output_path.exists():
        return []
    try:
        payload = json.loads(output_path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    relevant_paths = payload.get("relevant_paths")
    if not isinstance(relevant_paths, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in relevant_paths:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        reason = item.get("reason")
        if isinstance(path, str) and isinstance(reason, str):
            normalized.append({"path": path, "reason": reason})
    return normalized


def _load_ops_detail_context(db: Session, *, ticket: Ticket) -> dict[str, object]:
    creator = db.get(User, ticket.created_by_user_id)
    assignee = db.get(User, ticket.assigned_to_user_id) if ticket.assigned_to_user_id else None
    latest_ai_note = db.scalar(
        select(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket.id,
            TicketMessage.visibility == MessageVisibility.INTERNAL.value,
            TicketMessage.author_type == MessageAuthorType.AI.value,
            TicketMessage.source == MessageSource.AI_INTERNAL_NOTE.value,
        )
        .order_by(TicketMessage.created_at.desc(), TicketMessage.id.desc())
    )
    latest_run = db.scalar(
        select(AiRun)
        .where(AiRun.ticket_id == ticket.id)
        .order_by(AiRun.created_at.desc(), AiRun.id.desc())
    )
    pending_draft = db.scalar(
        select(AiDraft)
        .where(
            AiDraft.ticket_id == ticket.id,
            AiDraft.status == AiDraftStatus.PENDING_APPROVAL.value,
        )
        .order_by(AiDraft.created_at.desc(), AiDraft.id.desc())
    )
    latest_draft = db.scalar(
        select(AiDraft)
        .where(AiDraft.ticket_id == ticket.id)
        .order_by(AiDraft.created_at.desc(), AiDraft.id.desc())
    )
    return {
        "ticket": ticket,
        "creator": creator,
        "assignee": assignee,
        "public_thread": _build_thread(db, ticket_id=ticket.id, visibility=MessageVisibility.PUBLIC.value),
        "internal_thread": _build_thread(db, ticket_id=ticket.id, visibility=MessageVisibility.INTERNAL.value),
        "latest_ai_note_html": (
            markdown_to_safe_html(latest_ai_note.body_markdown) if latest_ai_note is not None else None
        ),
        "latest_ai_note_at": latest_ai_note.created_at if latest_ai_note is not None else None,
        "latest_run": latest_run,
        "relevant_paths": _load_relevant_paths(latest_run),
        "pending_draft": pending_draft,
        "pending_draft_html": (
            markdown_to_safe_html(pending_draft.body_markdown) if pending_draft is not None else None
        ),
        "latest_draft": latest_draft,
        "ops_users": _load_ops_users(db),
        "reply_status_options": [(value, ops_status_label(value)) for value in REPLY_STATUS_OPTIONS],
        "status_options": [(value, ops_status_label(value)) for value in OPS_STATUS_ORDER],
    }


def _render_ops_detail(
    request: Request,
    *,
    auth: AuthContext,
    db: Session,
    ticket: Ticket,
    error: str | None = None,
    public_reply_body: str = "",
    internal_note_body: str = "",
    next_status: str | None = None,
):
    templates = get_templates(request)
    context = _load_ops_detail_context(db, ticket=ticket)
    context.update(
        {
            "error": error,
            "public_reply_body": public_reply_body,
            "internal_note_body": internal_note_body,
            "selected_next_status": next_status or TicketStatus.WAITING_ON_USER.value,
        }
    )
    return templates.TemplateResponse(
        request,
        "ops/detail.html",
        template_context(request, auth=auth, **context),
        status_code=status.HTTP_400_BAD_REQUEST if error else status.HTTP_200_OK,
    )


def _selected_filters(request: Request) -> dict[str, str]:
    return {
        "status": request.query_params.get("status", ""),
        "ticket_class": request.query_params.get("ticket_class", ""),
        "assigned_to": request.query_params.get("assigned_to", ""),
        "urgent": request.query_params.get("urgent", ""),
        "unassigned_only": request.query_params.get("unassigned_only", ""),
        "created_by_me": request.query_params.get("created_by_me", ""),
        "needs_approval": request.query_params.get("needs_approval", ""),
        "updated_since_my_last_view": request.query_params.get("updated_since_my_last_view", ""),
    }


def _board_rows(db: Session, *, auth: AuthContext, filters: dict[str, str]) -> list[dict[str, object]]:
    last_viewed_at = TicketView.last_viewed_at.label("last_viewed_at")
    needs_approval = exists(
        select(1).where(
            AiDraft.ticket_id == Ticket.id,
            AiDraft.status == AiDraftStatus.PENDING_APPROVAL.value,
        )
    )
    query = (
        select(Ticket, User.display_name.label("creator_name"), last_viewed_at, needs_approval.label("needs_approval"))
        .join(User, User.id == Ticket.created_by_user_id)
        .outerjoin(
            TicketView,
            and_(TicketView.ticket_id == Ticket.id, TicketView.user_id == auth.user.id),
        )
    )

    if filters["status"]:
        query = query.where(Ticket.status == filters["status"])
    if filters["ticket_class"]:
        query = query.where(Ticket.ticket_class == filters["ticket_class"])
    if filters["assigned_to"]:
        try:
            assigned_uuid = uuid.UUID(filters["assigned_to"])
        except ValueError:
            assigned_uuid = None
        if assigned_uuid is not None:
            query = query.where(Ticket.assigned_to_user_id == assigned_uuid)
    if _parse_bool(filters["urgent"]):
        query = query.where(Ticket.urgent.is_(True))
    if _parse_bool(filters["unassigned_only"]):
        query = query.where(Ticket.assigned_to_user_id.is_(None))
    if _parse_bool(filters["created_by_me"]):
        query = query.where(Ticket.created_by_user_id == auth.user.id)
    if _parse_bool(filters["needs_approval"]):
        query = query.where(needs_approval)
    if _parse_bool(filters["updated_since_my_last_view"]):
        query = query.where(
            sa.or_(TicketView.last_viewed_at.is_(None), Ticket.updated_at > TicketView.last_viewed_at)
        )

    query = query.order_by(Ticket.updated_at.desc(), Ticket.id.desc())
    rows = db.execute(query).all()

    assignee_ids = {ticket.assigned_to_user_id for ticket, _, _, _ in rows if ticket.assigned_to_user_id}
    assignees = {
        user.id: user.display_name
        for user in db.scalars(select(User).where(User.id.in_(assignee_ids))).all()
    }
    rendered: list[dict[str, object]] = []
    for ticket, creator_name, viewed_at, has_pending_draft in rows:
        rendered.append(
            {
                "reference": ticket.reference,
                "title": ticket.title,
                "status": ticket.status,
                "status_label": ops_status_label(ticket.status),
                "creator_name": creator_name,
                "assignee_name": assignees.get(ticket.assigned_to_user_id),
                "ticket_class": ticket.ticket_class or "unclassified",
                "urgent": ticket.urgent,
                "needs_approval": bool(has_pending_draft),
                "updated": viewed_at is None or ticket.updated_at > viewed_at,
                "updated_at": ticket.updated_at,
            }
        )
    return rendered


@router.get("/ops")
def ops_home(auth: AuthContext = Depends(require_dev_ti)):
    return RedirectResponse(url="/ops/board", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/ops/board")
def ops_board(
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    templates = get_templates(request)
    filters = _selected_filters(request)
    rows = _board_rows(db, auth=auth, filters=filters)
    columns: list[dict[str, object]] = []
    for status_value in OPS_STATUS_ORDER:
        items = [row for row in rows if row["status"] == status_value]
        columns.append(
            {
                "status": status_value,
                "label": ops_status_label(status_value),
                "tickets": items,
            }
        )
    return templates.TemplateResponse(
        request,
        "ops/board.html",
        template_context(
            request,
            auth=auth,
            columns=columns,
            filters=filters,
            ticket_class_options=[item.value for item in TicketClass],
            assignee_options=_load_ops_users(db),
        ),
    )


@router.get("/ops/tickets/{reference}")
def ops_ticket_detail(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    ticket = _get_ticket_or_404(db, reference=reference)
    upsert_ticket_view(db, user_id=auth.user.id, ticket_id=ticket.id)
    db.commit()
    return _render_ops_detail(request, auth=auth, db=db, ticket=ticket)


@router.post("/ops/tickets/{reference}/assign")
async def assign_ticket(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    raw_assignee = str(form.get("assigned_to_user_id", "")).strip()
    assigned_to_user_id: uuid.UUID | None = None
    if raw_assignee:
        try:
            assigned_to_user_id = uuid.UUID(raw_assignee)
        except ValueError:
            return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error="Invalid assignee.")
        assignee = db.get(User, assigned_to_user_id)
        if assignee is None:
            return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error="Assignee not found.")
        try:
            ensure_dev_ti(assignee)
        except ValueError:
            return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error="Assignee must be a Dev/TI or admin user.")
    set_ticket_assignment(db, ticket=ticket, assigned_to_user_id=assigned_to_user_id, actor=auth.user)
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/tickets/{reference}/set-status")
async def set_status(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    target_status = str(form.get("status", "")).strip()
    if target_status not in OPS_STATUS_LABELS:
        return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error="Invalid status.")
    set_ticket_status_for_ops(db, ticket=ticket, actor=auth.user, to_status=target_status)
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/tickets/{reference}/reply-public")
async def reply_public(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    body_markdown = str(form.get("body", "")).strip()
    next_status = str(form.get("next_status", "")).strip()
    if not body_markdown:
        return _render_ops_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Public reply text is required.",
            public_reply_body=body_markdown,
            next_status=next_status,
        )
    if next_status not in REPLY_STATUS_OPTIONS:
        return _render_ops_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Choose the next public status.",
            public_reply_body=body_markdown,
            next_status=next_status,
        )
    add_public_reply(
        db,
        ticket=ticket,
        actor=auth.user,
        body_markdown=body_markdown,
        body_text=markdown_to_plain_text(body_markdown),
        next_status=next_status,
    )
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/tickets/{reference}/note-internal")
async def note_internal(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    body_markdown = str(form.get("body", "")).strip()
    if not body_markdown:
        return _render_ops_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Internal note text is required.",
            internal_note_body=body_markdown,
        )
    add_internal_note(
        db,
        ticket=ticket,
        actor=auth.user,
        body_markdown=body_markdown,
        body_text=markdown_to_plain_text(body_markdown),
    )
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/tickets/{reference}/rerun-ai")
async def rerun_ai(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    request_manual_rerun(db, ticket=ticket, actor=auth.user)
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/drafts/{draft_id}/approve-publish")
async def approve_draft_publish(
    draft_id: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    draft = _get_draft_or_404(db, draft_id=draft_id)
    ticket = db.get(Ticket, draft.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    next_status = str(form.get("next_status", "")).strip()
    if next_status not in REPLY_STATUS_OPTIONS:
        return _render_ops_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Choose the next public status before publishing the draft.",
            next_status=next_status,
        )
    try:
        approve_ai_draft(db, ticket=ticket, draft=draft, actor=auth.user, next_status=next_status)
    except InvalidDraftStateError as exc:
        return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error=str(exc))
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/drafts/{draft_id}/reject")
async def reject_draft(
    draft_id: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    draft = _get_draft_or_404(db, draft_id=draft_id)
    ticket = db.get(Ticket, draft.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    try:
        reject_ai_draft(db, ticket=ticket, draft=draft, actor=auth.user)
    except InvalidDraftStateError as exc:
        return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error=str(exc))
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)

```
# End of file: app/routes_ops.py

# File: app/templates/login.html
```html
{% extends "base.html" %}

{% block title %}Login{% endblock %}

{% block content %}
<section class="panel narrow">
  <h1>Sign in</h1>
  {% if error %}
  <p class="alert">{{ error }}</p>
  {% endif %}

  {% if current_user and current_user.role != "requester" %}
  <p>Signed in as <strong>{{ current_user.display_name }}</strong>.</p>
  <p>The Dev/TI surface is deferred to Phase 3, so only the requester flow is available in this phase.</p>
  {% elif not current_user %}
  <form method="post" action="/login" class="stack">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <label>
      <span>Email</span>
      <input type="email" name="email" autocomplete="username" required>
    </label>
    <label>
      <span>Password</span>
      <input type="password" name="password" autocomplete="current-password" required>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="remember_me">
      <span>Remember me</span>
    </label>
    <button type="submit" class="button">Log in</button>
  </form>
  {% endif %}

  {% if ops_pending %}
  <p class="note">Login succeeded, but the Dev/TI UI is intentionally deferred to Phase 3.</p>
  {% endif %}
</section>
{% endblock %}

```
# End of file: app/templates/login.html

# File: app/templates/base.html
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Stage 1 Triage{% endblock %}</title>
    <link rel="stylesheet" href="{{ request.url_for('static', path='styles.css') }}">
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
  </head>
  <body>
    <header class="site-header">
      <div>
        <a class="brand" href="{% if current_user and current_user.role != 'requester' %}/ops{% else %}/app{% endif %}">Stage 1 Triage</a>
      </div>
      {% if current_user %}
      <div class="header-actions">
        <nav class="header-nav">
          {% if current_user.role == "requester" %}
          <a href="/app/tickets">My tickets</a>
          <a href="/app/tickets/new">New ticket</a>
          {% else %}
          <a href="/ops/board">Ops board</a>
          {% endif %}
        </nav>
        <span class="user-chip">{{ current_user.display_name }}</span>
        <form method="post" action="/logout">
          <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
          <button type="submit" class="button button-secondary">Log out</button>
        </form>
      </div>
      {% endif %}
    </header>
    <main class="page-shell">
      {% block content %}{% endblock %}
    </main>
  </body>
</html>

```
# End of file: app/templates/base.html

# File: app/templates/ops/board.html
```html
{% extends "base.html" %}

{% block title %}Ops Board{% endblock %}

{% block content %}
<section class="page-head">
  <div>
    <p class="note">Dev/TI queue</p>
    <h1>Ops board</h1>
  </div>
</section>

<section class="panel wide">
  <form method="get" action="/ops/board" class="filter-grid">
    <label>
      <span>Status</span>
      <select name="status">
        <option value="">All statuses</option>
        {% for column in columns %}
        <option value="{{ column.status }}" {% if filters.status == column.status %}selected{% endif %}>{{ column.label }}</option>
        {% endfor %}
      </select>
    </label>
    <label>
      <span>Class</span>
      <select name="ticket_class">
        <option value="">All classes</option>
        {% for item in ticket_class_options %}
        <option value="{{ item }}" {% if filters.ticket_class == item %}selected{% endif %}>{{ item }}</option>
        {% endfor %}
      </select>
    </label>
    <label>
      <span>Assigned to</span>
      <select name="assigned_to">
        <option value="">Anyone</option>
        {% for user in assignee_options %}
        <option value="{{ user.id }}" {% if filters.assigned_to == (user.id|string) %}selected{% endif %}>{{ user.display_name }}</option>
        {% endfor %}
      </select>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="urgent" value="1" {% if filters.urgent %}checked{% endif %}>
      <span>Urgent only</span>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="unassigned_only" value="1" {% if filters.unassigned_only %}checked{% endif %}>
      <span>Unassigned only</span>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="created_by_me" value="1" {% if filters.created_by_me %}checked{% endif %}>
      <span>Created by me</span>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="needs_approval" value="1" {% if filters.needs_approval %}checked{% endif %}>
      <span>Needs approval</span>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="updated_since_my_last_view" value="1" {% if filters.updated_since_my_last_view %}checked{% endif %}>
      <span>Updated since my last view</span>
    </label>
    <div class="form-actions">
      <button type="submit" class="button">Apply filters</button>
      <a href="/ops/board" class="button button-secondary">Clear</a>
    </div>
  </form>
</section>

<section class="ops-board">
  {% for column in columns %}
  <section class="panel board-column">
    <div class="board-column-head">
      <h2>{{ column.label }}</h2>
      <span class="badge">{{ column.tickets|length }}</span>
    </div>
    <div class="board-cards">
      {% if column.tickets %}
        {% for ticket in column.tickets %}
        <article class="board-card">
          <div class="ticket-meta">
            <span class="note">{{ ticket.reference }}</span>
            {% if ticket.updated %}<span class="badge badge-updated">Updated</span>{% endif %}
          </div>
          <h3><a href="/ops/tickets/{{ ticket.reference }}">{{ ticket.title }}</a></h3>
          <p class="note">Created by {{ ticket.creator_name }}</p>
          <div class="ticket-meta">
            <span class="badge">{{ ticket.ticket_class }}</span>
            {% if ticket.urgent %}<span class="badge badge-urgent">Urgent</span>{% endif %}
            {% if ticket.needs_approval %}<span class="badge">Needs approval</span>{% endif %}
          </div>
          <p class="note">
            {% if ticket.assignee_name %}Assigned to {{ ticket.assignee_name }}{% else %}Unassigned{% endif %}
          </p>
          <p class="note">Updated {{ ticket.updated_at.strftime("%Y-%m-%d %H:%M UTC") }}</p>
        </article>
        {% endfor %}
      {% else %}
      <p class="note">No tickets match this column.</p>
      {% endif %}
    </div>
  </section>
  {% endfor %}
</section>
{% endblock %}

```
# End of file: app/templates/ops/board.html

# File: app/templates/ops/detail.html
```html
{% extends "base.html" %}

{% block title %}{{ ticket.reference }}{% endblock %}

{% block content %}
<section class="page-head">
  <div>
    <p class="note">{{ ticket.reference }}</p>
    <h1>{{ ticket.title }}</h1>
    <div class="ticket-meta">
      <span class="badge">{{ ticket.status.replace("_", " ").title() }}</span>
      {% if ticket.urgent %}<span class="badge badge-urgent">Urgent</span>{% endif %}
      {% if pending_draft %}<span class="badge">Draft pending approval</span>{% endif %}
    </div>
  </div>
  <form method="post" action="/ops/tickets/{{ ticket.reference }}/rerun-ai">
    <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
    <button type="submit" class="button button-secondary">Rerun AI</button>
  </form>
</section>

{% if error %}
<p class="alert">{{ error }}</p>
{% endif %}

<section class="ops-layout">
  <div class="ops-main">
    <section class="panel wide">
      <h2>Ticket header</h2>
      <dl class="meta-grid">
        <div><dt>Requester</dt><dd>{{ creator.display_name if creator else "Unknown" }}</dd></div>
        <div><dt>Assignee</dt><dd>{{ assignee.display_name if assignee else "Unassigned" }}</dd></div>
        <div><dt>Class</dt><dd>{{ ticket.ticket_class or "unknown" }}</dd></div>
        <div><dt>Impact</dt><dd>{{ ticket.impact_level or "unknown" }}</dd></div>
        <div><dt>Confidence</dt><dd>{{ ticket.ai_confidence if ticket.ai_confidence is not none else "n/a" }}</dd></div>
        <div><dt>Development needed</dt><dd>{{ ticket.development_needed if ticket.development_needed is not none else "unknown" }}</dd></div>
        <div><dt>Last AI action</dt><dd>{{ ticket.last_ai_action or "n/a" }}</dd></div>
        <div><dt>Requester language</dt><dd>{{ ticket.requester_language or "n/a" }}</dd></div>
      </dl>
    </section>

    <section class="panel wide">
      <h2>Public thread</h2>
      <div class="thread">
        {% if public_thread %}
          {% for message in public_thread %}
          <article class="message-card">
            <div class="message-head">
              <strong>{{ message.author_label }}</strong>
              <span class="note">{{ message.source_label }}</span>
              <span class="timestamp">{{ message.created_at.strftime("%Y-%m-%d %H:%M UTC") }}</span>
            </div>
            <div class="message-body">{{ message.body_html }}</div>
            {% if message.attachments %}
            <ul class="attachment-list">
              {% for attachment in message.attachments %}
              <li><a href="/attachments/{{ attachment.id }}">{{ attachment.original_filename }}</a></li>
              {% endfor %}
            </ul>
            {% endif %}
          </article>
          {% endfor %}
        {% else %}
        <p class="note">No public messages yet.</p>
        {% endif %}
      </div>
    </section>

    <section class="panel wide">
      <h2>Internal thread</h2>
      <div class="thread">
        {% if internal_thread %}
          {% for message in internal_thread %}
          <article class="message-card">
            <div class="message-head">
              <strong>{{ message.author_label }}</strong>
              <span class="note">{{ message.source_label }}</span>
              <span class="timestamp">{{ message.created_at.strftime("%Y-%m-%d %H:%M UTC") }}</span>
            </div>
            <div class="message-body">{{ message.body_html }}</div>
          </article>
          {% endfor %}
        {% else %}
        <p class="note">No internal notes yet.</p>
        {% endif %}
      </div>
    </section>
  </div>

  <aside class="ops-sidebar">
    <section class="panel wide">
      <h2>Assignment</h2>
      <form method="post" action="/ops/tickets/{{ ticket.reference }}/assign" class="stack">
        <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
        <label>
          <span>Assigned to</span>
          <select name="assigned_to_user_id">
            <option value="">Unassigned</option>
            {% for user in ops_users %}
            <option value="{{ user.id }}" {% if assignee and assignee.id == user.id %}selected{% endif %}>{{ user.display_name }}</option>
            {% endfor %}
          </select>
        </label>
        <button type="submit" class="button">Save assignment</button>
      </form>
    </section>

    <section class="panel wide">
      <h2>Status</h2>
      <form method="post" action="/ops/tickets/{{ ticket.reference }}/set-status" class="stack">
        <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
        <label>
          <span>Current state</span>
          <select name="status">
            {% for value, label in status_options %}
            <option value="{{ value }}" {% if ticket.status == value %}selected{% endif %}>{{ label }}</option>
            {% endfor %}
          </select>
        </label>
        <button type="submit" class="button">Update status</button>
      </form>
    </section>

    <section class="panel wide">
      <h2>AI analysis</h2>
      {% if latest_ai_note_html %}
      <div class="message-body">{{ latest_ai_note_html }}</div>
      <p class="note">Generated {{ latest_ai_note_at.strftime("%Y-%m-%d %H:%M UTC") }}</p>
      {% else %}
      <p class="note">No internal AI summary has been recorded yet.</p>
      {% endif %}
      {% if latest_run %}
      <p class="note">Latest run: {{ latest_run.status }}{% if latest_run.model_name %} via {{ latest_run.model_name }}{% endif %}</p>
      {% endif %}
    </section>

    <section class="panel wide">
      <h2>Relevant repo/docs paths</h2>
      {% if relevant_paths %}
      <ul class="path-list">
        {% for item in relevant_paths %}
        <li><code>{{ item.path }}</code> <span class="note">{{ item.reason }}</span></li>
        {% endfor %}
      </ul>
      {% else %}
      <p class="note">No relevant paths have been captured yet.</p>
      {% endif %}
    </section>

    <section class="panel wide">
      <h2>Public draft</h2>
      {% if pending_draft %}
      <div class="message-body">{{ pending_draft_html }}</div>
      <div class="split-actions">
        <form method="post" action="/ops/drafts/{{ pending_draft.id }}/approve-publish" class="stack">
          <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
          <label>
            <span>Next status</span>
            <select name="next_status">
              {% for value, label in reply_status_options %}
              <option value="{{ value }}" {% if selected_next_status == value %}selected{% endif %}>{{ label }}</option>
              {% endfor %}
            </select>
          </label>
          <button type="submit" class="button">Approve and publish</button>
        </form>
        <form method="post" action="/ops/drafts/{{ pending_draft.id }}/reject">
          <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
          <button type="submit" class="button button-secondary">Reject</button>
        </form>
      </div>
      {% elif latest_draft %}
      <p class="note">Latest draft status: {{ latest_draft.status }}</p>
      {% else %}
      <p class="note">No AI draft is waiting for review.</p>
      {% endif %}
    </section>

    <section class="panel wide">
      <h2>Public reply</h2>
      <form method="post" action="/ops/tickets/{{ ticket.reference }}/reply-public" class="stack">
        <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
        <label>
          <span>Message</span>
          <textarea name="body" rows="6">{{ public_reply_body }}</textarea>
        </label>
        <label>
          <span>Next status</span>
          <select name="next_status">
            {% for value, label in reply_status_options %}
            <option value="{{ value }}" {% if selected_next_status == value %}selected{% endif %}>{{ label }}</option>
            {% endfor %}
          </select>
        </label>
        <button type="submit" class="button">Send public reply</button>
      </form>
    </section>

    <section class="panel wide">
      <h2>Internal note</h2>
      <form method="post" action="/ops/tickets/{{ ticket.reference }}/note-internal" class="stack">
        <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
        <label>
          <span>Note</span>
          <textarea name="body" rows="5">{{ internal_note_body }}</textarea>
        </label>
        <button type="submit" class="button button-secondary">Save internal note</button>
      </form>
    </section>
  </aside>
</section>
{% endblock %}

```
# End of file: app/templates/ops/detail.html

# File: app/templates/tickets/detail.html
```html
{% extends "base.html" %}

{% block title %}{{ ticket.reference }}{% endblock %}

{% block content %}
<section class="page-head">
  <div>
    <p class="note">{{ ticket.reference }}</p>
    <h1>{{ ticket.title }}</h1>
    <div class="ticket-meta">
      <span class="badge">{{ requester_status }}</span>
      {% if ticket.urgent %}<span class="badge badge-urgent">Urgent</span>{% endif %}
    </div>
  </div>
  {% if ticket.status != "resolved" %}
  <form method="post" action="/app/tickets/{{ ticket.reference }}/resolve">
    <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
    <button type="submit" class="button button-secondary">Mark resolved</button>
  </form>
  {% endif %}
</section>

{% if error %}
<p class="alert">{{ error }}</p>
{% endif %}

<section class="thread">
  {% for message in thread %}
  <article class="panel message-card">
    <div class="message-head">
      <strong>{{ message.author_label }}</strong>
      <span class="timestamp">{{ message.created_at.strftime("%Y-%m-%d %H:%M UTC") }}</span>
    </div>
    <div class="message-body">{{ message.body_html }}</div>
    {% if message.attachments %}
    <ul class="attachment-list">
      {% for attachment in message.attachments %}
      <li>
        <a href="/attachments/{{ attachment.id }}">{{ attachment.original_filename }}</a>
        <span class="note">({{ attachment.mime_type }}, {{ attachment.size_bytes }} bytes)</span>
      </li>
      {% endfor %}
    </ul>
    {% endif %}
  </article>
  {% endfor %}
</section>

<section class="panel wide">
  <h2>Reply</h2>
  <form method="post" action="/app/tickets/{{ ticket.reference }}/reply" enctype="multipart/form-data" class="stack">
    <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
    <label>
      <span>Message</span>
      <textarea name="body" rows="6">{{ reply_body }}</textarea>
    </label>
    <label>
      <span>Images</span>
      <input type="file" name="attachments" accept="image/png,image/jpeg" multiple>
    </label>
    <button type="submit" class="button">Send reply</button>
  </form>
</section>
{% endblock %}

```
# End of file: app/templates/tickets/detail.html

# File: app/templates/tickets/list.html
```html
{% extends "base.html" %}

{% block title %}My Tickets{% endblock %}

{% block content %}
<section class="page-head">
  <div>
    <h1>My tickets</h1>
    <p class="note">Public thread view only. Internal analysis stays on the Dev/TI side.</p>
  </div>
  <a class="button" href="/app/tickets/new">New ticket</a>
</section>

<section class="panel">
  {% if tickets %}
  <ul class="ticket-list">
    {% for ticket in tickets %}
    <li class="ticket-row">
      <div>
        <a class="ticket-link" href="/app/tickets/{{ ticket.reference }}">{{ ticket.reference }}</a>
        <div class="ticket-title">{{ ticket.title }}</div>
      </div>
      <div class="ticket-meta">
        <span class="badge">{{ ticket.status }}</span>
        {% if ticket.urgent %}<span class="badge badge-urgent">Urgent</span>{% endif %}
        {% if ticket.updated %}<span class="badge badge-updated">Updated</span>{% endif %}
        <span class="timestamp">{{ ticket.updated_at.strftime("%Y-%m-%d %H:%M UTC") }}</span>
      </div>
    </li>
    {% endfor %}
  </ul>
  {% else %}
  <p>No tickets yet.</p>
  {% endif %}
</section>
{% endblock %}

```
# End of file: app/templates/tickets/list.html

# File: app/templates/tickets/new.html
```html
{% extends "base.html" %}

{% block title %}New Ticket{% endblock %}

{% block content %}
<section class="panel wide">
  <h1>Open a ticket</h1>
  {% if error %}
  <p class="alert">{{ error }}</p>
  {% endif %}
  <form method="post" action="/app/tickets" enctype="multipart/form-data" class="stack">
    <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
    <label>
      <span>Short title</span>
      <input type="text" name="title" maxlength="120" value="{{ title_value }}">
    </label>
    <label>
      <span>Description</span>
      <textarea name="description" rows="10" required>{{ description_value }}</textarea>
    </label>
    <label>
      <span>Images</span>
      <input type="file" name="attachments" accept="image/png,image/jpeg" multiple>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="urgent" {% if urgent %}checked{% endif %}>
      <span>Mark as urgent</span>
    </label>
    <div class="form-actions">
      <a class="button button-secondary" href="/app/tickets">Cancel</a>
      <button type="submit" class="button">Create ticket</button>
    </div>
  </form>
</section>
{% endblock %}

```
# End of file: app/templates/tickets/new.html

# File: app/static/styles.css
```css
body {
  margin: 0;
  font-family: "Segoe UI", Helvetica, Arial, sans-serif;
  background: linear-gradient(180deg, #f4efe6 0%, #fbfaf7 100%);
  color: #1f1f1f;
}

a {
  color: #9a3412;
}

.site-header,
.page-shell,
.page-head,
.ticket-row,
.ticket-meta,
.header-actions,
.header-nav,
.message-head,
.form-actions,
.split-actions,
.board-column-head {
  display: flex;
  gap: 1rem;
}

.site-header,
.page-head,
.ticket-row,
.message-head {
  align-items: center;
  justify-content: space-between;
}

.site-header {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #d9cdb7;
  background: rgba(255, 251, 245, 0.95);
  position: sticky;
  top: 0;
}

.brand {
  font-weight: 700;
  text-decoration: none;
}

.page-shell {
  flex-direction: column;
  max-width: 960px;
  margin: 0 auto;
  padding: 1.5rem;
}

.header-nav {
  align-items: center;
}

.header-nav a {
  text-decoration: none;
}

.panel {
  background: white;
  border: 1px solid #e6dcc8;
  border-radius: 16px;
  padding: 1.25rem;
  box-shadow: 0 10px 30px rgba(71, 45, 7, 0.06);
}

.panel.narrow {
  max-width: 420px;
}

.panel.wide {
  width: 100%;
}

.stack {
  display: grid;
  gap: 1rem;
}

label span {
  display: block;
  font-weight: 600;
  margin-bottom: 0.35rem;
}

input[type="email"],
input[type="password"],
input[type="text"],
textarea,
select {
  width: 100%;
  box-sizing: border-box;
  padding: 0.8rem;
  border-radius: 10px;
  border: 1px solid #cfbf9f;
  background: #fffdf8;
}

.checkbox {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.button {
  border: none;
  border-radius: 999px;
  padding: 0.75rem 1rem;
  background: #9a3412;
  color: white;
  font-weight: 700;
  cursor: pointer;
  text-decoration: none;
}

.button-secondary {
  background: #57534e;
}

.badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #f3e8d3;
  padding: 0.3rem 0.7rem;
  font-size: 0.9rem;
}

.badge-urgent {
  background: #fee2e2;
  color: #991b1b;
}

.badge-updated {
  background: #dcfce7;
  color: #166534;
}

.alert {
  padding: 0.85rem 1rem;
  border-radius: 12px;
  background: #fee2e2;
  color: #991b1b;
}

.note,
.timestamp {
  color: #6b7280;
}

.ticket-list,
.attachment-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.ticket-row {
  padding: 1rem 0;
  border-bottom: 1px solid #eee2cf;
}

.ticket-row:last-child {
  border-bottom: 0;
}

.ticket-link {
  font-weight: 700;
}

.ticket-title {
  margin-top: 0.3rem;
}

.thread {
  display: grid;
  gap: 1rem;
}

.filter-grid,
.meta-grid {
  display: grid;
  gap: 1rem;
}

.filter-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.meta-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.meta-grid dt {
  color: #6b7280;
  font-size: 0.9rem;
}

.meta-grid dd {
  margin: 0.3rem 0 0;
  font-weight: 600;
}

.ops-board {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.board-column,
.board-cards,
.ops-main,
.ops-sidebar,
.ops-layout {
  display: grid;
  gap: 1rem;
}

.board-card {
  border: 1px solid #eee2cf;
  border-radius: 14px;
  padding: 1rem;
  background: #fffdfa;
}

.ops-layout {
  grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
  align-items: start;
}

.path-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.6rem;
}

.message-card {
  display: grid;
  gap: 0.75rem;
}

.message-body p:first-child {
  margin-top: 0;
}

@media (max-width: 720px) {
  .site-header,
  .page-head,
  .ticket-row,
  .header-actions,
  .header-nav,
  .form-actions,
  .split-actions,
  .message-head {
    flex-direction: column;
    align-items: stretch;
  }

  .ops-layout {
    grid-template-columns: 1fr;
  }
}

```
# End of file: app/static/styles.css

# File: shared/config.py
```python
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Mapping


class ConfigError(ValueError):
    """Raised when required environment configuration is missing or invalid."""


DEFAULT_UPLOADS_DIR = Path("/opt/triage/data/uploads")
DEFAULT_TRIAGE_WORKSPACE_DIR = Path("/opt/triage/triage_workspace")
DEFAULT_REPO_DIRNAME = "app"
DEFAULT_MANUALS_DIRNAME = "manuals"

REQUIRED_ENV_VARS = (
    "APP_BASE_URL",
    "APP_SECRET_KEY",
    "DATABASE_URL",
    "CODEX_API_KEY",
)


def _coerce_int(name: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _coerce_float(name: str, value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc


@dataclass(frozen=True)
class Settings:
    app_base_url: str
    app_secret_key: str
    database_url: str
    codex_api_key: str
    uploads_dir: Path = DEFAULT_UPLOADS_DIR
    triage_workspace_dir: Path = DEFAULT_TRIAGE_WORKSPACE_DIR
    repo_mount_dir: Path = DEFAULT_TRIAGE_WORKSPACE_DIR / DEFAULT_REPO_DIRNAME
    manuals_mount_dir: Path = DEFAULT_TRIAGE_WORKSPACE_DIR / DEFAULT_MANUALS_DIRNAME
    codex_bin: str = "codex"
    codex_model: str | None = None
    codex_timeout_seconds: int = 75
    worker_poll_seconds: int = 10
    auto_support_reply_min_confidence: float = 0.85
    auto_confirm_intent_min_confidence: float = 0.90
    max_images_per_message: int = 3
    max_image_bytes: int = 5 * 1024 * 1024
    session_default_hours: int = 12
    session_remember_days: int = 30

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        values = dict(os.environ if env is None else env)
        missing = [key for key in REQUIRED_ENV_VARS if not values.get(key)]
        if missing:
            joined = ", ".join(sorted(missing))
            raise ConfigError(f"Missing required environment variables: {joined}")

        codex_model = values.get("CODEX_MODEL") or None
        triage_workspace_dir = Path(
            values.get("TRIAGE_WORKSPACE_DIR", str(DEFAULT_TRIAGE_WORKSPACE_DIR))
        )
        repo_mount_dir = Path(
            values.get("REPO_MOUNT_DIR", str(triage_workspace_dir / DEFAULT_REPO_DIRNAME))
        )
        manuals_mount_dir = Path(
            values.get("MANUALS_MOUNT_DIR", str(triage_workspace_dir / DEFAULT_MANUALS_DIRNAME))
        )

        settings = cls(
            app_base_url=values["APP_BASE_URL"],
            app_secret_key=values["APP_SECRET_KEY"],
            database_url=values["DATABASE_URL"],
            codex_api_key=values["CODEX_API_KEY"],
            uploads_dir=Path(values.get("UPLOADS_DIR", str(DEFAULT_UPLOADS_DIR))),
            triage_workspace_dir=triage_workspace_dir,
            repo_mount_dir=repo_mount_dir,
            manuals_mount_dir=manuals_mount_dir,
            codex_bin=values.get("CODEX_BIN", "codex"),
            codex_model=codex_model,
            codex_timeout_seconds=_coerce_int(
                "CODEX_TIMEOUT_SECONDS", values.get("CODEX_TIMEOUT_SECONDS", "75")
            ),
            worker_poll_seconds=_coerce_int(
                "WORKER_POLL_SECONDS", values.get("WORKER_POLL_SECONDS", "10")
            ),
            auto_support_reply_min_confidence=_coerce_float(
                "AUTO_SUPPORT_REPLY_MIN_CONFIDENCE",
                values.get("AUTO_SUPPORT_REPLY_MIN_CONFIDENCE", "0.85"),
            ),
            auto_confirm_intent_min_confidence=_coerce_float(
                "AUTO_CONFIRM_INTENT_MIN_CONFIDENCE",
                values.get("AUTO_CONFIRM_INTENT_MIN_CONFIDENCE", "0.90"),
            ),
            max_images_per_message=_coerce_int(
                "MAX_IMAGES_PER_MESSAGE", values.get("MAX_IMAGES_PER_MESSAGE", "3")
            ),
            max_image_bytes=_coerce_int(
                "MAX_IMAGE_BYTES", values.get("MAX_IMAGE_BYTES", str(5 * 1024 * 1024))
            ),
            session_default_hours=_coerce_int(
                "SESSION_DEFAULT_HOURS", values.get("SESSION_DEFAULT_HOURS", "12")
            ),
            session_remember_days=_coerce_int(
                "SESSION_REMEMBER_DAYS", values.get("SESSION_REMEMBER_DAYS", "30")
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.max_images_per_message <= 0:
            raise ConfigError("MAX_IMAGES_PER_MESSAGE must be greater than zero")
        if self.max_image_bytes <= 0:
            raise ConfigError("MAX_IMAGE_BYTES must be greater than zero")
        if self.session_default_hours <= 0:
            raise ConfigError("SESSION_DEFAULT_HOURS must be greater than zero")
        if self.session_remember_days <= 0:
            raise ConfigError("SESSION_REMEMBER_DAYS must be greater than zero")
        if self.worker_poll_seconds <= 0:
            raise ConfigError("WORKER_POLL_SECONDS must be greater than zero")
        if self.codex_timeout_seconds <= 0:
            raise ConfigError("CODEX_TIMEOUT_SECONDS must be greater than zero")
        if not self.app_base_url.strip():
            raise ConfigError("APP_BASE_URL must not be blank")
        if not self.app_secret_key.strip():
            raise ConfigError("APP_SECRET_KEY must not be blank")
        if not self.database_url.strip():
            raise ConfigError("DATABASE_URL must not be blank")
        if not self.codex_api_key.strip():
            raise ConfigError("CODEX_API_KEY must not be blank")
        for name, value in (
            ("AUTO_SUPPORT_REPLY_MIN_CONFIDENCE", self.auto_support_reply_min_confidence),
            (
                "AUTO_CONFIRM_INTENT_MIN_CONFIDENCE",
                self.auto_confirm_intent_min_confidence,
            ),
        ):
            if not 0.0 <= value <= 1.0:
                raise ConfigError(f"{name} must be between 0.0 and 1.0")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()

```
# End of file: shared/config.py

# File: shared/models.py
```python
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
import uuid

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, PrimaryKeyConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UserRole(StrEnum):
    REQUESTER = "requester"
    DEV_TI = "dev_ti"
    ADMIN = "admin"


class TicketStatus(StrEnum):
    NEW = "new"
    AI_TRIAGE = "ai_triage"
    WAITING_ON_USER = "waiting_on_user"
    WAITING_ON_DEV_TI = "waiting_on_dev_ti"
    RESOLVED = "resolved"


class TicketClass(StrEnum):
    SUPPORT = "support"
    ACCESS_CONFIG = "access_config"
    DATA_OPS = "data_ops"
    BUG = "bug"
    FEATURE = "feature"
    UNKNOWN = "unknown"


class ImpactLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class MessageAuthorType(StrEnum):
    REQUESTER = "requester"
    DEV_TI = "dev_ti"
    AI = "ai"
    SYSTEM = "system"


class MessageVisibility(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"


class MessageSource(StrEnum):
    TICKET_CREATE = "ticket_create"
    REQUESTER_REPLY = "requester_reply"
    HUMAN_PUBLIC_REPLY = "human_public_reply"
    HUMAN_INTERNAL_NOTE = "human_internal_note"
    AI_AUTO_PUBLIC = "ai_auto_public"
    AI_INTERNAL_NOTE = "ai_internal_note"
    AI_DRAFT_PUBLISHED = "ai_draft_published"
    SYSTEM = "system"


class AttachmentVisibility(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"


class StatusChangedByType(StrEnum):
    REQUESTER = "requester"
    DEV_TI = "dev_ti"
    AI = "ai"
    SYSTEM = "system"


class AiRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    SUPERSEDED = "superseded"


class AiRunTrigger(StrEnum):
    NEW_TICKET = "new_ticket"
    REQUESTER_REPLY = "requester_reply"
    MANUAL_RERUN = "manual_rerun"
    REOPEN = "reopen"


class TicketRequeueTrigger(StrEnum):
    REQUESTER_REPLY = "requester_reply"
    MANUAL_RERUN = "manual_rerun"
    REOPEN = "reopen"


class AiDraftKind(StrEnum):
    PUBLIC_REPLY = "public_reply"


class AiDraftStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    PUBLISHED = "published"


def enum_values(enum_cls: type[StrEnum]) -> tuple[str, ...]:
    return tuple(item.value for item in enum_cls)


def enum_type(enum_cls: type[StrEnum], *, name: str) -> sa.Enum:
    return sa.Enum(
        *enum_values(enum_cls),
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(sa.Text(), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    role: Mapped[str] = mapped_column(enum_type(UserRole, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(sa.Text(), nullable=False, unique=True)
    csrf_token: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    remember_me: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    user_agent: Mapped[str | None] = mapped_column(sa.Text())
    ip_address: Mapped[str | None] = mapped_column(sa.Text())


class Ticket(TimestampMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_status_updated_at", "status", sa.text("updated_at DESC")),
        Index(
            "ix_tickets_created_by_updated_at",
            "created_by_user_id",
            sa.text("updated_at DESC"),
        ),
        Index(
            "ix_tickets_assigned_to_updated_at",
            "assigned_to_user_id",
            sa.text("updated_at DESC"),
        ),
        Index(
            "ix_tickets_urgent_status_updated_at",
            "urgent",
            "status",
            sa.text("updated_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    reference_num: Mapped[int] = mapped_column(
        sa.BigInteger(),
        Identity(start=1),
        nullable=False,
        unique=True,
    )
    reference: Mapped[str] = mapped_column(sa.Text(), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="RESTRICT"),
    )
    status: Mapped[str] = mapped_column(enum_type(TicketStatus, name="ticket_status"), nullable=False)
    urgent: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )
    ticket_class: Mapped[str | None] = mapped_column(enum_type(TicketClass, name="ticket_class"))
    ai_confidence: Mapped[Decimal | None] = mapped_column(sa.Numeric(4, 3))
    impact_level: Mapped[str | None] = mapped_column(enum_type(ImpactLevel, name="impact_level"))
    development_needed: Mapped[bool | None] = mapped_column(sa.Boolean())
    clarification_rounds: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=False,
        default=0,
        server_default=sa.text("0"),
    )
    requester_language: Mapped[str | None] = mapped_column(sa.Text())
    last_processed_hash: Mapped[str | None] = mapped_column(sa.Text())
    last_ai_action: Mapped[str | None] = mapped_column(sa.Text())
    requeue_requested: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )
    requeue_trigger: Mapped[str | None] = mapped_column(
        enum_type(TicketRequeueTrigger, name="ticket_requeue_trigger")
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class AiRun(TimestampMixin, Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
        Index("ix_ai_runs_status_created_at", "status", "created_at"),
        Index("ix_ai_runs_ticket_created_at_desc", "ticket_id", sa.text("created_at DESC")),
        Index(
            "uq_ai_runs_ticket_active",
            "ticket_id",
            unique=True,
            postgresql_where=sa.text("status IN ('pending', 'running')"),
            sqlite_where=sa.text("status IN ('pending', 'running')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(enum_type(AiRunStatus, name="ai_run_status"), nullable=False)
    triggered_by: Mapped[str] = mapped_column(
        enum_type(AiRunTrigger, name="ai_run_trigger"),
        nullable=False,
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    input_hash: Mapped[str | None] = mapped_column(sa.Text())
    model_name: Mapped[str | None] = mapped_column(sa.Text())
    prompt_path: Mapped[str | None] = mapped_column(sa.Text())
    schema_path: Mapped[str | None] = mapped_column(sa.Text())
    final_output_path: Mapped[str | None] = mapped_column(sa.Text())
    stdout_jsonl_path: Mapped[str | None] = mapped_column(sa.Text())
    stderr_path: Mapped[str | None] = mapped_column(sa.Text())
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    error_text: Mapped[str | None] = mapped_column(sa.Text())


class TicketMessage(TimestampMixin, Base):
    __tablename__ = "ticket_messages"
    __table_args__ = (
        Index("ix_ticket_messages_ticket_created_at", "ticket_id", "created_at"),
        Index(
            "ix_ticket_messages_ticket_visibility_created_at",
            "ticket_id",
            "visibility",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    author_type: Mapped[str] = mapped_column(
        enum_type(MessageAuthorType, name="message_author_type"),
        nullable=False,
    )
    visibility: Mapped[str] = mapped_column(
        enum_type(MessageVisibility, name="message_visibility"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(enum_type(MessageSource, name="message_source"), nullable=False)
    body_markdown: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    body_text: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("ai_runs.id", ondelete="SET NULL"),
    )


class TicketAttachment(TimestampMixin, Base):
    __tablename__ = "ticket_attachments"
    __table_args__ = (
        Index("ix_ticket_attachments_ticket_id", "ticket_id"),
        Index("ix_ticket_attachments_message_id", "message_id"),
        Index("ix_ticket_attachments_sha256", "sha256"),
        CheckConstraint(
            "visibility = 'public' OR visibility = 'internal'",
            name="ck_ticket_attachments_visibility_allowed",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("ticket_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    visibility: Mapped[str] = mapped_column(
        enum_type(AttachmentVisibility, name="attachment_visibility"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    stored_path: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    mime_type: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    sha256: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    size_bytes: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    width: Mapped[int | None] = mapped_column(sa.Integer())
    height: Mapped[int | None] = mapped_column(sa.Integer())


class TicketStatusHistory(TimestampMixin, Base):
    __tablename__ = "ticket_status_history"
    __table_args__ = (Index("ix_ticket_status_history_ticket_created_at", "ticket_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(enum_type(TicketStatus, name="history_from_status"))
    to_status: Mapped[str] = mapped_column(enum_type(TicketStatus, name="history_to_status"), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    changed_by_type: Mapped[str] = mapped_column(
        enum_type(StatusChangedByType, name="status_changed_by_type"),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(sa.Text())


class TicketView(Base):
    __tablename__ = "ticket_views"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "ticket_id", name="pk_ticket_views"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    last_viewed_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


class AiDraft(TimestampMixin, Base):
    __tablename__ = "ai_drafts"
    __table_args__ = (
        Index("ix_ai_drafts_ticket_status_created_at_desc", "ticket_id", "status", sa.text("created_at DESC")),
        Index("ix_ai_drafts_ai_run_id", "ai_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_run_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("ai_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(enum_type(AiDraftKind, name="ai_draft_kind"), nullable=False)
    body_markdown: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    body_text: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    status: Mapped[str] = mapped_column(enum_type(AiDraftStatus, name="ai_draft_status"), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    published_message_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("ticket_messages.id", ondelete="SET NULL"),
    )


class SystemState(Base):
    __tablename__ = "system_state"

    key: Mapped[str] = mapped_column(sa.Text(), primary_key=True)
    value_json: Mapped[dict] = mapped_column(sa.JSON(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

```
# End of file: shared/models.py

# File: shared/logging.py
```python
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    def __init__(self, *, default_service: str) -> None:
        super().__init__()
        self.default_service = default_service

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.default_service,
            "level": record.levelname.lower(),
            "logger": record.name,
        }
        structured = getattr(record, "structured_payload", None)
        if isinstance(structured, dict):
            payload.update(structured)
        else:
            payload["message"] = record.getMessage()
        payload.setdefault("service", self.default_service)
        return json.dumps(payload, default=str)


def configure_logging(*, service: str, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(default_service=service))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def log_event(
    logger: logging.Logger,
    *,
    service: str,
    event: str,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    payload = {"service": service, "event": event, **fields}
    logger.log(level, event, extra={"structured_payload": payload})

```
# End of file: shared/logging.py

# File: shared/user_admin.py
```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models import User, UserRole
from shared.security import hash_password, normalize_email


class UserAdminError(RuntimeError):
    """Raised when a user administration command cannot be completed."""


def _require_role(role: str) -> str:
    allowed = {item.value for item in UserRole}
    if role not in allowed:
        joined = ", ".join(sorted(allowed))
        raise UserAdminError(f"Invalid role '{role}'. Allowed roles: {joined}")
    return role


def create_user_account(
    session: Session,
    *,
    email: str,
    display_name: str,
    password: str,
    role: str,
) -> User:
    normalized_email = normalize_email(email)
    role = _require_role(role)
    existing = session.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        raise UserAdminError(f"User already exists: {normalized_email}")

    user = User(
        email=normalized_email,
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def get_user_by_email(session: Session, *, email: str) -> User:
    normalized_email = normalize_email(email)
    user = session.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        raise UserAdminError(f"User not found: {normalized_email}")
    return user


def set_user_password(session: Session, *, email: str, password: str) -> User:
    user = get_user_by_email(session, email=email)
    user.password_hash = hash_password(password)
    session.flush()
    return user


def deactivate_user_account(session: Session, *, email: str) -> User:
    user = get_user_by_email(session, email=email)
    user.is_active = False
    session.flush()
    return user

```
# End of file: shared/user_admin.py

# File: shared/security.py
```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from urllib.parse import urlparse

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from shared.config import Settings


SESSION_COOKIE_NAME = "triage_session"
LOGIN_CSRF_COOKIE_NAME = "triage_login_csrf"
_PASSWORD_HASHER = PasswordHasher()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def session_expires_at(
    settings: Settings,
    *,
    remember_me: bool,
    now: datetime | None = None,
) -> datetime:
    now = now or utcnow()
    if remember_me:
        return now + timedelta(days=settings.session_remember_days)
    return now + timedelta(hours=settings.session_default_hours)


def session_max_age(settings: Settings, *, remember_me: bool) -> int | None:
    if not remember_me:
        return None
    return settings.session_remember_days * 24 * 60 * 60


def should_use_secure_cookies(settings: Settings) -> bool:
    return urlparse(settings.app_base_url).scheme == "https"


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def sign_login_csrf(secret_key: str, raw_token: str) -> str:
    digest = hmac.new(
        secret_key.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    )
    return digest.hexdigest()


def generate_login_csrf_token(secret_key: str) -> str:
    raw_token = generate_csrf_token()
    signature = sign_login_csrf(secret_key, raw_token)
    return f"{raw_token}.{signature}"


def validate_login_csrf_token(secret_key: str, token: str) -> bool:
    raw_token, separator, signature = token.partition(".")
    if not separator or not raw_token or not signature:
        return False
    expected = sign_login_csrf(secret_key, raw_token)
    return constant_time_equals(signature, expected)

```
# End of file: shared/security.py

# File: shared/permissions.py
```python
from __future__ import annotations

from shared.models import (
    AttachmentVisibility,
    Ticket,
    TicketAttachment,
    User,
    UserRole,
)


class PermissionDeniedError(ValueError):
    """Raised when a user attempts an unauthorized action."""


def has_role(user: User, *roles: UserRole | str) -> bool:
    allowed = {role.value if isinstance(role, UserRole) else role for role in roles}
    return user.role in allowed


def ensure_role(user: User, *roles: UserRole | str) -> None:
    if not has_role(user, *roles):
        joined = ", ".join(sorted(role.value if isinstance(role, UserRole) else role for role in roles))
        raise PermissionDeniedError(f"User role {user.role!r} does not satisfy required roles: {joined}")


def ensure_requester(user: User) -> None:
    ensure_role(user, UserRole.REQUESTER)


def ensure_dev_ti(user: User) -> None:
    ensure_role(user, UserRole.DEV_TI, UserRole.ADMIN)


def ensure_requester_ticket_access(user: User, ticket: Ticket) -> None:
    ensure_requester(user)
    if ticket.created_by_user_id != user.id:
        raise PermissionDeniedError("Requester does not own this ticket")


def ensure_requester_attachment_access(
    user: User,
    ticket: Ticket,
    attachment: TicketAttachment,
) -> None:
    ensure_requester_ticket_access(user, ticket)
    if attachment.visibility != AttachmentVisibility.PUBLIC.value:
        raise PermissionDeniedError("Requester cannot access non-public attachments")

```
# End of file: shared/permissions.py

# File: shared/bootstrap.py
```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from shared.config import Settings
from shared.db import session_scope
from shared.models import SystemState
from shared.workspace_contract import EXACT_AGENTS_MD, EXACT_SKILL_MD


DEFAULT_BOOTSTRAP_VERSION = "1.2-custom-final"


class WorkspaceBootstrapError(RuntimeError):
    """Raised when the workspace bootstrap contract cannot be satisfied."""


@dataclass(frozen=True)
class WorkspaceBootstrapResult:
    uploads_dir: str
    workspace_dir: str
    repo_mount_dir: str
    manuals_mount_dir: str
    git_initialized: bool
    initial_commit_created: bool
    agents_written: bool
    skill_written: bool
    bootstrap_version_written: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def workspace_agents_path(settings: Settings) -> Path:
    return settings.triage_workspace_dir / "AGENTS.md"


def workspace_skill_path(settings: Settings) -> Path:
    return settings.triage_workspace_dir / ".agents" / "skills" / "stage1-triage" / "SKILL.md"


def workspace_runs_dir(settings: Settings) -> Path:
    return settings.triage_workspace_dir / "runs"


def _write_if_changed(path: Path, content: str) -> bool:
    existing = None
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    if existing == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def ensure_workspace_files(settings: Settings) -> tuple[bool, bool]:
    settings.triage_workspace_dir.mkdir(parents=True, exist_ok=True)
    workspace_runs_dir(settings).mkdir(parents=True, exist_ok=True)
    agents_written = _write_if_changed(workspace_agents_path(settings), EXACT_AGENTS_MD)
    skill_written = _write_if_changed(workspace_skill_path(settings), EXACT_SKILL_MD)
    return agents_written, skill_written


def _run_git(settings: Settings, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(settings.triage_workspace_dir), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def ensure_workspace_git_repository(settings: Settings) -> tuple[bool, bool]:
    git_dir = settings.triage_workspace_dir / ".git"
    git_initialized = False
    initial_commit_created = False

    if not git_dir.exists():
        settings.triage_workspace_dir.mkdir(parents=True, exist_ok=True)
        completed = _run_git(settings, "init")
        if completed.returncode != 0:
            raise WorkspaceBootstrapError(completed.stderr.strip() or "git init failed")
        git_initialized = True

    head_check = _run_git(settings, "rev-parse", "--verify", "HEAD")
    if head_check.returncode != 0:
        commit = _run_git(
            settings,
            "-c",
            "user.name=Stage 1 Bootstrap",
            "-c",
            "user.email=stage1-triage@local",
            "commit",
            "--allow-empty",
            "-m",
            "Initialize workspace",
        )
        if commit.returncode != 0:
            raise WorkspaceBootstrapError(commit.stderr.strip() or "git commit --allow-empty failed")
        initial_commit_created = True

    return git_initialized, initial_commit_created


def verify_required_path(path: Path, *, label: str, must_be_directory: bool = True) -> None:
    if not path.exists():
        raise WorkspaceBootstrapError(f"{label} is missing: {path}")
    if must_be_directory and not path.is_dir():
        raise WorkspaceBootstrapError(f"{label} is not a directory: {path}")
    if not os.access(path, os.R_OK):
        raise WorkspaceBootstrapError(f"{label} is not readable: {path}")


def workspace_readiness_issues(settings: Settings) -> list[str]:
    issues: list[str] = []

    def check(path: Path, *, label: str, must_be_directory: bool = True, exact_text: str | None = None) -> None:
        if not path.exists():
            issues.append(f"{label} missing: {path}")
            return
        if must_be_directory and not path.is_dir():
            issues.append(f"{label} not a directory: {path}")
            return
        if not os.access(path, os.R_OK):
            issues.append(f"{label} not readable: {path}")
            return
        if exact_text is not None and path.read_text(encoding="utf-8") != exact_text:
            issues.append(f"{label} content mismatch: {path}")

    check(settings.uploads_dir, label="uploads_dir")
    check(settings.triage_workspace_dir, label="triage_workspace_dir")
    check(settings.repo_mount_dir, label="repo_mount_dir")
    check(settings.manuals_mount_dir, label="manuals_mount_dir")
    check(workspace_runs_dir(settings), label="workspace_runs_dir")
    check(workspace_agents_path(settings), label="agents_md", must_be_directory=False, exact_text=EXACT_AGENTS_MD)
    check(workspace_skill_path(settings), label="skill_md", must_be_directory=False, exact_text=EXACT_SKILL_MD)
    return issues


def check_database_readiness(session_factory: sessionmaker[Session]) -> str | None:
    try:
        with session_scope(session_factory) as session:
            session.execute(sa.text("SELECT 1"))
        return None
    except Exception as exc:  # pragma: no cover - error path exercised in app tests via monkeypatch
        return str(exc)


def write_bootstrap_version(
    session_factory: sessionmaker[Session],
    *,
    version: str = DEFAULT_BOOTSTRAP_VERSION,
    updated_at: datetime | None = None,
) -> bool:
    updated_at = updated_at or now_utc()
    with session_scope(session_factory) as session:
        row = session.get(SystemState, "bootstrap_version")
        payload = {"version": version, "updated_at": updated_at.isoformat()}
        if row is None:
            session.add(SystemState(key="bootstrap_version", value_json=payload, updated_at=updated_at))
            return True
        row.value_json = payload
        row.updated_at = updated_at
        return True


def bootstrap_workspace(
    settings: Settings,
    *,
    session_factory: sessionmaker[Session] | None = None,
    bootstrap_version: str = DEFAULT_BOOTSTRAP_VERSION,
) -> WorkspaceBootstrapResult:
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.triage_workspace_dir.mkdir(parents=True, exist_ok=True)

    git_initialized, initial_commit_created = ensure_workspace_git_repository(settings)
    verify_required_path(settings.repo_mount_dir, label="repo mount")
    verify_required_path(settings.manuals_mount_dir, label="manuals mount")
    agents_written, skill_written = ensure_workspace_files(settings)

    bootstrap_version_written = False
    if session_factory is not None:
        bootstrap_version_written = write_bootstrap_version(
            session_factory,
            version=bootstrap_version,
        )

    return WorkspaceBootstrapResult(
        uploads_dir=str(settings.uploads_dir),
        workspace_dir=str(settings.triage_workspace_dir),
        repo_mount_dir=str(settings.repo_mount_dir),
        manuals_mount_dir=str(settings.manuals_mount_dir),
        git_initialized=git_initialized,
        initial_commit_created=initial_commit_created,
        agents_written=agents_written,
        skill_written=skill_written,
        bootstrap_version_written=bootstrap_version_written,
    )

```
# End of file: shared/bootstrap.py

# File: shared/__init__.py
```python
"""Shared persistence, configuration, and domain helpers for Stage 1."""

```
# End of file: shared/__init__.py

# File: shared/workspace_contract.py
```python
from __future__ import annotations


EXACT_AGENTS_MD = """This repository is the Stage 1 custom triage workspace.

You are performing Stage 1 ticket triage only.

Hard rules:
1. Stage 1 is read-only.
2. Do not modify files under app/ or manuals/.
3. Do not inspect databases, DDL, schema dumps, or logs.
4. Do not use web search.
5. Use only the ticket title, public and internal ticket messages, attached images, files under manuals/, and files under app/.
6. Search manuals/ first for support, access, and operations guidance.
7. Inspect app/ when repository understanding is needed.
8. Distinguish among: support, access_config, data_ops, bug, feature, unknown.
9. Ask at most 3 clarifying questions.
10. Never promise a fix, implementation, release, or timeline.
11. Prefer concise requester-facing replies.
12. Auto-answer support/access questions only when the available evidence strongly supports the answer.
13. If information is ambiguous, missing, conflicting, or likely incorrect, ask clarifying questions instead of guessing.
14. Return only the final JSON object that matches the provided schema.
15. Treat screenshots as evidence but do not claim certainty beyond what is visible.
16. If evidence is weak or absent, do not invent procedural answers.
17. impact_level means business/user impact in Stage 1, not technical blast radius.
18. development_needed is a triage estimate only.
19. Never propose edits, patches, commits, branches, migrations, or database changes in Stage 1.
20. Internal messages may inform internal analysis and routing.
21. Do not disclose internal-only information in automatic public replies unless the same information is already present in public ticket content.
"""


EXACT_SKILL_MD = """---
name: stage1-triage
description: Classify a ticket, search manuals/ and app/ as needed, ask concise clarifying questions when needed, and draft either a safe public reply or an internal routing note. Never modify code, never inspect databases, and never propose patches.
---

Use this skill when:
- the task is a support ticket, internal request, bug report, or feature request written in natural language
- screenshots may help clarify the request
- the workspace contains app/ and manuals/
- the output must be structured JSON for automation

Do not use this skill when:
- code modification is required
- patch generation is required
- database or DDL analysis is required
- external web research is required

Workflow:
1. Read the ticket title and all relevant ticket messages carefully.
2. Search manuals/ first when support, access, or operations guidance may exist.
3. Inspect app/ when repository understanding is needed.
4. Use attached images when relevant.
5. Classify the ticket into exactly one class.
6. Determine if the ticket likely needs development.
7. Determine if clarification is needed.
8. If clarification is needed, ask only the minimum high-value questions, maximum 3.
9. If the available evidence strongly supports an answer and confidence is high, draft a concise public reply.
10. If the request is clearly understood but should go to Dev/TI, draft a concise public confirmation only if it is safe and useful.
11. Always produce a concise internal summary.
12. Internal-only notes may inform internal summaries and routing, but must not be disclosed in automatic public replies unless already public.
13. Return only the final JSON matching the provided schema.

Quality bar:
- do not repeat information already present
- do not ask questions that the image or files already answer
- do not claim certainty without evidence
- keep public text concise and practical
"""

```
# End of file: shared/workspace_contract.py

# File: shared/tickets.py
```python
from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from shared.models import (
    AiDraft,
    AiDraftStatus,
    AiRun,
    AiRunStatus,
    AiRunTrigger,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    StatusChangedByType,
    Ticket,
    TicketAttachment,
    TicketMessage,
    TicketStatus,
    TicketStatusHistory,
    TicketRequeueTrigger,
    TicketView,
    User,
)


class TicketError(ValueError):
    """Base class for shared ticket-domain helper errors."""


class MissingTicketReferenceNumberError(TicketError):
    """Raised when a ticket reference cannot be derived yet."""


class ActiveAIRunExistsError(TicketError):
    """Raised when a second active AI run is requested for the same ticket."""


class InvalidDraftStateError(TicketError):
    """Raised when a draft transition is attempted from the wrong state."""


ACTIVE_AI_RUN_STATUSES = (
    AiRunStatus.PENDING.value,
    AiRunStatus.RUNNING.value,
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_requeue_trigger(value: TicketRequeueTrigger | str) -> str:
    return value.value if isinstance(value, TicketRequeueTrigger) else value


def normalize_status(value: TicketStatus | str) -> str:
    return value.value if isinstance(value, TicketStatus) else value


def normalize_changed_by_type(value: StatusChangedByType | str) -> str:
    return value.value if isinstance(value, StatusChangedByType) else value


def normalize_run_trigger(value: AiRunTrigger | str) -> str:
    return value.value if isinstance(value, AiRunTrigger) else value


def format_ticket_reference(reference_num: int) -> str:
    return f"T-{reference_num:06d}"


def assign_ticket_reference(ticket: Ticket) -> str:
    if ticket.reference_num is None:
        raise MissingTicketReferenceNumberError(
            "Ticket reference_num must be assigned before formatting the reference"
        )
    ticket.reference = format_ticket_reference(ticket.reference_num)
    return ticket.reference


def bump_ticket_updated_at(ticket: Ticket, when: datetime | None = None) -> datetime:
    ticket.updated_at = when or now_utc()
    return ticket.updated_at


def change_ticket_status(
    session: Session,
    ticket: Ticket,
    to_status: TicketStatus | str,
    *,
    changed_by_type: StatusChangedByType | str,
    changed_by_user_id: uuid.UUID | None = None,
    note: str | None = None,
    changed_at: datetime | None = None,
) -> TicketStatusHistory | None:
    target_status = normalize_status(to_status)
    previous_status = ticket.status
    if previous_status == target_status:
        return None

    changed_at = changed_at or now_utc()
    ticket.status = target_status
    ticket.resolved_at = changed_at if target_status == TicketStatus.RESOLVED.value else None
    bump_ticket_updated_at(ticket, changed_at)

    history = TicketStatusHistory(
        ticket_id=ticket.id,
        from_status=previous_status,
        to_status=target_status,
        changed_by_user_id=changed_by_user_id,
        changed_by_type=normalize_changed_by_type(changed_by_type),
        note=note,
        created_at=changed_at,
    )
    session.add(history)
    return history


def first_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "Untitled ticket"
    parts = re.split(r"(?<=[.!?])\s+|\n+", stripped, maxsplit=1)
    candidate = parts[0].strip() if parts else stripped
    return candidate or "Untitled ticket"


def derive_ticket_title(title: str | None, description_text: str) -> str:
    candidate = (title or "").strip()
    if candidate:
        return candidate[:120]
    return first_sentence(description_text)[:120]


def _needs_manual_reference_assignment(session: Session) -> bool:
    bind = session.get_bind()
    return bind is not None and bind.dialect.name == "sqlite"


def _next_reference_num(session: Session) -> int:
    next_value = session.scalar(sa.select(sa.func.coalesce(sa.func.max(Ticket.reference_num), 0) + 1))
    return int(next_value or 1)


def upsert_ticket_view(
    session: Session,
    *,
    user_id: uuid.UUID,
    ticket_id: uuid.UUID,
    viewed_at: datetime | None = None,
) -> TicketView:
    viewed_at = viewed_at or now_utc()
    ticket_view = session.scalar(
        sa.select(TicketView).where(
            TicketView.user_id == user_id,
            TicketView.ticket_id == ticket_id,
        )
    )
    if ticket_view is None:
        ticket_view = TicketView(user_id=user_id, ticket_id=ticket_id, last_viewed_at=viewed_at)
        session.add(ticket_view)
    else:
        ticket_view.last_viewed_at = viewed_at
    return ticket_view


def supersede_pending_drafts(
    session: Session,
    *,
    ticket_id: uuid.UUID,
    keep_draft_id: uuid.UUID | None = None,
) -> int:
    drafts = session.scalars(
        sa.select(AiDraft).where(
            AiDraft.ticket_id == ticket_id,
            AiDraft.status == AiDraftStatus.PENDING_APPROVAL.value,
        )
    ).all()
    updated = 0
    for draft in drafts:
        if keep_draft_id is not None and draft.id == keep_draft_id:
            continue
        draft.status = AiDraftStatus.SUPERSEDED.value
        updated += 1
    return updated


def find_active_ai_run(session: Session, *, ticket_id: uuid.UUID) -> AiRun | None:
    return session.scalar(
        sa.select(AiRun).where(
            AiRun.ticket_id == ticket_id,
            AiRun.status.in_(ACTIVE_AI_RUN_STATUSES),
        )
    )


def create_pending_ai_run(
    session: Session,
    *,
    ticket_id: uuid.UUID,
    triggered_by: AiRunTrigger | str,
    requested_by_user_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
) -> AiRun:
    existing = find_active_ai_run(session, ticket_id=ticket_id)
    if existing is not None:
        raise ActiveAIRunExistsError(
            f"Ticket {ticket_id} already has an active AI run ({existing.id})"
        )

    run = AiRun(
        ticket_id=ticket_id,
        status=AiRunStatus.PENDING.value,
        triggered_by=normalize_run_trigger(triggered_by),
        requested_by_user_id=requested_by_user_id,
        created_at=created_at or now_utc(),
    )
    session.add(run)
    return run


def create_ticket_message(
    session: Session,
    *,
    ticket_id: uuid.UUID,
    author_user_id: uuid.UUID | None,
    author_type: MessageAuthorType | str,
    visibility: MessageVisibility | str,
    source: MessageSource | str,
    body_markdown: str,
    body_text: str,
    ai_run_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
) -> TicketMessage:
    message = TicketMessage(
        ticket_id=ticket_id,
        author_user_id=author_user_id,
        author_type=author_type.value if isinstance(author_type, MessageAuthorType) else author_type,
        visibility=visibility.value if isinstance(visibility, MessageVisibility) else visibility,
        source=source.value if isinstance(source, MessageSource) else source,
        body_markdown=body_markdown,
        body_text=body_text,
        ai_run_id=ai_run_id,
        created_at=created_at or now_utc(),
    )
    session.add(message)
    return message


def create_requester_ticket(
    session: Session,
    *,
    creator: User,
    title: str | None,
    description_markdown: str,
    description_text: str,
    urgent: bool,
    created_at: datetime | None = None,
) -> tuple[Ticket, TicketMessage, AiRun]:
    created_at = created_at or now_utc()
    reference_num = _next_reference_num(session) if _needs_manual_reference_assignment(session) else None

    ticket = Ticket(
        reference_num=reference_num,
        reference="pending",
        title=derive_ticket_title(title, description_text),
        created_by_user_id=creator.id,
        status=TicketStatus.NEW.value,
        urgent=urgent,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(ticket)
    session.flush()

    if ticket.reference_num is None:
        ticket.reference_num = _next_reference_num(session)
        session.flush()
    assign_ticket_reference(ticket)

    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=creator.id,
        author_type=MessageAuthorType.REQUESTER,
        visibility=MessageVisibility.PUBLIC,
        source=MessageSource.TICKET_CREATE,
        body_markdown=description_markdown,
        body_text=description_text,
        created_at=created_at,
    )
    run = create_pending_ai_run(
        session,
        ticket_id=ticket.id,
        triggered_by=AiRunTrigger.NEW_TICKET,
        requested_by_user_id=creator.id,
        created_at=created_at,
    )
    session.add(
        TicketStatusHistory(
            ticket_id=ticket.id,
            from_status=None,
            to_status=TicketStatus.NEW.value,
            changed_by_user_id=creator.id,
            changed_by_type=StatusChangedByType.REQUESTER.value,
            created_at=created_at,
        )
    )
    upsert_ticket_view(session, user_id=creator.id, ticket_id=ticket.id, viewed_at=created_at)
    return ticket, message, run


def add_requester_reply(
    session: Session,
    *,
    ticket: Ticket,
    requester: User,
    body_markdown: str,
    body_text: str,
    created_at: datetime | None = None,
) -> tuple[TicketMessage, AiRun | None]:
    created_at = created_at or now_utc()
    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=requester.id,
        author_type=MessageAuthorType.REQUESTER,
        visibility=MessageVisibility.PUBLIC,
        source=MessageSource.REQUESTER_REPLY,
        body_markdown=body_markdown,
        body_text=body_text,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)

    trigger = (
        AiRunTrigger.REOPEN.value
        if ticket.status == TicketStatus.RESOLVED.value
        else AiRunTrigger.REQUESTER_REPLY.value
    )
    run: AiRun | None = None
    active_run = find_active_ai_run(session, ticket_id=ticket.id)
    if active_run is None:
        run = create_pending_ai_run(
            session,
            ticket_id=ticket.id,
            triggered_by=trigger,
            requested_by_user_id=requester.id,
            created_at=created_at,
        )
    else:
        ticket.requeue_requested = True
        ticket.requeue_trigger = normalize_requeue_trigger(trigger)

    change_ticket_status(
        session,
        ticket,
        TicketStatus.AI_TRIAGE,
        changed_by_type=StatusChangedByType.REQUESTER,
        changed_by_user_id=requester.id,
        changed_at=created_at,
    )
    upsert_ticket_view(session, user_id=requester.id, ticket_id=ticket.id, viewed_at=created_at)
    return message, run


def mark_ticket_resolved(
    session: Session,
    *,
    ticket: Ticket,
    user: User,
    changed_by_type: StatusChangedByType | str,
    changed_at: datetime | None = None,
) -> TicketStatusHistory | None:
    changed_at = changed_at or now_utc()
    history = change_ticket_status(
        session,
        ticket,
        TicketStatus.RESOLVED,
        changed_by_type=changed_by_type,
        changed_by_user_id=user.id,
        changed_at=changed_at,
    )
    upsert_ticket_view(session, user_id=user.id, ticket_id=ticket.id, viewed_at=changed_at)
    return history


def set_ticket_assignment(
    session: Session,
    *,
    ticket: Ticket,
    assigned_to_user_id: uuid.UUID | None,
    actor: User,
    changed_at: datetime | None = None,
) -> bool:
    changed_at = changed_at or now_utc()
    changed = ticket.assigned_to_user_id != assigned_to_user_id
    if changed:
        ticket.assigned_to_user_id = assigned_to_user_id
        bump_ticket_updated_at(ticket, changed_at)
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=changed_at)
    return changed


def set_ticket_status_for_ops(
    session: Session,
    *,
    ticket: Ticket,
    actor: User,
    to_status: TicketStatus | str,
    note: str | None = None,
    changed_at: datetime | None = None,
) -> TicketStatusHistory | None:
    changed_at = changed_at or now_utc()
    history = change_ticket_status(
        session,
        ticket,
        to_status,
        changed_by_type=StatusChangedByType.DEV_TI,
        changed_by_user_id=actor.id,
        note=note,
        changed_at=changed_at,
    )
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=changed_at)
    return history


def add_public_reply(
    session: Session,
    *,
    ticket: Ticket,
    actor: User,
    body_markdown: str,
    body_text: str,
    next_status: TicketStatus | str,
    created_at: datetime | None = None,
) -> tuple[TicketMessage, TicketStatusHistory | None]:
    created_at = created_at or now_utc()
    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=actor.id,
        author_type=MessageAuthorType.DEV_TI,
        visibility=MessageVisibility.PUBLIC,
        source=MessageSource.HUMAN_PUBLIC_REPLY,
        body_markdown=body_markdown,
        body_text=body_text,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)
    history = change_ticket_status(
        session,
        ticket,
        next_status,
        changed_by_type=StatusChangedByType.DEV_TI,
        changed_by_user_id=actor.id,
        changed_at=created_at,
    )
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=created_at)
    return message, history


def add_internal_note(
    session: Session,
    *,
    ticket: Ticket,
    actor: User,
    body_markdown: str,
    body_text: str,
    created_at: datetime | None = None,
) -> TicketMessage:
    created_at = created_at or now_utc()
    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=actor.id,
        author_type=MessageAuthorType.DEV_TI,
        visibility=MessageVisibility.INTERNAL,
        source=MessageSource.HUMAN_INTERNAL_NOTE,
        body_markdown=body_markdown,
        body_text=body_text,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=created_at)
    return message


def request_manual_rerun(
    session: Session,
    *,
    ticket: Ticket,
    actor: User,
    requested_at: datetime | None = None,
) -> AiRun | None:
    requested_at = requested_at or now_utc()
    run = find_active_ai_run(session, ticket_id=ticket.id)
    if run is None:
        run = create_pending_ai_run(
            session,
            ticket_id=ticket.id,
            triggered_by=AiRunTrigger.MANUAL_RERUN,
            requested_by_user_id=actor.id,
            created_at=requested_at,
        )
        change_ticket_status(
            session,
            ticket,
            TicketStatus.AI_TRIAGE,
            changed_by_type=StatusChangedByType.DEV_TI,
            changed_by_user_id=actor.id,
            changed_at=requested_at,
        )
    else:
        ticket.requeue_requested = True
        ticket.requeue_trigger = TicketRequeueTrigger.MANUAL_RERUN.value
        bump_ticket_updated_at(ticket, requested_at)
        run = None
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=requested_at)
    return run


def approve_ai_draft(
    session: Session,
    *,
    ticket: Ticket,
    draft: AiDraft,
    actor: User,
    next_status: TicketStatus | str,
    published_at: datetime | None = None,
) -> tuple[TicketMessage, TicketStatusHistory | None]:
    if draft.status != AiDraftStatus.PENDING_APPROVAL.value:
        raise InvalidDraftStateError("Only pending approval drafts can be published")

    published_at = published_at or now_utc()
    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=None,
        author_type=MessageAuthorType.AI,
        visibility=MessageVisibility.PUBLIC,
        source=MessageSource.AI_DRAFT_PUBLISHED,
        body_markdown=draft.body_markdown,
        body_text=draft.body_text,
        ai_run_id=draft.ai_run_id,
        created_at=published_at,
    )
    draft.status = AiDraftStatus.PUBLISHED.value
    draft.reviewed_by_user_id = actor.id
    draft.reviewed_at = published_at
    draft.published_message_id = message.id
    bump_ticket_updated_at(ticket, published_at)
    history = change_ticket_status(
        session,
        ticket,
        next_status,
        changed_by_type=StatusChangedByType.DEV_TI,
        changed_by_user_id=actor.id,
        changed_at=published_at,
    )
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=published_at)
    return message, history


def reject_ai_draft(
    session: Session,
    *,
    ticket: Ticket,
    draft: AiDraft,
    actor: User,
    rejected_at: datetime | None = None,
) -> None:
    if draft.status != AiDraftStatus.PENDING_APPROVAL.value:
        raise InvalidDraftStateError("Only pending approval drafts can be rejected")

    rejected_at = rejected_at or now_utc()
    draft.status = AiDraftStatus.REJECTED.value
    draft.reviewed_by_user_id = actor.id
    draft.reviewed_at = rejected_at
    bump_ticket_updated_at(ticket, rejected_at)
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=rejected_at)

```
# End of file: shared/tickets.py

# File: shared/db.py
```python
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from shared.config import Settings, get_settings


def get_database_url(settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    return resolved.database_url


def make_engine(settings: Settings | None = None, url: str | None = None) -> Engine:
    database_url = url or get_database_url(settings)
    return create_engine(database_url, future=True)


def make_session_factory(
    settings: Settings | None = None,
    url: str | None = None,
) -> sessionmaker[Session]:
    engine = make_engine(settings=settings, url=url)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

```
# End of file: shared/db.py

# File: shared/migrations/env.py
```python
from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import get_settings
from shared.models import Base


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

```
# End of file: shared/migrations/env.py

# File: shared/migrations/script.py.mako
```text
"""${message}"""

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}

```
# End of file: shared/migrations/script.py.mako

# File: shared/migrations/versions/20260319_0001_initial.py
```python
"""Initial Stage 1 triage schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260319_0001"
down_revision = None
branch_labels = None
depends_on = None


def enum_type(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "role",
            enum_type("user_role", "requester", "dev_ti", "admin"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("csrf_token", sa.Text(), nullable=False),
        sa.Column("remember_me", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("user_agent", sa.Text()),
        sa.Column("ip_address", sa.Text()),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("reference_num", sa.BigInteger(), sa.Identity(start=1), nullable=False),
        sa.Column("reference", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assigned_to_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "status",
            enum_type(
                "ticket_status",
                "new",
                "ai_triage",
                "waiting_on_user",
                "waiting_on_dev_ti",
                "resolved",
            ),
            nullable=False,
        ),
        sa.Column("urgent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "ticket_class",
            enum_type(
                "ticket_class",
                "support",
                "access_config",
                "data_ops",
                "bug",
                "feature",
                "unknown",
            ),
        ),
        sa.Column("ai_confidence", sa.Numeric(4, 3)),
        sa.Column("impact_level", enum_type("impact_level", "low", "medium", "high", "unknown")),
        sa.Column("development_needed", sa.Boolean()),
        sa.Column(
            "clarification_rounds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("requester_language", sa.Text()),
        sa.Column("last_processed_hash", sa.Text()),
        sa.Column("last_ai_action", sa.Text()),
        sa.Column("requeue_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "requeue_trigger",
            enum_type("ticket_requeue_trigger", "requester_reply", "manual_rerun", "reopen"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("reference_num"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_tickets_status_updated_at", "tickets", ["status", sa.text("updated_at DESC")])
    op.create_index(
        "ix_tickets_created_by_updated_at",
        "tickets",
        ["created_by_user_id", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_tickets_assigned_to_updated_at",
        "tickets",
        ["assigned_to_user_id", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_tickets_urgent_status_updated_at",
        "tickets",
        ["urgent", "status", sa.text("updated_at DESC")],
    )

    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "status",
            enum_type(
                "ai_run_status",
                "pending",
                "running",
                "succeeded",
                "failed",
                "skipped",
                "superseded",
            ),
            nullable=False,
        ),
        sa.Column(
            "triggered_by",
            enum_type("ai_run_trigger", "new_ticket", "requester_reply", "manual_rerun", "reopen"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("input_hash", sa.Text()),
        sa.Column("model_name", sa.Text()),
        sa.Column("prompt_path", sa.Text()),
        sa.Column("schema_path", sa.Text()),
        sa.Column("final_output_path", sa.Text()),
        sa.Column("stdout_jsonl_path", sa.Text()),
        sa.Column("stderr_path", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("error_text", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_ai_runs_status_created_at", "ai_runs", ["status", "created_at"])
    op.create_index("ix_ai_runs_ticket_created_at_desc", "ai_runs", ["ticket_id", sa.text("created_at DESC")])
    op.create_index(
        "uq_ai_runs_ticket_active",
        "ai_runs",
        ["ticket_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )

    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "author_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "author_type",
            enum_type("message_author_type", "requester", "dev_ti", "ai", "system"),
            nullable=False,
        ),
        sa.Column(
            "visibility",
            enum_type("message_visibility", "public", "internal"),
            nullable=False,
        ),
        sa.Column(
            "source",
            enum_type(
                "message_source",
                "ticket_create",
                "requester_reply",
                "human_public_reply",
                "human_internal_note",
                "ai_auto_public",
                "ai_internal_note",
                "ai_draft_published",
                "system",
            ),
            nullable=False,
        ),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column(
            "ai_run_id",
            sa.Uuid(),
            sa.ForeignKey("ai_runs.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_ticket_messages_ticket_created_at", "ticket_messages", ["ticket_id", "created_at"])
    op.create_index(
        "ix_ticket_messages_ticket_visibility_created_at",
        "ticket_messages",
        ["ticket_id", "visibility", "created_at"],
    )

    op.create_table(
        "ticket_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "message_id",
            sa.Uuid(),
            sa.ForeignKey("ticket_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "visibility",
            enum_type("attachment_visibility", "public", "internal"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_ticket_attachments_ticket_id", "ticket_attachments", ["ticket_id"])
    op.create_index("ix_ticket_attachments_message_id", "ticket_attachments", ["message_id"])
    op.create_index("ix_ticket_attachments_sha256", "ticket_attachments", ["sha256"])

    op.create_table(
        "ticket_status_history",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "from_status",
            enum_type(
                "history_from_status",
                "new",
                "ai_triage",
                "waiting_on_user",
                "waiting_on_dev_ti",
                "resolved",
            ),
        ),
        sa.Column(
            "to_status",
            enum_type(
                "history_to_status",
                "new",
                "ai_triage",
                "waiting_on_user",
                "waiting_on_dev_ti",
                "resolved",
            ),
            nullable=False,
        ),
        sa.Column(
            "changed_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "changed_by_type",
            enum_type("status_changed_by_type", "requester", "dev_ti", "ai", "system"),
            nullable=False,
        ),
        sa.Column("note", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_ticket_status_history_ticket_created_at",
        "ticket_status_history",
        ["ticket_id", "created_at"],
    )

    op.create_table(
        "ticket_views",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "last_viewed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("user_id", "ticket_id", name="pk_ticket_views"),
    )

    op.create_table(
        "ai_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), sa.ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "kind",
            enum_type("ai_draft_kind", "public_reply"),
            nullable=False,
        ),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            enum_type(
                "ai_draft_status",
                "pending_approval",
                "approved",
                "rejected",
                "superseded",
                "published",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "reviewed_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "published_message_id",
            sa.Uuid(),
            sa.ForeignKey("ticket_messages.id", ondelete="SET NULL"),
        ),
    )
    op.create_index(
        "ix_ai_drafts_ticket_status_created_at_desc",
        "ai_drafts",
        ["ticket_id", "status", sa.text("created_at DESC")],
    )
    op.create_index("ix_ai_drafts_ai_run_id", "ai_drafts", ["ai_run_id"])

    op.create_table(
        "system_state",
        sa.Column("key", sa.Text(), primary_key=True, nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_table("system_state")
    op.drop_index("ix_ai_drafts_ai_run_id", table_name="ai_drafts")
    op.drop_index("ix_ai_drafts_ticket_status_created_at_desc", table_name="ai_drafts")
    op.drop_table("ai_drafts")
    op.drop_table("ticket_views")
    op.drop_index("ix_ticket_status_history_ticket_created_at", table_name="ticket_status_history")
    op.drop_table("ticket_status_history")
    op.drop_index("ix_ticket_attachments_sha256", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_message_id", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_ticket_id", table_name="ticket_attachments")
    op.drop_table("ticket_attachments")
    op.drop_index("ix_ticket_messages_ticket_visibility_created_at", table_name="ticket_messages")
    op.drop_index("ix_ticket_messages_ticket_created_at", table_name="ticket_messages")
    op.drop_table("ticket_messages")
    op.drop_index("uq_ai_runs_ticket_active", table_name="ai_runs")
    op.drop_index("ix_ai_runs_ticket_created_at_desc", table_name="ai_runs")
    op.drop_index("ix_ai_runs_status_created_at", table_name="ai_runs")
    op.drop_table("ai_runs")
    op.drop_index("ix_tickets_urgent_status_updated_at", table_name="tickets")
    op.drop_index("ix_tickets_assigned_to_updated_at", table_name="tickets")
    op.drop_index("ix_tickets_created_by_updated_at", table_name="tickets")
    op.drop_index("ix_tickets_status_updated_at", table_name="tickets")
    op.drop_table("tickets")
    op.drop_table("sessions")
    op.drop_table("users")

```
# End of file: shared/migrations/versions/20260319_0001_initial.py

# File: scripts/create_user.py
```python
from __future__ import annotations

import argparse

try:
    from _common import print_json, resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import print_json, resolve_runtime
from shared.db import session_scope
from shared.user_admin import UserAdminError, create_user_account


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a local triage user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", required=True, choices=["requester", "dev_ti", "admin"])
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    _, resolved_session_factory = resolve_runtime(settings=settings, session_factory=session_factory)
    try:
        with session_scope(resolved_session_factory) as session:
            user = create_user_account(
                session,
                email=args.email,
                display_name=args.display_name,
                password=args.password,
                role=args.role,
            )
            payload = {
                "status": "ok",
                "user_id": str(user.id),
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
            }
    except UserAdminError as exc:
        print_json({"status": "error", "error": str(exc)})
        return 1

    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/create_user.py

# File: scripts/create_admin.py
```python
from __future__ import annotations

import argparse

try:
    from _common import print_json, resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import print_json, resolve_runtime
from shared.db import session_scope
from shared.models import UserRole
from shared.user_admin import UserAdminError, create_user_account


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create an admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--password", required=True)
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    _, resolved_session_factory = resolve_runtime(settings=settings, session_factory=session_factory)
    try:
        with session_scope(resolved_session_factory) as session:
            user = create_user_account(
                session,
                email=args.email,
                display_name=args.display_name,
                password=args.password,
                role=UserRole.ADMIN.value,
            )
            payload = {
                "status": "ok",
                "user_id": str(user.id),
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
            }
    except UserAdminError as exc:
        print_json({"status": "error", "error": str(exc)})
        return 1

    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/create_admin.py

# File: scripts/set_password.py
```python
from __future__ import annotations

import argparse

try:
    from _common import print_json, resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import print_json, resolve_runtime
from shared.db import session_scope
from shared.user_admin import UserAdminError, set_user_password


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reset a local triage user password.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    _, resolved_session_factory = resolve_runtime(settings=settings, session_factory=session_factory)
    try:
        with session_scope(resolved_session_factory) as session:
            user = set_user_password(session, email=args.email, password=args.password)
            payload = {
                "status": "ok",
                "user_id": str(user.id),
                "email": user.email,
            }
    except UserAdminError as exc:
        print_json({"status": "error", "error": str(exc)})
        return 1

    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/set_password.py

# File: scripts/_common.py
```python
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import Settings, get_settings  # noqa: E402
from shared.db import make_session_factory  # noqa: E402


def resolve_runtime(
    *,
    settings: Settings | None = None,
    session_factory=None,
):
    resolved_settings = settings or get_settings()
    resolved_session_factory = session_factory or make_session_factory(settings=resolved_settings)
    return resolved_settings, resolved_session_factory


def print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, default=str))

```
# End of file: scripts/_common.py

# File: scripts/run_worker.py
```python
from __future__ import annotations

import argparse

try:
    from _common import resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import resolve_runtime
from shared.logging import configure_logging
from worker.main import run_worker_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Stage 1 worker.")
    parser.add_argument("--once", action="store_true", help="Process at most one polling iteration.")
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    resolved_settings, resolved_session_factory = resolve_runtime(
        settings=settings,
        session_factory=session_factory,
    )
    configure_logging(service="worker")
    run_worker_loop(
        settings=resolved_settings,
        session_factory=resolved_session_factory,
        once=args.once,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/run_worker.py

# File: scripts/deactivate_user.py
```python
from __future__ import annotations

import argparse

try:
    from _common import print_json, resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import print_json, resolve_runtime
from shared.db import session_scope
from shared.user_admin import UserAdminError, deactivate_user_account


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deactivate a local triage user.")
    parser.add_argument("--email", required=True)
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    _, resolved_session_factory = resolve_runtime(settings=settings, session_factory=session_factory)
    try:
        with session_scope(resolved_session_factory) as session:
            user = deactivate_user_account(session, email=args.email)
            payload = {
                "status": "ok",
                "user_id": str(user.id),
                "email": user.email,
                "is_active": user.is_active,
            }
    except UserAdminError as exc:
        print_json({"status": "error", "error": str(exc)})
        return 1

    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/deactivate_user.py

# File: scripts/__init__.py
```python
"""Executable management scripts for the Stage 1 triage app."""

```
# End of file: scripts/__init__.py

# File: scripts/bootstrap_workspace.py
```python
from __future__ import annotations

import argparse

try:
    from _common import print_json, resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import print_json, resolve_runtime
from shared.bootstrap import DEFAULT_BOOTSTRAP_VERSION, WorkspaceBootstrapError, bootstrap_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap the Stage 1 triage workspace.")
    parser.add_argument(
        "--bootstrap-version",
        default=DEFAULT_BOOTSTRAP_VERSION,
        help="Value written to system_state.bootstrap_version.",
    )
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    resolved_settings, resolved_session_factory = resolve_runtime(
        settings=settings,
        session_factory=session_factory,
    )
    try:
        result = bootstrap_workspace(
            resolved_settings,
            session_factory=resolved_session_factory,
            bootstrap_version=args.bootstrap_version,
        )
    except WorkspaceBootstrapError as exc:
        print_json({"status": "error", "error": str(exc)})
        return 1

    payload = {"status": "ok"}
    payload.update(result.as_dict())
    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/bootstrap_workspace.py

# File: scripts/run_web.py
```python
from __future__ import annotations

import argparse

import uvicorn

try:
    from _common import resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import resolve_runtime
from app.main import create_app
from shared.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Stage 1 web app.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    resolved_settings, resolved_session_factory = resolve_runtime(
        settings=settings,
        session_factory=session_factory,
    )
    configure_logging(service="web")
    app = create_app(settings=resolved_settings, session_factory=resolved_session_factory)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_config=None,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/run_web.py

# File: tests/test_security.py
```python
from __future__ import annotations

from shared.config import Settings
from shared.security import (
    generate_login_csrf_token,
    hash_password,
    hash_token,
    session_max_age,
    validate_login_csrf_token,
    verify_password,
)


def make_settings() -> Settings:
    return Settings.from_env(
        {
            "APP_BASE_URL": "https://triage.example.test",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "CODEX_API_KEY": "codex-secret",
        }
    )


def test_password_hash_round_trip() -> None:
    hashed = hash_password("hunter2")

    assert hashed != "hunter2"
    assert verify_password(hashed, "hunter2") is True
    assert verify_password(hashed, "wrong") is False


def test_login_csrf_token_round_trip() -> None:
    token = generate_login_csrf_token("secret")

    assert validate_login_csrf_token("secret", token) is True
    assert validate_login_csrf_token("secret", f"{token}x") is False


def test_session_max_age_only_for_remember_me() -> None:
    settings = make_settings()

    assert session_max_age(settings, remember_me=False) is None
    assert session_max_age(settings, remember_me=True) == 30 * 24 * 60 * 60


def test_hash_token_is_sha256_hex() -> None:
    digest = hash_token("plain-token")

    assert len(digest) == 64
    assert digest != "plain-token"

```
# End of file: tests/test_security.py

# File: tests/test_ticket_helpers.py
```python
from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from shared.models import (
    AiDraft,
    AiDraftStatus,
    AiRunStatus,
    AiRunTrigger,
    Base,
    StatusChangedByType,
    Ticket,
    TicketStatus,
    User,
    UserRole,
)
from shared.tickets import (
    ActiveAIRunExistsError,
    assign_ticket_reference,
    change_ticket_status,
    create_pending_ai_run,
    format_ticket_reference,
    supersede_pending_drafts,
    upsert_ticket_view,
)


@pytest.fixture
def session() -> Session:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        yield db


def make_user(email: str) -> User:
    return User(
        email=email,
        display_name=email.split("@", 1)[0],
        password_hash="hashed",
        role=UserRole.REQUESTER.value,
    )


def make_ticket(user_id: uuid.UUID, reference_num: int = 1) -> Ticket:
    ticket = Ticket(
        reference_num=reference_num,
        reference=format_ticket_reference(reference_num),
        title="Title",
        created_by_user_id=user_id,
        status=TicketStatus.NEW.value,
    )
    return ticket


def test_format_ticket_reference_zero_pads() -> None:
    assert format_ticket_reference(42) == "T-000042"


def test_assign_ticket_reference_uses_reference_num() -> None:
    ticket = Ticket(reference_num=12, reference="placeholder", title="x", created_by_user_id=uuid.uuid4(), status="new")
    assert assign_ticket_reference(ticket) == "T-000012"


def test_change_ticket_status_writes_history_and_resolved_at(session: Session) -> None:
    actor = make_user("user@example.com")
    session.add(actor)
    session.flush()
    ticket = make_ticket(actor.id)
    session.add(ticket)
    session.flush()

    changed_at = datetime(2026, 3, 19, tzinfo=timezone.utc)
    history = change_ticket_status(
        session,
        ticket,
        TicketStatus.RESOLVED,
        changed_by_type=StatusChangedByType.DEV_TI,
        changed_by_user_id=actor.id,
        changed_at=changed_at,
    )
    session.flush()

    assert history is not None
    assert ticket.status == TicketStatus.RESOLVED.value
    assert ticket.resolved_at == changed_at
    assert ticket.updated_at == changed_at


def test_upsert_ticket_view_updates_existing_row(session: Session) -> None:
    actor = make_user("viewer@example.com")
    session.add(actor)
    session.flush()
    ticket = make_ticket(actor.id)
    session.add(ticket)
    session.flush()

    first_seen = datetime(2026, 3, 19, 10, tzinfo=timezone.utc)
    second_seen = datetime(2026, 3, 19, 12, tzinfo=timezone.utc)
    first = upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=first_seen)
    session.flush()
    second = upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=second_seen)

    assert first.user_id == second.user_id
    assert second.last_viewed_at == second_seen


def test_supersede_pending_drafts_only_touches_pending_approval(session: Session) -> None:
    actor = make_user("author@example.com")
    session.add(actor)
    session.flush()
    ticket = make_ticket(actor.id)
    session.add(ticket)
    session.flush()
    run = create_pending_ai_run(session, ticket_id=ticket.id, triggered_by=AiRunTrigger.NEW_TICKET)
    run.status = AiRunStatus.SUCCEEDED.value
    session.flush()

    kept = AiDraft(
        ticket_id=ticket.id,
        ai_run_id=run.id,
        kind="public_reply",
        body_markdown="one",
        body_text="one",
        status=AiDraftStatus.PENDING_APPROVAL.value,
    )
    stale = AiDraft(
        ticket_id=ticket.id,
        ai_run_id=run.id,
        kind="public_reply",
        body_markdown="two",
        body_text="two",
        status=AiDraftStatus.PENDING_APPROVAL.value,
    )
    published = AiDraft(
        ticket_id=ticket.id,
        ai_run_id=run.id,
        kind="public_reply",
        body_markdown="three",
        body_text="three",
        status=AiDraftStatus.PUBLISHED.value,
    )
    session.add_all([kept, stale, published])
    session.flush()

    updated = supersede_pending_drafts(session, ticket_id=ticket.id, keep_draft_id=kept.id)

    assert updated == 1
    assert kept.status == AiDraftStatus.PENDING_APPROVAL.value
    assert stale.status == AiDraftStatus.SUPERSEDED.value
    assert published.status == AiDraftStatus.PUBLISHED.value


def test_create_pending_ai_run_rejects_second_active_run(session: Session) -> None:
    actor = make_user("queue@example.com")
    session.add(actor)
    session.flush()
    ticket = make_ticket(actor.id)
    session.add(ticket)
    session.flush()

    create_pending_ai_run(session, ticket_id=ticket.id, triggered_by=AiRunTrigger.NEW_TICKET)
    with pytest.raises(ActiveAIRunExistsError):
        create_pending_ai_run(session, ticket_id=ticket.id, triggered_by=AiRunTrigger.REQUESTER_REPLY)

```
# End of file: tests/test_ticket_helpers.py

# File: tests/test_models.py
```python
from __future__ import annotations

from pathlib import Path

from shared.models import AiRun, Base, TicketView


def test_ai_runs_has_partial_unique_index_for_active_statuses() -> None:
    index = next(index for index in AiRun.__table__.indexes if index.name == "uq_ai_runs_ticket_active")
    predicate = str(index.dialect_options["postgresql"]["where"])

    assert index.unique is True
    assert "pending" in predicate
    assert "running" in predicate


def test_ticket_views_primary_key_matches_prd() -> None:
    primary_key = TicketView.__table__.primary_key

    assert [column.name for column in primary_key.columns] == ["user_id", "ticket_id"]


def test_initial_migration_declares_active_run_partial_index() -> None:
    migration_path = (
        Path(__file__).resolve().parent.parent
        / "shared"
        / "migrations"
        / "versions"
        / "20260319_0001_initial.py"
    )
    content = migration_path.read_text()

    assert "uq_ai_runs_ticket_active" in content
    assert "status IN ('pending', 'running')" in content


def test_metadata_contains_all_prd_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "sessions",
        "tickets",
        "ticket_messages",
        "ticket_attachments",
        "ticket_status_history",
        "ticket_views",
        "ai_runs",
        "ai_drafts",
        "system_state",
    }

```
# End of file: tests/test_models.py

# File: tests/test_config.py
```python
from __future__ import annotations

from pathlib import Path

import pytest

from shared.config import ConfigError, Settings


def test_settings_from_env_applies_required_defaults() -> None:
    settings = Settings.from_env(
        {
            "APP_BASE_URL": "http://localhost:8000",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": "postgresql+psycopg://triage:triage@localhost/triage",
            "CODEX_API_KEY": "codex-secret",
        }
    )

    assert settings.uploads_dir.as_posix() == "/opt/triage/data/uploads"
    assert settings.triage_workspace_dir.as_posix() == "/opt/triage/triage_workspace"
    assert settings.repo_mount_dir.as_posix() == "/opt/triage/triage_workspace/app"
    assert settings.manuals_mount_dir.as_posix() == "/opt/triage/triage_workspace/manuals"
    assert settings.max_images_per_message == 3
    assert settings.max_image_bytes == 5 * 1024 * 1024
    assert settings.session_remember_days == 30


def test_settings_require_core_secrets_database_url_and_codex_key() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env({"APP_BASE_URL": "http://localhost:8000"})


def test_settings_derive_repo_and_manual_paths_from_workspace_override() -> None:
    settings = Settings.from_env(
        {
            "APP_BASE_URL": "http://localhost:8000",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": "postgresql+psycopg://triage:triage@localhost/triage",
            "CODEX_API_KEY": "codex-secret",
            "TRIAGE_WORKSPACE_DIR": "/srv/triage/workspace",
        }
    )

    assert settings.repo_mount_dir == Path("/srv/triage/workspace/app")
    assert settings.manuals_mount_dir == Path("/srv/triage/workspace/manuals")


def test_settings_validate_confidence_bounds() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env(
            {
                "APP_BASE_URL": "http://localhost:8000",
                "APP_SECRET_KEY": "secret",
                "DATABASE_URL": "postgresql+psycopg://triage:triage@localhost/triage",
                "CODEX_API_KEY": "codex-secret",
                "AUTO_SUPPORT_REPLY_MIN_CONFIDENCE": "1.1",
            }
        )


def test_env_example_documents_all_required_inputs() -> None:
    env_example = (
        Path(__file__).resolve().parent.parent / ".env.example"
    ).read_text()

    for variable in (
        "APP_BASE_URL",
        "APP_SECRET_KEY",
        "DATABASE_URL",
        "CODEX_API_KEY",
        "TRIAGE_WORKSPACE_DIR",
        "REPO_MOUNT_DIR",
        "MANUALS_MOUNT_DIR",
    ):
        assert f"{variable}=" in env_example

```
# End of file: tests/test_config.py

# File: tests/test_uploads.py
```python
from __future__ import annotations

import asyncio
from io import BytesIO

from PIL import Image
import pytest
from starlette.datastructures import FormData, Headers, UploadFile

from app.uploads import UploadValidationError, validate_public_image_uploads
from shared.config import Settings


def make_settings(*, max_images_per_message: int = 3, max_image_bytes: int = 5 * 1024 * 1024) -> Settings:
    return Settings.from_env(
        {
            "APP_BASE_URL": "http://testserver",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "CODEX_API_KEY": "codex-secret",
            "MAX_IMAGES_PER_MESSAGE": str(max_images_per_message),
            "MAX_IMAGE_BYTES": str(max_image_bytes),
        }
    )


def make_png_bytes(color: str = "red") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def make_upload(filename: str, data: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_validate_public_image_uploads_rejects_more_than_max_files() -> None:
    settings = make_settings(max_images_per_message=3)
    form = FormData(
        [
            ("attachments", make_upload("1.png", make_png_bytes("red"), "image/png")),
            ("attachments", make_upload("2.png", make_png_bytes("green"), "image/png")),
            ("attachments", make_upload("3.png", make_png_bytes("blue"), "image/png")),
            ("attachments", make_upload("4.png", make_png_bytes("yellow"), "image/png")),
        ]
    )

    with pytest.raises(UploadValidationError, match="at most 3 images"):
        asyncio.run(validate_public_image_uploads(form, settings))


def test_validate_public_image_uploads_rejects_files_over_size_limit() -> None:
    settings = make_settings(max_image_bytes=10)
    form = FormData(
        [
            ("attachments", make_upload("large.png", b"x" * 11, "image/png")),
        ]
    )

    with pytest.raises(UploadValidationError, match="10 bytes or smaller"):
        asyncio.run(validate_public_image_uploads(form, settings))

```
# End of file: tests/test_uploads.py

# File: tests/test_ops_app.py
```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.main import create_app
from shared.config import Settings
from shared.models import (
    AiDraft,
    AiDraftKind,
    AiDraftStatus,
    AiRun,
    AiRunStatus,
    Base,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    Ticket,
    TicketAttachment,
    TicketMessage,
    TicketStatus,
    TicketStatusHistory,
    TicketView,
    User,
    UserRole,
)
from shared.security import hash_password
from shared.tickets import (
    change_ticket_status,
    create_requester_ticket,
    create_ticket_message,
    format_ticket_reference,
    upsert_ticket_view,
)


def make_settings(database_url: str, uploads_dir: Path) -> Settings:
    return Settings.from_env(
        {
            "APP_BASE_URL": "http://testserver",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": database_url,
            "CODEX_API_KEY": "codex-secret",
            "UPLOADS_DIR": str(uploads_dir),
        }
    )


def build_client():
    temp_dir = Path(tempfile.mkdtemp(prefix="triage-stage1-ops-test-"))
    db_path = temp_dir / "test.db"
    uploads_dir = temp_dir / "uploads"
    engine = sa.create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    settings = make_settings(f"sqlite+pysqlite:///{db_path}", uploads_dir)
    app = create_app(settings=settings, session_factory=session_factory)
    client = TestClient(app)
    return client, session_factory


def seed_user(session_factory: sessionmaker[Session], *, email: str, role: str) -> User:
    with session_factory() as session:
        user = User(
            email=email,
            display_name=email.split("@", 1)[0],
            password_hash=hash_password("password123"),
            role=role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def login(client: TestClient, email: str, password: str = "password123"):
    response = client.get("/login")
    csrf_token = response.cookies.get("triage_login_csrf")
    return client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": csrf_token},
        follow_redirects=False,
    )


def create_ticket_fixture(
    session_factory: sessionmaker[Session],
    *,
    creator: User,
    title: str,
    body: str,
    status: str = TicketStatus.NEW.value,
    ticket_class: str | None = None,
    urgent: bool = False,
    assigned_to_user_id=None,
    created_at: datetime | None = None,
    ai_run_status: str = AiRunStatus.SUCCEEDED.value,
) -> tuple[Ticket, AiRun]:
    created_at = created_at or datetime.now(timezone.utc)
    with session_factory() as session:
        creator_db = session.get(User, creator.id)
        assert creator_db is not None
        ticket, _, run = create_requester_ticket(
            session,
            creator=creator_db,
            title=title,
            description_markdown=body,
            description_text=body,
            urgent=urgent,
            created_at=created_at,
        )
        session.flush()
        run.status = ai_run_status
        run.ended_at = created_at
        ticket.ticket_class = ticket_class
        ticket.assigned_to_user_id = assigned_to_user_id
        if status != TicketStatus.NEW.value:
            change_ticket_status(
                session,
                ticket,
                status,
                changed_by_type="system",
                changed_at=created_at + timedelta(minutes=5),
            )
        session.commit()
        session.refresh(ticket)
        session.refresh(run)
        return ticket, run


def extract_csrf(html: str) -> str:
    return html.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]


def normalize_dt(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def test_ops_board_filters_and_human_actions() -> None:
    client, session_factory = build_client()
    ops_user = seed_user(session_factory, email="ops@example.com", role=UserRole.DEV_TI.value)
    requester = seed_user(session_factory, email="requester@example.com", role=UserRole.REQUESTER.value)

    base_time = datetime(2026, 3, 20, 8, tzinfo=timezone.utc)
    filtered_ticket, filtered_run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Bug in import flow",
        body="Import crashes after upload.",
        status=TicketStatus.WAITING_ON_DEV_TI.value,
        ticket_class="bug",
        urgent=True,
        assigned_to_user_id=ops_user.id,
        created_at=base_time,
    )
    self_ticket, _ = create_ticket_fixture(
        session_factory,
        creator=ops_user,
        title="Ops-owned ticket",
        body="Created by ops.",
        status=TicketStatus.WAITING_ON_DEV_TI.value,
        ticket_class="support",
        created_at=base_time + timedelta(hours=1),
    )
    other_ticket, _ = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Resolved support request",
        body="Issue already fixed.",
        status=TicketStatus.RESOLVED.value,
        ticket_class="support",
        created_at=base_time + timedelta(hours=2),
    )

    with session_factory() as session:
        ticket = session.get(Ticket, filtered_ticket.id)
        ops = session.get(User, ops_user.id)
        assert ticket is not None
        assert ops is not None
        upsert_ticket_view(
            session,
            user_id=ops.id,
            ticket_id=ticket.id,
            viewed_at=base_time - timedelta(days=1),
        )
        session.add(
            AiDraft(
                ticket_id=ticket.id,
                ai_run_id=filtered_run.id,
                kind=AiDraftKind.PUBLIC_REPLY.value,
                body_markdown="Please retry the import with a CSV export from the new screen.",
                body_text="Please retry the import with a CSV export from the new screen.",
                status=AiDraftStatus.PENDING_APPROVAL.value,
            )
        )
        session.commit()

    assert login(client, ops_user.email).status_code == 303

    board_response = client.get(
        "/ops/board",
        params={
            "status": TicketStatus.WAITING_ON_DEV_TI.value,
            "ticket_class": "bug",
            "assigned_to": str(ops_user.id),
            "urgent": "1",
            "needs_approval": "1",
            "updated_since_my_last_view": "1",
        },
    )
    assert board_response.status_code == 200
    assert filtered_ticket.reference in board_response.text
    assert other_ticket.reference not in board_response.text

    created_by_me_response = client.get("/ops/board", params={"created_by_me": "1"})
    assert created_by_me_response.status_code == 200
    assert self_ticket.reference in created_by_me_response.text
    assert filtered_ticket.reference not in created_by_me_response.text

    detail_response = client.get(f"/ops/tickets/{filtered_ticket.reference}")
    csrf_token = extract_csrf(detail_response.text)

    assign_response = client.post(
        f"/ops/tickets/{filtered_ticket.reference}/assign",
        data={"csrf_token": csrf_token, "assigned_to_user_id": ""},
        follow_redirects=False,
    )
    assert assign_response.status_code == 303

    detail_response = client.get(f"/ops/tickets/{filtered_ticket.reference}")
    csrf_token = extract_csrf(detail_response.text)
    note_response = client.post(
        f"/ops/tickets/{filtered_ticket.reference}/note-internal",
        data={"csrf_token": csrf_token, "body": "Investigating app-side validation mismatch."},
        follow_redirects=False,
    )
    assert note_response.status_code == 303

    detail_response = client.get(f"/ops/tickets/{filtered_ticket.reference}")
    csrf_token = extract_csrf(detail_response.text)
    reply_response = client.post(
        f"/ops/tickets/{filtered_ticket.reference}/reply-public",
        data={
            "csrf_token": csrf_token,
            "body": "We are reviewing this with the team and will follow up here.",
            "next_status": TicketStatus.WAITING_ON_USER.value,
        },
        follow_redirects=False,
    )
    assert reply_response.status_code == 303

    detail_response = client.get(f"/ops/tickets/{filtered_ticket.reference}")
    csrf_token = extract_csrf(detail_response.text)
    rerun_response = client.post(
        f"/ops/tickets/{filtered_ticket.reference}/rerun-ai",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert rerun_response.status_code == 303

    with session_factory() as session:
        ticket = session.get(Ticket, filtered_ticket.id)
        assert ticket is not None
        assert ticket.assigned_to_user_id is None
        assert ticket.status == TicketStatus.AI_TRIAGE.value

        internal_note = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.INTERNAL.value,
                TicketMessage.source == MessageSource.HUMAN_INTERNAL_NOTE.value,
            )
        )
        public_reply = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.PUBLIC.value,
                TicketMessage.source == MessageSource.HUMAN_PUBLIC_REPLY.value,
            )
        )
        manual_rerun = session.scalar(
            sa.select(AiRun)
            .where(
                AiRun.ticket_id == ticket.id,
                AiRun.triggered_by == "manual_rerun",
            )
            .order_by(AiRun.created_at.desc())
        )
        ticket_view = session.get(TicketView, (ops_user.id, ticket.id))

        assert internal_note is not None
        assert public_reply is not None
        assert manual_rerun is not None
        assert manual_rerun.status == AiRunStatus.PENDING.value
        assert ticket_view is not None


def test_ops_view_tracking_only_updates_on_detail_and_successful_mutations() -> None:
    client, session_factory = build_client()
    ops_user = seed_user(session_factory, email="ops2@example.com", role=UserRole.DEV_TI.value)
    requester = seed_user(session_factory, email="owner@example.com", role=UserRole.REQUESTER.value)
    ticket, _ = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Visibility check",
        body="Please inspect this ticket.",
        status=TicketStatus.NEW.value,
    )

    old_seen = datetime(2026, 3, 1, tzinfo=timezone.utc)
    with session_factory() as session:
        upsert_ticket_view(session, user_id=ops_user.id, ticket_id=ticket.id, viewed_at=old_seen)
        session.commit()

    assert login(client, ops_user.email).status_code == 303

    board_response = client.get("/ops/board")
    assert board_response.status_code == 200
    with session_factory() as session:
        view_after_board = session.get(TicketView, (ops_user.id, ticket.id))
        assert view_after_board is not None
        assert normalize_dt(view_after_board.last_viewed_at) == old_seen

    detail_response = client.get(f"/ops/tickets/{ticket.reference}")
    assert detail_response.status_code == 200
    with session_factory() as session:
        view_after_detail = session.get(TicketView, (ops_user.id, ticket.id))
        assert view_after_detail is not None
        assert normalize_dt(view_after_detail.last_viewed_at) > old_seen
        detail_seen = normalize_dt(view_after_detail.last_viewed_at)

    csrf_token = extract_csrf(detail_response.text)
    note_response = client.post(
        f"/ops/tickets/{ticket.reference}/note-internal",
        data={"csrf_token": csrf_token, "body": "Operator note."},
        follow_redirects=False,
    )
    assert note_response.status_code == 303

    with session_factory() as session:
        view_after_post = session.get(TicketView, (ops_user.id, ticket.id))
        assert view_after_post is not None
        assert normalize_dt(view_after_post.last_viewed_at) >= detail_seen


def test_ops_invalid_public_reply_does_not_change_ticket_or_view_timestamp() -> None:
    client, session_factory = build_client()
    ops_user = seed_user(session_factory, email="ops-invalid@example.com", role=UserRole.DEV_TI.value)
    requester = seed_user(session_factory, email="owner-invalid@example.com", role=UserRole.REQUESTER.value)
    ticket, _ = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Reply validation",
        body="Need a safe validation path.",
        status=TicketStatus.WAITING_ON_DEV_TI.value,
    )

    original_updated_at = normalize_dt(ticket.updated_at)
    old_seen = datetime(2026, 3, 10, tzinfo=timezone.utc)
    with session_factory() as session:
        upsert_ticket_view(session, user_id=ops_user.id, ticket_id=ticket.id, viewed_at=old_seen)
        session.commit()

    assert login(client, ops_user.email).status_code == 303

    detail_response = client.get(f"/ops/tickets/{ticket.reference}")
    assert detail_response.status_code == 200
    csrf_token = extract_csrf(detail_response.text)
    with session_factory() as session:
        view_after_detail = session.get(TicketView, (ops_user.id, ticket.id))
        assert view_after_detail is not None
        detail_seen = normalize_dt(view_after_detail.last_viewed_at)
        assert detail_seen > old_seen

    invalid_reply_response = client.post(
        f"/ops/tickets/{ticket.reference}/reply-public",
        data={
            "csrf_token": csrf_token,
            "body": "This should not persist.",
            "next_status": "not-a-valid-status",
        },
    )
    assert invalid_reply_response.status_code == 400
    assert "Choose the next public status." in invalid_reply_response.text

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        ticket_view = session.get(TicketView, (ops_user.id, ticket.id))
        public_reply = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.PUBLIC.value,
                TicketMessage.source == MessageSource.HUMAN_PUBLIC_REPLY.value,
            )
        )
        assert ticket_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value
        assert normalize_dt(ticket_db.updated_at) == original_updated_at
        assert ticket_view is not None
        assert normalize_dt(ticket_view.last_viewed_at) == detail_seen
        assert public_reply is None


def test_ops_manual_status_route_updates_history_and_rejects_invalid_status() -> None:
    client, session_factory = build_client()
    ops_user = seed_user(session_factory, email="ops-status@example.com", role=UserRole.DEV_TI.value)
    requester = seed_user(session_factory, email="owner-status@example.com", role=UserRole.REQUESTER.value)
    ticket, _ = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Status control",
        body="Please test the manual status flow.",
        status=TicketStatus.WAITING_ON_DEV_TI.value,
    )

    with session_factory() as session:
        initial_history_count = session.scalar(
            sa.select(sa.func.count()).select_from(TicketStatusHistory).where(TicketStatusHistory.ticket_id == ticket.id)
        )
        upsert_ticket_view(
            session,
            user_id=ops_user.id,
            ticket_id=ticket.id,
            viewed_at=datetime(2026, 3, 12, tzinfo=timezone.utc),
        )
        session.commit()

    assert login(client, ops_user.email).status_code == 303

    detail_response = client.get(f"/ops/tickets/{ticket.reference}")
    assert detail_response.status_code == 200
    csrf_token = extract_csrf(detail_response.text)
    with session_factory() as session:
        view_after_detail = session.get(TicketView, (ops_user.id, ticket.id))
        assert view_after_detail is not None
        detail_seen = normalize_dt(view_after_detail.last_viewed_at)

    invalid_status_response = client.post(
        f"/ops/tickets/{ticket.reference}/set-status",
        data={"csrf_token": csrf_token, "status": "not-a-status"},
    )
    assert invalid_status_response.status_code == 400
    assert "Invalid status." in invalid_status_response.text

    with session_factory() as session:
        ticket_after_invalid = session.get(Ticket, ticket.id)
        view_after_invalid = session.get(TicketView, (ops_user.id, ticket.id))
        history_after_invalid = session.scalar(
            sa.select(sa.func.count()).select_from(TicketStatusHistory).where(TicketStatusHistory.ticket_id == ticket.id)
        )
        assert ticket_after_invalid is not None
        assert ticket_after_invalid.status == TicketStatus.WAITING_ON_DEV_TI.value
        assert ticket_after_invalid.resolved_at is None
        assert view_after_invalid is not None
        assert normalize_dt(view_after_invalid.last_viewed_at) == detail_seen
        assert history_after_invalid == initial_history_count

    detail_response = client.get(f"/ops/tickets/{ticket.reference}")
    assert detail_response.status_code == 200
    csrf_token = extract_csrf(detail_response.text)

    valid_status_response = client.post(
        f"/ops/tickets/{ticket.reference}/set-status",
        data={"csrf_token": csrf_token, "status": TicketStatus.RESOLVED.value},
        follow_redirects=False,
    )
    assert valid_status_response.status_code == 303

    with session_factory() as session:
        ticket_after_valid = session.get(Ticket, ticket.id)
        view_after_valid = session.get(TicketView, (ops_user.id, ticket.id))
        resolved_history = session.scalar(
            sa.select(TicketStatusHistory)
            .where(
                TicketStatusHistory.ticket_id == ticket.id,
                TicketStatusHistory.to_status == TicketStatus.RESOLVED.value,
            )
            .order_by(TicketStatusHistory.created_at.desc(), TicketStatusHistory.id.desc())
        )
        history_after_valid = session.scalar(
            sa.select(sa.func.count()).select_from(TicketStatusHistory).where(TicketStatusHistory.ticket_id == ticket.id)
        )
        assert ticket_after_valid is not None
        assert ticket_after_valid.status == TicketStatus.RESOLVED.value
        assert ticket_after_valid.resolved_at is not None
        assert view_after_valid is not None
        assert normalize_dt(view_after_valid.last_viewed_at) > detail_seen
        assert resolved_history is not None
        assert resolved_history.from_status == TicketStatus.WAITING_ON_DEV_TI.value
        assert resolved_history.to_status == TicketStatus.RESOLVED.value
        assert resolved_history.changed_by_user_id == ops_user.id
        assert history_after_valid == initial_history_count + 1


def test_ops_can_publish_ai_draft_without_exposing_internal_note_to_requester() -> None:
    client, session_factory = build_client()
    ops_user = seed_user(session_factory, email="ops3@example.com", role=UserRole.DEV_TI.value)
    requester = seed_user(session_factory, email="requester2@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Need guidance",
        body="Where do I find the export button?",
        status=TicketStatus.WAITING_ON_DEV_TI.value,
        ticket_class="support",
    )

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        assert ticket_db is not None
        create_ticket_message(
            session,
            ticket_id=ticket_db.id,
            author_user_id=ops_user.id,
            author_type=MessageAuthorType.DEV_TI,
            visibility=MessageVisibility.INTERNAL,
            source=MessageSource.HUMAN_INTERNAL_NOTE,
            body_markdown="Internal: this user is part of the finance pilot.",
            body_text="Internal: this user is part of the finance pilot.",
        )
        draft = AiDraft(
            ticket_id=ticket_db.id,
            ai_run_id=run.id,
            kind=AiDraftKind.PUBLIC_REPLY.value,
            body_markdown="Open **Exports** from the Reports screen and choose CSV.",
            body_text="Open Exports from the Reports screen and choose CSV.",
            status=AiDraftStatus.PENDING_APPROVAL.value,
        )
        session.add(draft)
        session.commit()
        draft_id = draft.id

    assert login(client, ops_user.email).status_code == 303
    detail_response = client.get(f"/ops/tickets/{ticket.reference}")
    assert "finance pilot" in detail_response.text
    csrf_token = extract_csrf(detail_response.text)

    approve_response = client.post(
        f"/ops/drafts/{draft_id}/approve-publish",
        data={"csrf_token": csrf_token, "next_status": TicketStatus.RESOLVED.value},
        follow_redirects=False,
    )
    assert approve_response.status_code == 303

    with session_factory() as session:
        draft = session.get(AiDraft, draft_id)
        ticket_db = session.get(Ticket, ticket.id)
        published = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.source == MessageSource.AI_DRAFT_PUBLISHED.value,
            )
        )
        assert draft is not None
        assert draft.status == AiDraftStatus.PUBLISHED.value
        assert ticket_db is not None
        assert ticket_db.status == TicketStatus.RESOLVED.value
        assert published is not None
        assert published.author_type == MessageAuthorType.AI.value

    client = TestClient(client.app)
    assert login(client, requester.email).status_code == 303
    requester_detail = client.get(f"/app/tickets/{ticket.reference}")
    assert requester_detail.status_code == 200
    assert "Open <strong>Exports</strong> from the Reports screen and choose CSV." in requester_detail.text
    assert "finance pilot" not in requester_detail.text


def test_ops_can_reject_pending_draft_without_publishing_message() -> None:
    client, session_factory = build_client()
    ops_user = seed_user(session_factory, email="ops4@example.com", role=UserRole.DEV_TI.value)
    requester = seed_user(session_factory, email="requester4@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Draft rejection",
        body="I need a response draft.",
        status=TicketStatus.WAITING_ON_DEV_TI.value,
    )

    with session_factory() as session:
        draft = AiDraft(
            ticket_id=ticket.id,
            ai_run_id=run.id,
            kind=AiDraftKind.PUBLIC_REPLY.value,
            body_markdown="Draft body.",
            body_text="Draft body.",
            status=AiDraftStatus.PENDING_APPROVAL.value,
        )
        session.add(draft)
        session.commit()
        draft_id = draft.id

    assert login(client, ops_user.email).status_code == 303
    detail_response = client.get(f"/ops/tickets/{ticket.reference}")
    csrf_token = extract_csrf(detail_response.text)
    reject_response = client.post(
        f"/ops/drafts/{draft_id}/reject",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert reject_response.status_code == 303

    with session_factory() as session:
        draft = session.get(AiDraft, draft_id)
        published = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.source == MessageSource.AI_DRAFT_PUBLISHED.value,
            )
        )
        ticket_db = session.get(Ticket, ticket.id)
        assert draft is not None
        assert draft.status == AiDraftStatus.REJECTED.value
        assert published is None
        assert ticket_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value

```
# End of file: tests/test_ops_app.py

# File: tests/conftest.py
```python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

```
# End of file: tests/conftest.py

# File: tests/test_requester_app.py
```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient
from PIL import Image
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.main import create_app
from shared.config import Settings
from shared.models import (
    AiRun,
    AttachmentVisibility,
    Base,
    SessionRecord,
    Ticket,
    TicketAttachment,
    TicketMessage,
    TicketStatus,
    TicketView,
    User,
    UserRole,
)
from shared.security import SESSION_COOKIE_NAME, hash_password, hash_token
from shared.tickets import add_public_reply


def make_png_bytes(color: str = "red") -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (8, 8), color=color)
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_settings(database_url: str, uploads_dir: Path) -> Settings:
    return Settings.from_env(
        {
            "APP_BASE_URL": "http://testserver",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": database_url,
            "CODEX_API_KEY": "codex-secret",
            "UPLOADS_DIR": str(uploads_dir),
        }
    )


def login(client: TestClient, email: str, password: str, remember_me: bool = False):
    response = client.get("/login")
    csrf_token = response.cookies.get("triage_login_csrf")
    data = {
        "email": email,
        "password": password,
        "csrf_token": csrf_token,
    }
    if remember_me:
        data["remember_me"] = "on"
    return client.post("/login", data=data, follow_redirects=False)


def build_client():
    temp_dir = Path(tempfile.mkdtemp(prefix="triage-stage1-test-"))
    db_path = temp_dir / "test.db"
    uploads_dir = temp_dir / "uploads"
    engine = sa.create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    settings = make_settings(f"sqlite+pysqlite:///{db_path}", uploads_dir)
    app = create_app(settings=settings, session_factory=session_factory)
    client = TestClient(app)
    return client, session_factory, uploads_dir


def seed_user(session_factory: sessionmaker[Session], *, email: str, role: str = "requester") -> User:
    with session_factory() as session:
        user = User(
            email=email,
            display_name=email.split("@", 1)[0],
            password_hash=hash_password("password123"),
            role=role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def test_login_creates_server_side_session_with_opaque_cookie() -> None:
    client, session_factory, _ = build_client()
    user = seed_user(session_factory, email="requester@example.com")

    response = login(client, user.email, "password123", remember_me=True)

    assert response.status_code == 303
    raw_token = response.cookies.get(SESSION_COOKIE_NAME)
    assert raw_token

    with session_factory() as session:
        record = session.scalar(sa.select(SessionRecord))
        assert record is not None
        assert record.user_id == user.id
        assert record.token_hash == hash_token(raw_token)
        assert record.csrf_token
        assert record.remember_me is True


def test_login_cookie_persistence_matches_remember_me_choice() -> None:
    client, session_factory, _ = build_client()
    user = seed_user(session_factory, email="session@example.com")
    fresh_client = TestClient(client.app)

    default_response = login(client, user.email, "password123", remember_me=False)
    remember_response = login(fresh_client, user.email, "password123", remember_me=True)

    default_cookie_headers = ",".join(default_response.headers.get_list("set-cookie"))
    remember_cookie_headers = ",".join(remember_response.headers.get_list("set-cookie"))

    assert "triage_session=" in default_cookie_headers
    assert "Max-Age=2592000" not in default_cookie_headers
    assert "triage_session=" in remember_cookie_headers
    assert "Max-Age=2592000" in remember_cookie_headers

    with session_factory() as session:
        records = session.scalars(sa.select(SessionRecord).order_by(SessionRecord.created_at.asc())).all()
        assert len(records) == 2
        assert records[0].remember_me is False
        assert records[1].remember_me is True
        default_duration = records[0].expires_at - records[0].created_at
        remember_duration = records[1].expires_at - records[1].created_at
        assert timedelta(hours=11) <= default_duration <= timedelta(hours=13)
        assert timedelta(days=29) <= remember_duration <= timedelta(days=31)


def test_expired_session_redirects_requester_back_to_login() -> None:
    client, session_factory, _ = build_client()
    user = seed_user(session_factory, email="expired@example.com")
    assert login(client, user.email, "password123").status_code == 303

    with session_factory() as session:
        record = session.scalar(sa.select(SessionRecord))
        assert record is not None
        record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()

    response = client.get("/app", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_requester_can_create_ticket_with_attachment_and_view_it() -> None:
    client, session_factory, uploads_dir = build_client()
    user = seed_user(session_factory, email="creator@example.com")

    login_response = login(client, user.email, "password123")
    assert login_response.status_code == 303

    ticket_form = client.get("/app/tickets/new")
    csrf_token = ticket_form.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    response = client.post(
        "/app/tickets",
        data={
            "csrf_token": csrf_token,
            "title": "",
            "description": "The dashboard is blank after I sign in.",
            "urgent": "on",
        },
        files=[
            ("attachments", ("screenshot.png", make_png_bytes(), "image/png")),
        ],
        follow_redirects=False,
    )

    assert response.status_code == 303
    detail_url = response.headers["location"]
    detail_response = client.get(detail_url)
    assert detail_response.status_code == 200
    assert "The dashboard is blank after I sign in." in detail_response.text
    assert "Updated" not in detail_response.text

    with session_factory() as session:
        ticket = session.scalar(sa.select(Ticket))
        assert ticket is not None
        assert ticket.title == "The dashboard is blank after I sign in."
        assert ticket.urgent is True

        run = session.scalar(sa.select(AiRun))
        assert run is not None
        assert run.triggered_by == "new_ticket"

        attachment = session.scalar(sa.select(TicketAttachment))
        assert attachment is not None
        assert Path(attachment.stored_path).exists()
        assert str(uploads_dir) in attachment.stored_path


def test_requester_reply_on_resolved_ticket_sets_reopen_requeue_when_run_active() -> None:
    client, session_factory, _ = build_client()
    user = seed_user(session_factory, email="reply@example.com")
    assert login(client, user.email, "password123").status_code == 303

    new_page = client.get("/app/tickets/new")
    csrf_token = new_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    create_response = client.post(
        "/app/tickets",
        data={
            "csrf_token": csrf_token,
            "description": "Initial ticket body.",
        },
        follow_redirects=False,
    )
    detail_url = create_response.headers["location"]

    detail_page = client.get(detail_url)
    detail_csrf = detail_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    resolve_response = client.post(
        f"{detail_url}/resolve",
        data={"csrf_token": detail_csrf},
        follow_redirects=False,
    )
    assert resolve_response.status_code == 303

    reopened_page = client.get(detail_url)
    reply_csrf = reopened_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    reply_response = client.post(
        f"{detail_url}/reply",
        data={
            "csrf_token": reply_csrf,
            "body": "Here is more context.",
        },
        follow_redirects=False,
    )
    assert reply_response.status_code == 303

    with session_factory() as session:
        ticket = session.scalar(sa.select(Ticket))
        assert ticket is not None
        assert ticket.status == "ai_triage"
        assert ticket.requeue_requested is True
        assert ticket.requeue_trigger == "reopen"


def test_requester_cannot_access_another_users_ticket_or_attachment() -> None:
    client, session_factory, _ = build_client()
    owner = seed_user(session_factory, email="owner@example.com")
    other = seed_user(session_factory, email="other@example.com")

    assert login(client, owner.email, "password123").status_code == 303
    new_page = client.get("/app/tickets/new")
    csrf_token = new_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    create_response = client.post(
        "/app/tickets",
        data={
            "csrf_token": csrf_token,
            "description": "Ticket only the owner should see.",
        },
        files=[("attachments", ("owner.png", make_png_bytes("blue"), "image/png"))],
        follow_redirects=False,
    )
    detail_url = create_response.headers["location"]

    with session_factory() as session:
        attachment = session.scalar(sa.select(TicketAttachment))
        assert attachment is not None
        attachment_id = str(attachment.id)

    client.post("/logout", data={"csrf_token": client.get(detail_url).text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]})
    assert login(client, other.email, "password123").status_code == 303

    assert client.get(detail_url).status_code == 404
    assert client.get(f"/attachments/{attachment_id}").status_code == 404


def test_requester_list_marks_ticket_updated_until_ticket_is_opened() -> None:
    client, session_factory, _ = build_client()
    requester = seed_user(session_factory, email="updates@example.com")
    ops_user = seed_user(session_factory, email="ops-updates@example.com", role=UserRole.DEV_TI.value)

    assert login(client, requester.email, "password123").status_code == 303
    new_page = client.get("/app/tickets/new")
    csrf_token = new_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    create_response = client.post(
        "/app/tickets",
        data={
            "csrf_token": csrf_token,
            "description": "Show me unread marker behavior.",
        },
        follow_redirects=False,
    )
    detail_url = create_response.headers["location"]

    list_response = client.get("/app/tickets")
    assert "Updated" not in list_response.text

    with session_factory() as session:
        ticket = session.scalar(sa.select(Ticket))
        ticket_view = session.scalar(sa.select(TicketView))
        ops_db = session.get(User, ops_user.id)
        assert ticket is not None
        assert ticket_view is not None
        assert ops_db is not None
        seen_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        ticket_view.last_viewed_at = seen_at
        add_public_reply(
            session,
            ticket=ticket,
            actor=ops_db,
            body_markdown="We need one more screenshot.",
            body_text="We need one more screenshot.",
            next_status=TicketStatus.WAITING_ON_USER,
            created_at=seen_at + timedelta(minutes=5),
        )
        session.commit()

    updated_list_response = client.get("/app/tickets")
    assert updated_list_response.status_code == 200
    assert "Updated" in updated_list_response.text

    detail_response = client.get(detail_url)
    assert detail_response.status_code == 200
    assert "We need one more screenshot." in detail_response.text

    cleared_list_response = client.get("/app/tickets")
    assert cleared_list_response.status_code == 200
    assert "Updated" not in cleared_list_response.text


def test_invalid_attachment_type_is_rejected() -> None:
    client, session_factory, _ = build_client()
    user = seed_user(session_factory, email="upload@example.com")
    assert login(client, user.email, "password123").status_code == 303

    new_page = client.get("/app/tickets/new")
    csrf_token = new_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    response = client.post(
        "/app/tickets",
        data={
            "csrf_token": csrf_token,
            "description": "Ticket with invalid attachment.",
        },
        files=[("attachments", ("notes.txt", b"plain text", "text/plain"))],
    )

    assert response.status_code == 400
    assert "Only PNG and JPEG images are allowed." in response.text


def test_requester_detail_only_shows_public_attachments() -> None:
    client, session_factory, uploads_dir = build_client()
    user = seed_user(session_factory, email="visibility@example.com")
    assert login(client, user.email, "password123").status_code == 303

    new_page = client.get("/app/tickets/new")
    csrf_token = new_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    create_response = client.post(
        "/app/tickets",
        data={
            "csrf_token": csrf_token,
            "description": "Ticket with one public and one internal attachment row.",
        },
        files=[("attachments", ("public.png", make_png_bytes("green"), "image/png"))],
        follow_redirects=False,
    )
    detail_url = create_response.headers["location"]

    with session_factory() as session:
        ticket = session.scalar(sa.select(Ticket))
        message = session.scalar(sa.select(TicketMessage))
        assert ticket is not None
        assert message is not None
        internal_path = uploads_dir / str(ticket.id) / str(message.id) / "internal-note.png"
        internal_path.parent.mkdir(parents=True, exist_ok=True)
        internal_path.write_bytes(make_png_bytes("black"))
        session.add(
            TicketAttachment(
                ticket_id=ticket.id,
                message_id=message.id,
                visibility=AttachmentVisibility.INTERNAL.value,
                original_filename="internal-note.png",
                stored_path=str(internal_path),
                mime_type="image/png",
                sha256="deadbeef",
                size_bytes=internal_path.stat().st_size,
                width=8,
                height=8,
            )
        )
        session.commit()

    detail_response = client.get(detail_url)

    assert detail_response.status_code == 200
    assert "public.png" in detail_response.text
    assert "internal-note.png" not in detail_response.text

```
# End of file: tests/test_requester_app.py

# File: tests/test_worker_phase4.py
```python
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.render import markdown_to_plain_text
from shared.config import Settings
from shared.models import (
    AiDraft,
    AiDraftStatus,
    AiRun,
    AiRunStatus,
    AttachmentVisibility,
    Base,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    Ticket,
    TicketAttachment,
    TicketMessage,
    TicketStatus,
    User,
    UserRole,
)
from shared.tickets import (
    add_requester_reply,
    create_pending_ai_run,
    create_requester_ticket,
    create_ticket_message,
)
from worker.codex_runner import CodexExecutionError, CodexRunResult, EXACT_AGENTS_MD, EXACT_SKILL_MD
from worker.main import claim_next_run, finish_prepared_run, process_next_run
from worker.ticket_loader import compute_publication_fingerprint, load_ticket_run_context


def make_settings(database_url: str, workspace_dir: Path, uploads_dir: Path) -> Settings:
    return Settings.from_env(
        {
            "APP_BASE_URL": "http://testserver",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": database_url,
            "CODEX_API_KEY": "codex-secret",
            "TRIAGE_WORKSPACE_DIR": str(workspace_dir),
            "REPO_MOUNT_DIR": str(workspace_dir / "app"),
            "MANUALS_MOUNT_DIR": str(workspace_dir / "manuals"),
            "UPLOADS_DIR": str(uploads_dir),
            "CODEX_BIN": "/bin/echo",
        }
    )


def build_session_factory():
    temp_dir = Path(tempfile.mkdtemp(prefix="triage-stage1-worker-test-"))
    db_path = temp_dir / "test.db"
    workspace_dir = temp_dir / "workspace"
    uploads_dir = temp_dir / "uploads"
    (workspace_dir / "app").mkdir(parents=True, exist_ok=True)
    (workspace_dir / "manuals").mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    engine = sa.create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    settings = make_settings(f"sqlite+pysqlite:///{db_path}", workspace_dir, uploads_dir)
    return session_factory, settings, temp_dir


def seed_user(session_factory: sessionmaker[Session], *, email: str, role: str) -> User:
    with session_factory() as session:
        user = User(
            email=email,
            display_name=email.split("@", 1)[0],
            password_hash="hashed",
            role=role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def create_ticket_fixture(
    session_factory: sessionmaker[Session],
    *,
    creator: User,
    title: str,
    body: str,
    created_at: datetime | None = None,
) -> tuple[Ticket, AiRun]:
    created_at = created_at or datetime.now(timezone.utc)
    with session_factory() as session:
        creator_db = session.get(User, creator.id)
        assert creator_db is not None
        ticket, _, run = create_requester_ticket(
            session,
            creator=creator_db,
            title=title,
            description_markdown=body,
            description_text=body,
            urgent=False,
            created_at=created_at,
        )
        session.commit()
        session.refresh(ticket)
        session.refresh(run)
        return ticket, run


def _success_payload(public_reply_markdown: str = "Please try the documented export flow.") -> dict[str, object]:
    return {
        "ticket_class": "support",
        "confidence": 0.96,
        "impact_level": "medium",
        "requester_language": "en",
        "summary_short": "Export guidance",
        "summary_internal": "The ticket matches a documented support workflow.",
        "development_needed": False,
        "needs_clarification": False,
        "clarifying_questions": [],
        "incorrect_or_conflicting_details": [],
        "evidence_found": True,
        "relevant_paths": [{"path": "manuals/export.md", "reason": "Contains the export steps."}],
        "recommended_next_action": "auto_public_reply",
        "auto_public_reply_allowed": True,
        "public_reply_markdown": public_reply_markdown,
        "internal_note_markdown": "Internal summary for Dev/TI.",
    }


def _clarification_payload(question: str = "Which export screen are you using?") -> dict[str, object]:
    return {
        "ticket_class": "unknown",
        "confidence": 0.62,
        "impact_level": "unknown",
        "requester_language": "en",
        "summary_short": "Need clarification",
        "summary_internal": "The request is ambiguous.",
        "development_needed": False,
        "needs_clarification": True,
        "clarifying_questions": [question],
        "incorrect_or_conflicting_details": [],
        "evidence_found": False,
        "relevant_paths": [],
        "recommended_next_action": "ask_clarification",
        "auto_public_reply_allowed": False,
        "public_reply_markdown": question,
        "internal_note_markdown": "Internal ambiguity summary.",
    }


def _draft_payload(public_reply_markdown: str = "Please review this draft reply.") -> dict[str, object]:
    return {
        "ticket_class": "bug",
        "confidence": 0.72,
        "impact_level": "medium",
        "requester_language": "en",
        "summary_short": "Needs review",
        "summary_internal": "The ticket needs a human-reviewed public response.",
        "development_needed": True,
        "needs_clarification": False,
        "clarifying_questions": [],
        "incorrect_or_conflicting_details": [],
        "evidence_found": True,
        "relevant_paths": [{"path": "app/import.py", "reason": "Likely related implementation path."}],
        "recommended_next_action": "draft_public_reply",
        "auto_public_reply_allowed": False,
        "public_reply_markdown": public_reply_markdown,
        "internal_note_markdown": "Internal summary for reviewer approval.",
    }


def test_worker_success_writes_workspace_artifacts_and_publishes_once(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="requester@example.com", role=UserRole.REQUESTER.value)
    ticket, _run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Need export help",
        body="I cannot find the export button.",
        created_at=datetime(2026, 3, 20, 9, tzinfo=timezone.utc),
    )

    attachment_path = settings.uploads_dir / "evidence.png"
    attachment_path.write_bytes(b"png")
    with session_factory() as session:
        initial_message = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.source == MessageSource.TICKET_CREATE.value,
            )
        )
        assert initial_message is not None
        session.add(
            TicketAttachment(
                ticket_id=ticket.id,
                message_id=initial_message.id,
                visibility=AttachmentVisibility.PUBLIC.value,
                original_filename="evidence.png",
                stored_path=str(attachment_path),
                mime_type="image/png",
                sha256="abc123",
                size_bytes=3,
                width=1,
                height=1,
            )
        )
        session.commit()

    execution = claim_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 10, tzinfo=timezone.utc),
    )
    assert execution is not None
    command = execution.prepared_run.command
    assert "--sandbox" in command
    assert "read-only" in command
    assert "--ask-for-approval" in command
    assert "never" in command
    assert "--json" in command
    assert "--output-schema" in command
    assert "--output-last-message" in command
    assert "--image" in command
    assert 'web_search="disabled"' in command
    assert execution.prepared_run.prompt_path.read_text(encoding="utf-8").startswith("$stage1-triage")
    assert (settings.triage_workspace_dir / "AGENTS.md").read_text(encoding="utf-8") == EXACT_AGENTS_MD
    assert (
        settings.triage_workspace_dir / ".agents" / "skills" / "stage1-triage" / "SKILL.md"
    ).read_text(encoding="utf-8") == EXACT_SKILL_MD

    payload = _success_payload()

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout='{"event":"done"}\n', stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = finish_prepared_run(
        session_factory,
        settings=settings,
        execution=execution,
        completed_at=datetime(2026, 3, 20, 10, 1, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value
    assert execution.prepared_run.final_output_path.exists()

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        run_db = session.get(AiRun, execution.run_id)
        ai_internal_notes = session.scalars(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.INTERNAL.value,
                TicketMessage.source == MessageSource.AI_INTERNAL_NOTE.value,
            )
        ).all()
        ai_public_messages = session.scalars(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.PUBLIC.value,
                TicketMessage.source == MessageSource.AI_AUTO_PUBLIC.value,
            )
        ).all()

        assert ticket_db is not None
        assert run_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_USER.value
        assert ticket_db.last_ai_action == "auto_public_reply"
        assert ticket_db.ticket_class == "support"
        assert ticket_db.last_processed_hash
        assert run_db.status == AiRunStatus.SUCCEEDED.value
        assert len(ai_internal_notes) == 1
        assert len(ai_public_messages) == 1
        assert ai_public_messages[0].body_text == markdown_to_plain_text(payload["public_reply_markdown"])


def test_worker_marks_run_superseded_and_enqueues_single_requeue(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="requeue@example.com", role=UserRole.REQUESTER.value)
    ticket, original_run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Intermittent export issue",
        body="The export is failing.",
        created_at=datetime(2026, 3, 20, 11, tzinfo=timezone.utc),
    )

    execution = claim_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 11, 1, tzinfo=timezone.utc),
    )
    assert execution is not None

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        requester_db = session.get(User, requester.id)
        assert ticket_db is not None
        assert requester_db is not None
        add_requester_reply(
            session,
            ticket=ticket_db,
            requester=requester_db,
            body_markdown="More detail: it fails only for large files.",
            body_text="More detail: it fails only for large files.",
            created_at=datetime(2026, 3, 20, 11, 2, tzinfo=timezone.utc),
        )
        session.commit()

    payload = _success_payload()

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = finish_prepared_run(
        session_factory,
        settings=settings,
        execution=execution,
        completed_at=datetime(2026, 3, 20, 11, 3, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUPERSEDED.value

    with session_factory() as session:
        original_run_db = session.get(AiRun, original_run.id)
        queued_runs = session.scalars(
            sa.select(AiRun)
            .where(AiRun.ticket_id == ticket.id)
            .order_by(AiRun.created_at.asc(), AiRun.id.asc())
        ).all()
        ai_messages = session.scalars(
            sa.select(TicketMessage).where(TicketMessage.ai_run_id == original_run.id)
        ).all()
        ticket_db = session.get(Ticket, ticket.id)

        assert original_run_db is not None
        assert ticket_db is not None
        assert original_run_db.status == AiRunStatus.SUPERSEDED.value
        assert len(queued_runs) == 2
        assert queued_runs[-1].status == AiRunStatus.PENDING.value
        assert queued_runs[-1].triggered_by == "requester_reply"
        assert ticket_db.requeue_requested is False
        assert ticket_db.requeue_trigger is None
        assert ai_messages == []


def test_worker_disables_automatic_publication_when_internal_notes_exist(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="leak@example.com", role=UserRole.REQUESTER.value)
    ticket, _run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Need help",
        body="I need help with the import flow.",
        created_at=datetime(2026, 3, 20, 11, 30, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.DEV_TI,
            visibility=MessageVisibility.INTERNAL,
            source=MessageSource.HUMAN_INTERNAL_NOTE,
            body_markdown="Reset the finance export entitlement for this requester before replying.",
            body_text="Reset the finance export entitlement for this requester before replying.",
        )
        session.commit()

    payload = _success_payload(public_reply_markdown="Please retry now.")

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 11, 31, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 11, 32, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        public_message = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.PUBLIC.value,
                TicketMessage.source == MessageSource.AI_AUTO_PUBLIC.value,
            )
        )
        pending_draft = session.scalar(
            sa.select(AiDraft).where(
                AiDraft.ticket_id == ticket.id,
                AiDraft.status == AiDraftStatus.PENDING_APPROVAL.value,
            )
        )
        assert ticket_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value
        assert ticket_db.last_ai_action == "draft_public_reply"
        assert public_message is None
        assert pending_draft is not None


def test_worker_routes_to_dev_ti_instead_of_asking_clarification_when_internal_notes_exist(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="clarify@example.com", role=UserRole.REQUESTER.value)
    ticket, _run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Unsure which screen",
        body="The export is not working.",
        created_at=datetime(2026, 3, 20, 11, 45, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.DEV_TI,
            visibility=MessageVisibility.INTERNAL,
            source=MessageSource.HUMAN_INTERNAL_NOTE,
            body_markdown="Ops already suspects the legacy export screen is involved.",
            body_text="Ops already suspects the legacy export screen is involved.",
        )
        session.commit()

    payload = _clarification_payload()

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 11, 46, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 11, 47, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        public_message = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.PUBLIC.value,
                TicketMessage.source == MessageSource.AI_AUTO_PUBLIC.value,
            )
        )
        assert ticket_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value
        assert ticket_db.last_ai_action == "route_dev_ti"
        assert public_message is None


def test_worker_skips_non_manual_run_when_fingerprint_matches_last_processed_hash() -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="skip@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Repeatable request",
        body="Please help with the same issue.",
        created_at=datetime(2026, 3, 20, 12, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        context = load_ticket_run_context(session, ticket_id=ticket.id)
        ticket_db = session.get(Ticket, ticket.id)
        assert ticket_db is not None
        ticket_db.last_processed_hash = compute_publication_fingerprint(context)
        session.commit()

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 12, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 12, 1, tzinfo=timezone.utc),
    )
    assert status is None

    with session_factory() as session:
        run_db = session.get(AiRun, run.id)
        ai_messages = session.scalars(
            sa.select(TicketMessage).where(TicketMessage.ticket_id == ticket.id, TicketMessage.ai_run_id == run.id)
        ).all()
        assert run_db is not None
        assert run_db.status == AiRunStatus.SKIPPED.value
        assert ai_messages == []


def test_worker_processes_manual_rerun_even_when_fingerprint_matches_last_processed_hash(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="manual@example.com", role=UserRole.REQUESTER.value)
    ops_user = seed_user(session_factory, email="ops-manual@example.com", role=UserRole.DEV_TI.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Manual rerun request",
        body="Please retry triage.",
        created_at=datetime(2026, 3, 20, 12, 30, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        ops_db = session.get(User, ops_user.id)
        run_db = session.get(AiRun, run.id)
        assert ticket_db is not None
        assert ops_db is not None
        assert run_db is not None
        context = load_ticket_run_context(session, ticket_id=ticket.id)
        ticket_db.last_processed_hash = compute_publication_fingerprint(context)
        run_db.status = AiRunStatus.SUCCEEDED.value
        run_db.ended_at = datetime(2026, 3, 20, 12, 31, tzinfo=timezone.utc)
        session.flush()
        create_pending_ai_run(
            session,
            ticket_id=ticket.id,
            triggered_by="manual_rerun",
            requested_by_user_id=ops_db.id,
            created_at=datetime(2026, 3, 20, 12, 32, tzinfo=timezone.utc),
        )
        session.commit()

    payload = _success_payload(public_reply_markdown="Manual rerun completed successfully.")

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 12, 33, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 12, 34, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value

    with session_factory() as session:
        runs = session.scalars(
            sa.select(AiRun).where(AiRun.ticket_id == ticket.id).order_by(AiRun.created_at.asc(), AiRun.id.asc())
        ).all()
        public_messages = session.scalars(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.source == MessageSource.AI_AUTO_PUBLIC.value,
            )
        ).all()
        assert [item.status for item in runs] == [AiRunStatus.SUCCEEDED.value, AiRunStatus.SUCCEEDED.value]
        assert runs[-1].triggered_by == "manual_rerun"
        assert len(public_messages) == 1


def test_worker_new_draft_supersedes_older_pending_draft(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="drafts@example.com", role=UserRole.REQUESTER.value)
    ticket, current_run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Draft supersede",
        body="Need a reviewed reply.",
        created_at=datetime(2026, 3, 20, 12, 45, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        current_run_db = session.get(AiRun, current_run.id)
        assert current_run_db is not None
        historical_run = AiRun(
            ticket_id=ticket.id,
            status=AiRunStatus.SUCCEEDED.value,
            triggered_by="new_ticket",
            requested_by_user_id=requester.id,
            created_at=datetime(2026, 3, 20, 12, 44, tzinfo=timezone.utc),
            ended_at=datetime(2026, 3, 20, 12, 44, tzinfo=timezone.utc),
        )
        session.add(historical_run)
        session.flush()
        session.add(
            AiDraft(
                ticket_id=ticket.id,
                ai_run_id=historical_run.id,
                kind="public_reply",
                body_markdown="Older pending draft.",
                body_text="Older pending draft.",
                status=AiDraftStatus.PENDING_APPROVAL.value,
                created_at=datetime(2026, 3, 20, 12, 44, tzinfo=timezone.utc),
            )
        )
        session.commit()

    payload = _draft_payload(public_reply_markdown="New draft awaiting review.")

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 12, 46, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 12, 47, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value

    with session_factory() as session:
        drafts = session.scalars(
            sa.select(AiDraft).where(AiDraft.ticket_id == ticket.id).order_by(AiDraft.created_at.asc(), AiDraft.id.asc())
        ).all()
        assert len(drafts) == 2
        assert drafts[0].status == AiDraftStatus.SUPERSEDED.value
        assert drafts[1].status == AiDraftStatus.PENDING_APPROVAL.value
        assert drafts[1].body_text == "New draft awaiting review."


def test_worker_failure_routes_ticket_to_dev_ti_and_adds_internal_failure_note(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="failure@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Broken triage",
        body="This should fail.",
        created_at=datetime(2026, 3, 20, 13, tzinfo=timezone.utc),
    )

    def fake_run_codex(_prepared_run, *, settings):
        raise CodexExecutionError("Codex exited with status 2")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 13, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 13, 2, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.FAILED.value

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        run_db = session.get(AiRun, run.id)
        failure_note = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.INTERNAL.value,
                TicketMessage.source == MessageSource.SYSTEM.value,
            )
        )
        assert ticket_db is not None
        assert run_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value
        assert run_db.status == AiRunStatus.FAILED.value
        assert run_db.error_text == "Codex exited with status 2"
        assert failure_note is not None

```
# End of file: tests/test_worker_phase4.py

# File: tests/test_phase5_operability.py
```python
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from scripts import bootstrap_workspace as bootstrap_workspace_script
from scripts import create_admin as create_admin_script
from scripts import create_user as create_user_script
from scripts import deactivate_user as deactivate_user_script
from scripts import run_web as run_web_script
from scripts import run_worker as run_worker_script
from scripts import set_password as set_password_script
from shared.bootstrap import bootstrap_workspace
from shared.config import Settings
from shared.models import Base, SystemState, User, UserRole
from shared.security import verify_password
from worker.main import run_worker_loop


def build_runtime(tmp_path: Path) -> tuple[sessionmaker, Settings]:
    db_path = tmp_path / "test.db"
    workspace_dir = tmp_path / "workspace"
    uploads_dir = tmp_path / "uploads"
    (workspace_dir / "app").mkdir(parents=True, exist_ok=True)
    (workspace_dir / "manuals").mkdir(parents=True, exist_ok=True)

    engine = sa.create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    settings = Settings.from_env(
        {
            "APP_BASE_URL": "http://testserver",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": f"sqlite+pysqlite:///{db_path}",
            "CODEX_API_KEY": "codex-secret",
            "TRIAGE_WORKSPACE_DIR": str(workspace_dir),
            "REPO_MOUNT_DIR": str(workspace_dir / "app"),
            "MANUALS_MOUNT_DIR": str(workspace_dir / "manuals"),
            "UPLOADS_DIR": str(uploads_dir),
            "CODEX_BIN": "/bin/echo",
        }
    )
    return session_factory, settings


def test_bootstrap_workspace_script_creates_git_artifacts_and_bootstrap_state(
    tmp_path: Path,
    capsys,
) -> None:
    session_factory, settings = build_runtime(tmp_path)

    exit_code = bootstrap_workspace_script.main(
        ["--bootstrap-version", "phase5-test"],
        settings=settings,
        session_factory=session_factory,
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "ok"
    assert Path(payload["workspace_dir"], ".git").exists()
    assert Path(payload["uploads_dir"]).is_dir()
    assert Path(payload["workspace_dir"], "AGENTS.md").is_file()
    assert Path(payload["workspace_dir"], ".agents", "skills", "stage1-triage", "SKILL.md").is_file()
    assert Path(payload["workspace_dir"], "runs").is_dir()

    head = subprocess.run(
        ["git", "-C", str(settings.triage_workspace_dir), "rev-parse", "--verify", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert head.returncode == 0
    assert head.stdout.strip()

    with session_factory() as session:
        bootstrap_row = session.get(SystemState, "bootstrap_version")
        assert bootstrap_row is not None
        assert bootstrap_row.value_json["version"] == "phase5-test"


def test_bootstrap_workspace_script_returns_error_when_required_mount_is_missing(
    tmp_path: Path,
    capsys,
) -> None:
    session_factory, settings = build_runtime(tmp_path)
    settings.manuals_mount_dir.rmdir()

    exit_code = bootstrap_workspace_script.main(
        [],
        settings=settings,
        session_factory=session_factory,
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "error"
    assert "manuals mount is missing" in payload["error"]


def test_user_management_scripts_create_reset_and_deactivate_accounts(
    tmp_path: Path,
    capsys,
) -> None:
    session_factory, settings = build_runtime(tmp_path)

    assert (
        create_admin_script.main(
            [
                "--email",
                "Admin@Example.com",
                "--display-name",
                "Admin User",
                "--password",
                "secret-1",
            ],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )
    assert (
        create_user_script.main(
            [
                "--email",
                "requester@example.com",
                "--display-name",
                "Requester User",
                "--password",
                "secret-2",
                "--role",
                "requester",
            ],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )
    assert (
        set_password_script.main(
            ["--email", "requester@example.com", "--password", "changed-password"],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )
    assert (
        deactivate_user_script.main(
            ["--email", "requester@example.com"],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )

    with session_factory() as session:
        admin_user = session.scalar(sa.select(User).where(User.email == "admin@example.com"))
        requester_user = session.scalar(sa.select(User).where(User.email == "requester@example.com"))
        assert admin_user is not None
        assert requester_user is not None
        assert admin_user.role == UserRole.ADMIN.value
        assert verify_password(requester_user.password_hash, "changed-password")
        assert requester_user.is_active is False

    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert [line["status"] for line in lines] == ["ok", "ok", "ok", "ok"]


def test_user_management_scripts_report_duplicate_and_missing_user_errors(
    tmp_path: Path,
    capsys,
) -> None:
    session_factory, settings = build_runtime(tmp_path)

    assert (
        create_user_script.main(
            [
                "--email",
                "requester@example.com",
                "--display-name",
                "Requester User",
                "--password",
                "secret-2",
                "--role",
                "requester",
            ],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )
    assert (
        create_user_script.main(
            [
                "--email",
                "requester@example.com",
                "--display-name",
                "Requester User",
                "--password",
                "secret-2",
                "--role",
                "requester",
            ],
            settings=settings,
            session_factory=session_factory,
        )
        == 1
    )
    assert (
        set_password_script.main(
            ["--email", "missing@example.com", "--password", "changed-password"],
            settings=settings,
            session_factory=session_factory,
        )
        == 1
    )

    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert lines[0]["status"] == "ok"
    assert lines[1] == {"status": "error", "error": "User already exists: requester@example.com"}
    assert lines[2] == {"status": "error", "error": "User not found: missing@example.com"}


def test_health_and_readiness_routes_report_bootstrap_state(tmp_path: Path) -> None:
    session_factory, settings = build_runtime(tmp_path)
    app = create_app(settings=settings, session_factory=session_factory)
    client = TestClient(app)

    health_response = client.get("/healthz")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}

    readiness_before = client.get("/readyz")
    assert readiness_before.status_code == 503
    issues = readiness_before.json()["issues"]
    assert any("uploads_dir missing" in issue for issue in issues)
    assert any("agents_md missing" in issue for issue in issues)

    bootstrap_workspace(settings, session_factory=session_factory)

    readiness_after = client.get("/readyz")
    assert readiness_after.status_code == 200
    assert readiness_after.json() == {"status": "ok"}


def test_readyz_reports_database_failure(tmp_path: Path, monkeypatch) -> None:
    session_factory, settings = build_runtime(tmp_path)
    bootstrap_workspace(settings, session_factory=session_factory)
    app = create_app(settings=settings, session_factory=session_factory)
    client = TestClient(app)

    monkeypatch.setattr("app.main.check_database_readiness", lambda _factory: "db offline")
    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["issues"][0] == "database not ready: db offline"


def test_worker_once_updates_heartbeat_system_state(tmp_path: Path, monkeypatch) -> None:
    session_factory, settings = build_runtime(tmp_path)

    monkeypatch.setattr("worker.main.process_next_run", lambda *args, **kwargs: None)
    run_worker_loop(settings=settings, session_factory=session_factory, once=True)

    with session_factory() as session:
        heartbeat = session.get(SystemState, "worker_heartbeat")
        assert heartbeat is not None
        timestamp = heartbeat.value_json["timestamp"]
        assert datetime.fromisoformat(timestamp).tzinfo == timezone.utc


def test_run_web_script_passes_configured_app_to_uvicorn(tmp_path: Path, monkeypatch) -> None:
    session_factory, settings = build_runtime(tmp_path)
    captured: dict[str, object] = {}

    def fake_uvicorn_run(app, **kwargs):
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr("scripts.run_web.uvicorn.run", fake_uvicorn_run)

    exit_code = run_web_script.main(
        ["--host", "127.0.0.1", "--port", "9000"],
        settings=settings,
        session_factory=session_factory,
    )

    assert exit_code == 0
    assert captured["app"].title == "Stage 1 AI Triage MVP"
    assert captured["kwargs"] == {
        "host": "127.0.0.1",
        "port": 9000,
        "reload": False,
        "log_config": None,
        "access_log": False,
    }


def test_run_worker_script_passes_once_flag_to_worker_loop(tmp_path: Path, monkeypatch) -> None:
    session_factory, settings = build_runtime(tmp_path)
    captured: dict[str, object] = {}

    def fake_run_worker_loop(*, settings, session_factory, once):
        captured["settings"] = settings
        captured["session_factory"] = session_factory
        captured["once"] = once

    monkeypatch.setattr("scripts.run_worker.run_worker_loop", fake_run_worker_loop)

    exit_code = run_worker_script.main(
        ["--once"],
        settings=settings,
        session_factory=session_factory,
    )

    assert exit_code == 0
    assert captured["settings"] == settings
    assert captured["session_factory"] is session_factory
    assert captured["once"] is True

```
# End of file: tests/test_phase5_operability.py

# File: worker/codex_runner.py
```python
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import uuid

from shared.bootstrap import ensure_workspace_files
from shared.config import Settings
from shared.workspace_contract import EXACT_AGENTS_MD, EXACT_SKILL_MD

EXACT_SCHEMA_JSON = """{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "ticket_class": {
      "type": "string",
      "enum": ["support", "access_config", "data_ops", "bug", "feature", "unknown"]
    },
    "confidence": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0
    },
    "impact_level": {
      "type": "string",
      "enum": ["low", "medium", "high", "unknown"]
    },
    "requester_language": {
      "type": "string",
      "minLength": 2
    },
    "summary_short": {
      "type": "string",
      "minLength": 1,
      "maxLength": 120
    },
    "summary_internal": {
      "type": "string",
      "minLength": 1
    },
    "development_needed": {
      "type": "boolean"
    },
    "needs_clarification": {
      "type": "boolean"
    },
    "clarifying_questions": {
      "type": "array",
      "maxItems": 3,
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "incorrect_or_conflicting_details": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "evidence_found": {
      "type": "boolean"
    },
    "relevant_paths": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "path": { "type": "string" },
          "reason": { "type": "string" }
        },
        "required": ["path", "reason"]
      }
    },
    "recommended_next_action": {
      "type": "string",
      "enum": [
        "ask_clarification",
        "auto_public_reply",
        "auto_confirm_and_route",
        "draft_public_reply",
        "route_dev_ti"
      ]
    },
    "auto_public_reply_allowed": {
      "type": "boolean"
    },
    "public_reply_markdown": {
      "type": "string"
    },
    "internal_note_markdown": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "ticket_class",
    "confidence",
    "impact_level",
    "requester_language",
    "summary_short",
    "summary_internal",
    "development_needed",
    "needs_clarification",
    "clarifying_questions",
    "incorrect_or_conflicting_details",
    "evidence_found",
    "relevant_paths",
    "recommended_next_action",
    "auto_public_reply_allowed",
    "public_reply_markdown",
    "internal_note_markdown"
  ]
}
"""


class CodexExecutionError(RuntimeError):
    """Raised when the Codex CLI execution fails or returns invalid artifacts."""


@dataclass(frozen=True)
class CodexPreparedRun:
    run_dir: Path
    prompt_path: Path
    schema_path: Path
    final_output_path: Path
    stdout_jsonl_path: Path
    stderr_path: Path
    command: tuple[str, ...]


@dataclass(frozen=True)
class CodexRunResult:
    payload: dict[str, object]
    stdout: str
    stderr: str
def _format_messages(messages: list[dict[str, str]]) -> str:
    if not messages:
        return "(none)"
    blocks: list[str] = []
    for index, message in enumerate(messages, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[{index}] author_type: {message['author_type']}",
                    f"source: {message['source']}",
                    "body:",
                    message["body_markdown"] or message["body_text"] or "(empty)",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_prompt(
    *,
    reference: str,
    title: str,
    status: str,
    urgent: bool,
    public_messages: list[dict[str, str]],
    internal_messages: list[dict[str, str]],
) -> str:
    return f"""$stage1-triage

Task:
Analyze this internal ticket for Stage 1 triage only.

Constraints:
- Use only the ticket title, ticket messages, attached images, files under manuals/, and files under app/.
- Search manuals/ first when support, access, or operations guidance may exist.
- Inspect app/ when repository understanding is needed.
- Do not use databases, logs, DDL, schema dumps, or external web search.
- Return only valid JSON matching the provided schema.
- Ask at most 3 clarifying questions.
- Never promise a fix, implementation, or timeline.
- Internal messages may inform internal analysis and routing but MUST NOT be disclosed in automatic public replies unless the same information is already public on the ticket.

Ticket reference:
{reference}

Ticket title:
{title}

Current status:
{status}

Urgent:
{str(urgent)}

Public messages:
{_format_messages(public_messages)}

Internal messages:
{_format_messages(internal_messages)}

Decision policy:
- Classify into exactly one of: support, access_config, data_ops, bug, feature, unknown.
- impact_level means business/user impact only.
- development_needed is only a triage estimate.
- Search manuals/ before answering support or access/config questions.
- Inspect app/ when repository understanding is needed.
- If the available evidence strongly supports an answer and confidence is high, you may draft a concise public reply.
- If the request is understood but should go to Dev/TI, you may draft a safe public confirmation and route it.
- If information is ambiguous, missing, conflicting, or likely incorrect, ask concise clarifying questions instead of guessing.
- If no safe public reply should be prepared, leave public_reply_markdown empty and set auto_public_reply_allowed to false.

Output:
Return only the JSON object.
"""


def prepare_codex_run(
    settings: Settings,
    *,
    ticket_id: uuid.UUID,
    run_id: uuid.UUID,
    prompt: str,
    image_paths: list[Path],
) -> CodexPreparedRun:
    ensure_workspace_files(settings)

    run_dir = settings.triage_workspace_dir / "runs" / str(ticket_id) / str(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = run_dir / "prompt.txt"
    schema_path = run_dir / "schema.json"
    final_output_path = run_dir / "final.json"
    stdout_jsonl_path = run_dir / "stdout.jsonl"
    stderr_path = run_dir / "stderr.txt"

    prompt_path.write_text(prompt, encoding="utf-8")
    schema_path.write_text(EXACT_SCHEMA_JSON, encoding="utf-8")
    if not stdout_jsonl_path.exists():
        stdout_jsonl_path.write_text("", encoding="utf-8")
    if not stderr_path.exists():
        stderr_path.write_text("", encoding="utf-8")

    command: list[str] = [
        settings.codex_bin,
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--ask-for-approval",
        "never",
        "--json",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(final_output_path),
        "-c",
        'web_search="disabled"',
    ]
    if settings.codex_model:
        command.extend(["--model", settings.codex_model])
    for image_path in image_paths:
        command.extend(["--image", str(image_path)])
    command.append(prompt)

    return CodexPreparedRun(
        run_dir=run_dir,
        prompt_path=prompt_path,
        schema_path=schema_path,
        final_output_path=final_output_path,
        stdout_jsonl_path=stdout_jsonl_path,
        stderr_path=stderr_path,
        command=tuple(command),
    )


def run_codex(prepared: CodexPreparedRun, *, settings: Settings) -> CodexRunResult:
    env = os.environ.copy()
    env["CODEX_API_KEY"] = settings.codex_api_key
    try:
        completed = subprocess.run(
            prepared.command,
            cwd=settings.triage_workspace_dir,
            env=env,
            text=True,
            capture_output=True,
            timeout=settings.codex_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        prepared.stdout_jsonl_path.write_text(stdout, encoding="utf-8")
        prepared.stderr_path.write_text(stderr, encoding="utf-8")
        raise CodexExecutionError(
            f"Codex execution timed out after {settings.codex_timeout_seconds} seconds"
        ) from exc

    prepared.stdout_jsonl_path.write_text(completed.stdout or "", encoding="utf-8")
    prepared.stderr_path.write_text(completed.stderr or "", encoding="utf-8")

    if completed.returncode != 0:
        raise CodexExecutionError(f"Codex exited with status {completed.returncode}")
    if not prepared.final_output_path.exists():
        raise CodexExecutionError("Codex did not produce the canonical final output artifact")

    try:
        payload = json.loads(prepared.final_output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CodexExecutionError("Codex final output was not valid JSON") from exc

    if not isinstance(payload, dict):
        raise CodexExecutionError("Codex final output must be a JSON object")

    return CodexRunResult(
        payload=payload,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )

```
# End of file: worker/codex_runner.py

# File: worker/main.py
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time
import uuid

from sqlalchemy.orm import Session, sessionmaker

from shared.config import Settings, get_settings
from shared.db import make_session_factory, session_scope
from shared.logging import configure_logging, log_event
from shared.models import AiRun, AiRunStatus, AiRunTrigger, SystemState, Ticket, TicketStatus
from shared.tickets import change_ticket_status
from worker.codex_runner import (
    CodexExecutionError,
    CodexPreparedRun,
    build_prompt,
    prepare_codex_run,
    run_codex,
)
from worker.queue import acquire_next_pending_run
from worker.ticket_loader import compute_publication_fingerprint, load_ticket_run_context
from worker.triage import (
    finalize_failure,
    finalize_skipped,
    finalize_success,
    finalize_superseded,
    validate_triage_payload,
)


LOGGER = logging.getLogger("triage-stage1.worker")
HEARTBEAT_KEY = "worker_heartbeat"


@dataclass(frozen=True)
class PreparedExecution:
    run_id: uuid.UUID
    ticket_id: uuid.UUID
    prepared_run: CodexPreparedRun


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _message_dicts(messages) -> list[dict[str, str]]:
    return [
        {
            "author_type": message.author_type,
            "source": message.source,
            "body_markdown": message.body_markdown,
            "body_text": message.body_text,
        }
        for message in messages
    ]


def _log(event: str, **fields: object) -> None:
    log_event(LOGGER, service="worker", event=event, **fields)


def claim_next_run(
    session_factory: sessionmaker[Session],
    *,
    settings: Settings,
    claimed_at: datetime | None = None,
) -> PreparedExecution | None:
    claimed_at = claimed_at or now_utc()
    with session_scope(session_factory) as session:
        run = acquire_next_pending_run(session)
        if run is None:
            return None

        context = load_ticket_run_context(session, ticket_id=run.ticket_id)
        ticket = context.ticket
        fingerprint_before_start = compute_publication_fingerprint(context)

        if (
            run.triggered_by != "manual_rerun"
            and ticket.last_processed_hash
            and fingerprint_before_start == ticket.last_processed_hash
        ):
            result = finalize_skipped(session, ticket=ticket, run=run, completed_at=claimed_at)
            _log(
                "ai_run_skipped",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
            )
            return None

        prompt = build_prompt(
            reference=ticket.reference,
            title=ticket.title,
            status=ticket.status,
            urgent=ticket.urgent,
            public_messages=_message_dicts(context.public_messages),
            internal_messages=_message_dicts(context.internal_messages),
        )
        prepared_run = prepare_codex_run(
            settings,
            ticket_id=ticket.id,
            run_id=run.id,
            prompt=prompt,
            image_paths=[attachment.path for attachment in context.public_attachments],
        )

        run.prompt_path = str(prepared_run.prompt_path)
        run.schema_path = str(prepared_run.schema_path)
        run.final_output_path = str(prepared_run.final_output_path)
        run.stdout_jsonl_path = str(prepared_run.stdout_jsonl_path)
        run.stderr_path = str(prepared_run.stderr_path)
        run.model_name = settings.codex_model
        run.status = AiRunStatus.RUNNING.value
        run.started_at = claimed_at
        run.error_text = None
        change_ticket_status(
            session,
            ticket,
            TicketStatus.AI_TRIAGE,
            changed_by_type="system",
            changed_at=claimed_at,
        )
        session.flush()
        run.input_hash = compute_publication_fingerprint(
            load_ticket_run_context(session, ticket_id=run.ticket_id)
        )
        _log("ai_run_started", run_id=run.id, ticket_reference=ticket.reference)
        return PreparedExecution(run_id=run.id, ticket_id=ticket.id, prepared_run=prepared_run)


def finish_prepared_run(
    session_factory: sessionmaker[Session],
    *,
    settings: Settings,
    execution: PreparedExecution,
    completed_at: datetime | None = None,
) -> str:
    completed_at = completed_at or now_utc()
    error_text: str | None = None
    payload: dict[str, object] | None = None

    try:
        result = run_codex(execution.prepared_run, settings=settings)
        payload = result.payload
    except CodexExecutionError as exc:
        error_text = str(exc)
    except Exception as exc:  # pragma: no cover - defensive worker boundary
        error_text = f"Unexpected worker error: {exc}"

    with session_scope(session_factory) as session:
        run = session.get(AiRun, execution.run_id)
        ticket = session.get(Ticket, execution.ticket_id)
        if run is None or ticket is None:
            raise LookupError("Run or ticket disappeared while finishing worker execution")

        if error_text is not None or payload is None:
            result = finalize_failure(
                session,
                ticket=ticket,
                run=run,
                error_text=error_text or "Unknown AI execution failure",
                completed_at=completed_at,
            )
            _log(
                "ai_run_failed",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
                error_text=run.error_text,
            )
            return result.run_status

        try:
            validated_output = validate_triage_payload(payload, settings=settings, ticket=ticket)
        except Exception as exc:
            result = finalize_failure(
                session,
                ticket=ticket,
                run=run,
                error_text=str(exc),
                completed_at=completed_at,
            )
            _log(
                "ai_run_failed",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
                error_text=run.error_text,
            )
            return result.run_status

        context = load_ticket_run_context(session, ticket_id=ticket.id)
        publication_fingerprint = compute_publication_fingerprint(context)
        if ticket.requeue_requested or publication_fingerprint != run.input_hash:
            if not ticket.requeue_requested:
                ticket.requeue_requested = True
                ticket.requeue_trigger = (
                    ticket.requeue_trigger or AiRunTrigger.REQUESTER_REPLY.value
                )
            result = finalize_superseded(session, ticket=ticket, run=run, completed_at=completed_at)
            _log(
                "ai_run_superseded",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
            )
            return result.run_status

        try:
            result = finalize_success(
                session,
                ticket=ticket,
                run=run,
                output=validated_output,
                internal_body_texts=[message.body_text for message in context.internal_messages],
                publication_fingerprint=publication_fingerprint,
                completed_at=completed_at,
            )
        except Exception as exc:
            result = finalize_failure(
                session,
                ticket=ticket,
                run=run,
                error_text=str(exc),
                completed_at=completed_at,
            )
            _log(
                "ai_run_failed",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
                error_text=run.error_text,
            )
            return result.run_status

        _log(
            "ai_run_succeeded",
            run_id=run.id,
            ticket_reference=ticket.reference,
            action=ticket.last_ai_action,
            queued_requeue_run_id=result.queued_requeue_run_id,
        )
        return result.run_status


def process_next_run(
    session_factory: sessionmaker[Session],
    *,
    settings: Settings,
    claimed_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> str | None:
    execution = claim_next_run(session_factory, settings=settings, claimed_at=claimed_at)
    if execution is None:
        return None
    return finish_prepared_run(
        session_factory,
        settings=settings,
        execution=execution,
        completed_at=completed_at,
    )


def update_worker_heartbeat(
    session_factory: sessionmaker[Session],
    *,
    heartbeat_at: datetime | None = None,
) -> None:
    heartbeat_at = heartbeat_at or now_utc()
    with session_scope(session_factory) as session:
        row = session.get(SystemState, HEARTBEAT_KEY)
        payload = {"timestamp": heartbeat_at.isoformat()}
        if row is None:
            session.add(SystemState(key=HEARTBEAT_KEY, value_json=payload, updated_at=heartbeat_at))
        else:
            row.value_json = payload
            row.updated_at = heartbeat_at


def run_worker_loop(
    *,
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
    once: bool = False,
) -> None:
    resolved_settings = settings or get_settings()
    resolved_session_factory = session_factory or make_session_factory(settings=resolved_settings)
    last_heartbeat_at: datetime | None = None

    while True:
        current = now_utc()
        if last_heartbeat_at is None or (current - last_heartbeat_at).total_seconds() >= 60:
            update_worker_heartbeat(resolved_session_factory, heartbeat_at=current)
            last_heartbeat_at = current

        process_next_run(resolved_session_factory, settings=resolved_settings)
        if once:
            return
        time.sleep(resolved_settings.worker_poll_seconds)


def main() -> None:
    configure_logging(service="worker")
    run_worker_loop()


if __name__ == "__main__":
    main()

```
# End of file: worker/main.py

# File: worker/queue.py
```python
from __future__ import annotations

from datetime import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from shared.models import AiRun, AiRunStatus, AiRunTrigger, Ticket, TicketRequeueTrigger
from shared.tickets import create_pending_ai_run


def acquire_next_pending_run(session: Session) -> AiRun | None:
    query = (
        sa.select(AiRun)
        .where(AiRun.status == AiRunStatus.PENDING.value)
        .order_by(AiRun.created_at.asc(), AiRun.id.asc())
    )
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    return session.scalar(query)


def _normalize_trigger(value: str | None) -> str:
    if value in {
        TicketRequeueTrigger.REQUESTER_REPLY.value,
        TicketRequeueTrigger.MANUAL_RERUN.value,
        TicketRequeueTrigger.REOPEN.value,
    }:
        return value
    return AiRunTrigger.REQUESTER_REPLY.value


def enqueue_deferred_requeue(
    session: Session,
    *,
    ticket: Ticket,
    created_at: datetime,
    requested_by_user_id: uuid.UUID | None = None,
) -> AiRun | None:
    if not ticket.requeue_requested:
        return None

    session.flush()
    active_run = session.scalar(
        sa.select(AiRun).where(
            AiRun.ticket_id == ticket.id,
            AiRun.status.in_([AiRunStatus.PENDING.value, AiRunStatus.RUNNING.value]),
        )
    )
    if active_run is not None:
        return None

    run = create_pending_ai_run(
        session,
        ticket_id=ticket.id,
        triggered_by=_normalize_trigger(ticket.requeue_trigger),
        requested_by_user_id=requested_by_user_id,
        created_at=created_at,
    )
    ticket.requeue_requested = False
    ticket.requeue_trigger = None
    return run


```
# End of file: worker/queue.py

# File: worker/__init__.py
```python
"""Worker package for later phases."""

```
# End of file: worker/__init__.py

# File: worker/triage.py
```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

from app.render import markdown_to_plain_text
from shared.config import Settings
from shared.models import (
    AiDraft,
    AiDraftKind,
    AiDraftStatus,
    AiRun,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    StatusChangedByType,
    Ticket,
    TicketClass,
    TicketStatus,
)
from shared.tickets import (
    bump_ticket_updated_at,
    change_ticket_status,
    create_ticket_message,
    supersede_pending_drafts,
)
from worker.queue import enqueue_deferred_requeue


class RelevantPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    reason: str


class TriageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_class: Literal["support", "access_config", "data_ops", "bug", "feature", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    impact_level: Literal["low", "medium", "high", "unknown"]
    requester_language: str = Field(min_length=2)
    summary_short: str = Field(min_length=1, max_length=120)
    summary_internal: str = Field(min_length=1)
    development_needed: bool
    needs_clarification: bool
    clarifying_questions: list[str] = Field(default_factory=list, max_length=3)
    incorrect_or_conflicting_details: list[str] = Field(default_factory=list)
    evidence_found: bool
    relevant_paths: list[RelevantPath] = Field(default_factory=list)
    recommended_next_action: Literal[
        "ask_clarification",
        "auto_public_reply",
        "auto_confirm_and_route",
        "draft_public_reply",
        "route_dev_ti",
    ]
    auto_public_reply_allowed: bool
    public_reply_markdown: str = ""
    internal_note_markdown: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_action_rules(self) -> "TriageOutput":
        if (
            self.recommended_next_action == "ask_clarification"
            and (not self.needs_clarification or not self.public_reply_markdown.strip())
        ):
            raise ValueError("ask_clarification requires clarification and a public reply")
        if self.recommended_next_action == "auto_public_reply":
            if not self.auto_public_reply_allowed:
                raise ValueError("auto_public_reply requires auto_public_reply_allowed=true")
            if not self.evidence_found:
                raise ValueError("auto_public_reply requires evidence_found=true")
            if not self.public_reply_markdown.strip():
                raise ValueError("auto_public_reply requires a public reply")
            if self.ticket_class == TicketClass.UNKNOWN.value:
                raise ValueError("unknown tickets cannot auto publish")
        if self.recommended_next_action == "auto_confirm_and_route":
            if not self.auto_public_reply_allowed:
                raise ValueError("auto_confirm_and_route requires auto_public_reply_allowed=true")
            if not self.public_reply_markdown.strip():
                raise ValueError("auto_confirm_and_route requires a public reply")
        if self.recommended_next_action == "draft_public_reply":
            if self.auto_public_reply_allowed:
                raise ValueError("draft_public_reply requires auto_public_reply_allowed=false")
            if not self.public_reply_markdown.strip():
                raise ValueError("draft_public_reply requires a public reply")
        if self.recommended_next_action == "route_dev_ti" and self.public_reply_markdown is None:
            raise ValueError("route_dev_ti requires public_reply_markdown to be present")
        return self


class TriageValidationError(ValueError):
    """Raised when the AI payload violates product-level validation rules."""


@dataclass(frozen=True)
class PublicationResult:
    run_status: str
    queued_requeue_run_id: uuid.UUID | None


def guard_auto_public_reply(
    output: TriageOutput,
    *,
    internal_body_texts: list[str],
) -> TriageOutput:
    if output.recommended_next_action not in {
        "ask_clarification",
        "auto_public_reply",
        "auto_confirm_and_route",
    }:
        return output
    if not internal_body_texts:
        return output

    if output.recommended_next_action == "ask_clarification":
        return output.model_copy(
            update={
                "recommended_next_action": "route_dev_ti",
                "auto_public_reply_allowed": False,
                "public_reply_markdown": "",
            }
        )
    return output.model_copy(
        update={
            "recommended_next_action": "draft_public_reply",
            "auto_public_reply_allowed": False,
        }
    )


def validate_triage_payload(
    payload: dict[str, object],
    *,
    settings: Settings,
    ticket: Ticket,
) -> TriageOutput:
    try:
        result = TriageOutput.model_validate(payload)
    except ValidationError as exc:
        raise TriageValidationError(str(exc)) from exc

    if (
        result.recommended_next_action == "auto_public_reply"
        and result.confidence < settings.auto_support_reply_min_confidence
    ):
        raise TriageValidationError("auto_public_reply confidence is below the configured threshold")
    if (
        result.recommended_next_action == "auto_confirm_and_route"
        and result.confidence < settings.auto_confirm_intent_min_confidence
    ):
        raise TriageValidationError(
            "auto_confirm_and_route confidence is below the configured threshold"
        )
    if (
        result.recommended_next_action == "ask_clarification"
        and ticket.clarification_rounds >= 2
    ):
        raise TriageValidationError("clarification limit already reached for this ticket")
    return result


def apply_ticket_classification(ticket: Ticket, output: TriageOutput) -> None:
    ticket.ticket_class = output.ticket_class
    ticket.ai_confidence = Decimal(str(output.confidence)).quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_UP,
    )
    ticket.impact_level = output.impact_level
    ticket.development_needed = output.development_needed
    ticket.requester_language = output.requester_language


def publish_internal_ai_note(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    output: TriageOutput,
    created_at,
) -> None:
    create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=None,
        author_type=MessageAuthorType.AI,
        visibility=MessageVisibility.INTERNAL,
        source=MessageSource.AI_INTERNAL_NOTE,
        body_markdown=output.internal_note_markdown,
        body_text=markdown_to_plain_text(output.internal_note_markdown),
        ai_run_id=run.id,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)


def publish_failure_note(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    error_text: str,
    created_at,
) -> None:
    body_markdown = (
        "AI triage failed for this run.\n\n"
        f"- Run ID: `{run.id}`\n"
        f"- Error: {error_text}"
    )
    create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=None,
        author_type=MessageAuthorType.SYSTEM,
        visibility=MessageVisibility.INTERNAL,
        source=MessageSource.SYSTEM,
        body_markdown=body_markdown,
        body_text=markdown_to_plain_text(body_markdown),
        ai_run_id=run.id,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)


def apply_ai_action(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    output: TriageOutput,
    acted_at,
) -> None:
    public_body_text = markdown_to_plain_text(output.public_reply_markdown)

    if output.recommended_next_action == "ask_clarification":
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.AI,
            visibility=MessageVisibility.PUBLIC,
            source=MessageSource.AI_AUTO_PUBLIC,
            body_markdown=output.public_reply_markdown,
            body_text=public_body_text,
            ai_run_id=run.id,
            created_at=acted_at,
        )
        ticket.clarification_rounds += 1
        bump_ticket_updated_at(ticket, acted_at)
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_USER,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    elif output.recommended_next_action == "auto_public_reply":
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.AI,
            visibility=MessageVisibility.PUBLIC,
            source=MessageSource.AI_AUTO_PUBLIC,
            body_markdown=output.public_reply_markdown,
            body_text=public_body_text,
            ai_run_id=run.id,
            created_at=acted_at,
        )
        bump_ticket_updated_at(ticket, acted_at)
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_USER,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    elif output.recommended_next_action == "auto_confirm_and_route":
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.AI,
            visibility=MessageVisibility.PUBLIC,
            source=MessageSource.AI_AUTO_PUBLIC,
            body_markdown=output.public_reply_markdown,
            body_text=public_body_text,
            ai_run_id=run.id,
            created_at=acted_at,
        )
        bump_ticket_updated_at(ticket, acted_at)
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_DEV_TI,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    elif output.recommended_next_action == "draft_public_reply":
        draft = AiDraft(
            ticket_id=ticket.id,
            ai_run_id=run.id,
            kind=AiDraftKind.PUBLIC_REPLY.value,
            body_markdown=output.public_reply_markdown,
            body_text=public_body_text,
            status=AiDraftStatus.PENDING_APPROVAL.value,
            created_at=acted_at,
        )
        session.add(draft)
        session.flush()
        supersede_pending_drafts(session, ticket_id=ticket.id, keep_draft_id=draft.id)
        bump_ticket_updated_at(ticket, acted_at)
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_DEV_TI,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    elif output.recommended_next_action == "route_dev_ti":
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_DEV_TI,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    else:
        raise TriageValidationError(f"Unsupported action: {output.recommended_next_action}")

    ticket.last_ai_action = output.recommended_next_action


def finalize_success(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    output: TriageOutput,
    internal_body_texts: list[str],
    publication_fingerprint: str,
    completed_at,
) -> PublicationResult:
    guarded_output = guard_auto_public_reply(
        output,
        internal_body_texts=internal_body_texts,
    )
    apply_ticket_classification(ticket, guarded_output)
    publish_internal_ai_note(
        session,
        ticket=ticket,
        run=run,
        output=guarded_output,
        created_at=completed_at,
    )
    apply_ai_action(session, ticket=ticket, run=run, output=guarded_output, acted_at=completed_at)
    ticket.last_processed_hash = publication_fingerprint
    run.status = "succeeded"
    run.ended_at = completed_at
    session.flush()
    requeue_run = enqueue_deferred_requeue(session, ticket=ticket, created_at=completed_at)
    return PublicationResult(run_status=run.status, queued_requeue_run_id=getattr(requeue_run, "id", None))


def finalize_failure(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    error_text: str,
    completed_at,
) -> PublicationResult:
    publish_failure_note(session, ticket=ticket, run=run, error_text=error_text, created_at=completed_at)
    change_ticket_status(
        session,
        ticket,
        TicketStatus.WAITING_ON_DEV_TI,
        changed_by_type=StatusChangedByType.SYSTEM,
        changed_at=completed_at,
    )
    run.status = "failed"
    run.ended_at = completed_at
    run.error_text = error_text
    session.flush()
    requeue_run = enqueue_deferred_requeue(session, ticket=ticket, created_at=completed_at)
    return PublicationResult(run_status=run.status, queued_requeue_run_id=getattr(requeue_run, "id", None))


def finalize_superseded(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    completed_at,
) -> PublicationResult:
    run.status = "superseded"
    run.ended_at = completed_at
    session.flush()
    requeue_run = enqueue_deferred_requeue(session, ticket=ticket, created_at=completed_at)
    return PublicationResult(run_status=run.status, queued_requeue_run_id=getattr(requeue_run, "id", None))


def finalize_skipped(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    completed_at,
) -> PublicationResult:
    run.status = "skipped"
    run.ended_at = completed_at
    session.flush()
    requeue_run = enqueue_deferred_requeue(session, ticket=ticket, created_at=completed_at)
    return PublicationResult(run_status=run.status, queued_requeue_run_id=getattr(requeue_run, "id", None))

```
# End of file: worker/triage.py

# File: worker/ticket_loader.py
```python
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from shared.models import (
    AttachmentVisibility,
    MessageVisibility,
    Ticket,
    TicketAttachment,
    TicketMessage,
)


@dataclass(frozen=True)
class LoadedMessage:
    id: uuid.UUID
    author_type: str
    source: str
    body_markdown: str
    body_text: str


@dataclass(frozen=True)
class LoadedAttachment:
    id: uuid.UUID
    message_id: uuid.UUID
    stored_path: str
    original_filename: str
    mime_type: str
    sha256: str
    created_order: tuple[str, str, str, str]

    @property
    def path(self) -> Path:
        return Path(self.stored_path)


@dataclass(frozen=True)
class TicketRunContext:
    ticket: Ticket
    public_messages: tuple[LoadedMessage, ...]
    internal_messages: tuple[LoadedMessage, ...]
    public_attachments: tuple[LoadedAttachment, ...]


def _load_messages(session: Session, *, ticket_id: uuid.UUID, visibility: str) -> tuple[LoadedMessage, ...]:
    messages = session.scalars(
        sa.select(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.visibility == visibility,
        )
        .order_by(TicketMessage.created_at.asc(), TicketMessage.id.asc())
    ).all()
    return tuple(
        LoadedMessage(
            id=message.id,
            author_type=message.author_type,
            source=message.source,
            body_markdown=message.body_markdown,
            body_text=message.body_text,
        )
        for message in messages
    )


def _load_public_attachments(session: Session, *, ticket_id: uuid.UUID) -> tuple[LoadedAttachment, ...]:
    rows = session.execute(
        sa.select(
            TicketAttachment,
            TicketMessage.created_at.label("message_created_at"),
        )
        .join(TicketMessage, TicketMessage.id == TicketAttachment.message_id)
        .where(
            TicketAttachment.ticket_id == ticket_id,
            TicketAttachment.visibility == AttachmentVisibility.PUBLIC.value,
            TicketMessage.visibility == MessageVisibility.PUBLIC.value,
        )
        .order_by(
            TicketMessage.created_at.asc(),
            TicketMessage.id.asc(),
            TicketAttachment.created_at.asc(),
            TicketAttachment.id.asc(),
        )
    ).all()
    return tuple(
        LoadedAttachment(
            id=attachment.id,
            message_id=attachment.message_id,
            stored_path=attachment.stored_path,
            original_filename=attachment.original_filename,
            mime_type=attachment.mime_type,
            sha256=attachment.sha256,
            created_order=(
                str(message_created_at.isoformat()),
                str(attachment.message_id),
                str(attachment.created_at.isoformat()),
                str(attachment.id),
            ),
        )
        for attachment, message_created_at in rows
    )


def load_ticket_run_context(session: Session, *, ticket_id: uuid.UUID) -> TicketRunContext:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise LookupError(f"Ticket {ticket_id} not found")
    return TicketRunContext(
        ticket=ticket,
        public_messages=_load_messages(
            session,
            ticket_id=ticket_id,
            visibility=MessageVisibility.PUBLIC.value,
        ),
        internal_messages=_load_messages(
            session,
            ticket_id=ticket_id,
            visibility=MessageVisibility.INTERNAL.value,
        ),
        public_attachments=_load_public_attachments(session, ticket_id=ticket_id),
    )


def compute_publication_fingerprint(context: TicketRunContext) -> str:
    payload = {
        "attachment_count": len(context.public_attachments),
        "public_attachments": [attachment.sha256 for attachment in context.public_attachments],
        "public_messages": [
            {
                "author_type": message.author_type,
                "body_text": message.body_text,
                "source": message.source,
            }
            for message in context.public_messages
        ],
        "status": context.ticket.status,
        "title": context.ticket.title,
        "urgent": context.ticket.urgent,
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

```
# End of file: worker/ticket_loader.py

# File: docs/acceptance_matrix.md
```markdown
# Stage 1 Acceptance Matrix

This matrix maps PRD acceptance criteria AC1-AC19 to the primary implementation surfaces and their current verification path.

| AC | Requirement | Primary code paths | Automated verification | Manual verification |
| --- | --- | --- | --- | --- |
| AC1 | Local login with optional remember-me | `app/routes_auth.py`, `app/auth.py`, `shared/security.py` | `tests/test_requester_app.py`, `tests/test_security.py` | [manual_verification.md](/workspace/docloop/triage-stage1/docs/manual_verification.md) steps 1-2 |
| AC2 | PostgreSQL-backed opaque server-side sessions | `app/auth.py`, `shared/models.py`, `shared/security.py` | `tests/test_requester_app.py`, `tests/test_models.py` | steps 1-2 |
| AC3 | Requester can only see own tickets and public content | `app/routes_requester.py`, `shared/permissions.py` | `tests/test_requester_app.py` | steps 3-4 |
| AC4 | New ticket with optional title, urgency, and PNG/JPEG images | `app/routes_requester.py`, `app/uploads.py`, `shared/tickets.py` | `tests/test_requester_app.py`, `tests/test_uploads.py` | step 3 |
| AC5 | Vague ticket produces clarification questions and `waiting_on_user` | `worker/main.py`, `worker/triage.py` | `tests/test_worker_phase4.py` | step 7 |
| AC6 | Clear support/access ticket gets safe auto-reply | `worker/main.py`, `worker/triage.py` | `tests/test_worker_phase4.py` | step 7 |
| AC7 | Safe public confirm-and-route to Dev/TI | `worker/main.py`, `worker/triage.py` | `tests/test_worker_phase4.py` | step 7 |
| AC8 | Bug/feature route publishes one internal AI note and moves to Dev/TI | `worker/main.py`, `worker/triage.py` | `tests/test_worker_phase4.py` | step 7 |
| AC9 | AI drafts can be approved or rejected | `app/routes_ops.py`, `shared/tickets.py`, `worker/triage.py` | `tests/test_ops_app.py`, `tests/test_worker_phase4.py` | step 6 |
| AC10 | Requesters never see internal notes or internal AI analysis | `app/routes_requester.py`, `shared/permissions.py` | `tests/test_requester_app.py`, `tests/test_ops_app.py` | steps 4 and 6 |
| AC11 | Automatic public AI replies never leak internal-only facts | `worker/triage.py`, `worker/main.py` | `tests/test_worker_phase4.py`, `tests/test_ops_app.py` | steps 6-7 |
| AC12 | Repo-aware read-only Codex triage over `app/` and `manuals/` | `worker/codex_runner.py`, `shared/bootstrap.py` | `tests/test_worker_phase4.py`, `tests/test_phase5_operability.py` | steps 5 and 7 |
| AC13 | No repo modification, patching, branching, or SQL Server access | `worker/codex_runner.py`, `shared/workspace_contract.py` | `tests/test_worker_phase4.py`, `tests/test_phase5_operability.py` | steps 5 and 7 |
| AC14 | Resolved ticket reopens on requester reply and requeues AI | `shared/tickets.py`, `app/routes_requester.py` | `tests/test_requester_app.py` | step 4 |
| AC15 | One active AI run per ticket with requeue behavior | `shared/models.py`, `shared/tickets.py`, `worker/queue.py`, `worker/main.py` | `tests/test_models.py`, `tests/test_ticket_helpers.py`, `tests/test_worker_phase4.py` | step 7 |
| AC16 | Stale runs are suppressed and superseded | `worker/main.py`, `worker/queue.py`, `worker/ticket_loader.py` | `tests/test_worker_phase4.py` | step 7 |
| AC17 | Uploads enforce 3-image / 5 MiB limits | `app/routes_requester.py`, `app/uploads.py`, `shared/config.py` | `tests/test_requester_app.py`, `tests/test_uploads.py` | step 3 |
| AC18 | Unread markers only clear on ticket detail or successful same-ticket POST | `app/routes_requester.py`, `app/routes_ops.py`, `shared/tickets.py` | `tests/test_requester_app.py`, `tests/test_ops_app.py` | steps 4 and 6 |
| AC19 | No Kanboard, Slack, SMTP, or external notification dependency | `app/`, `worker/`, `scripts/`, `README.md` | `tests/test_phase5_operability.py` | step 8 |

```
# End of file: docs/acceptance_matrix.md

# File: docs/triage_stage1_codebase_extract.md
```markdown
├── .env.example
├── README.md
├── alembic.ini
├── app/
│   ├── __init__.py
│   ├── auth.py
│   ├── main.py
│   ├── render.py
│   ├── routes_auth.py
│   ├── routes_ops.py
│   ├── routes_requester.py
│   ├── static/
│   │   └── styles.css
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── ops/
│   │   │   ├── board.html
│   │   │   └── detail.html
│   │   └── tickets/
│   │       ├── detail.html
│   │       ├── list.html
│   │       └── new.html
│   └── uploads.py
├── docs/
│   ├── acceptance_matrix.md
│   ├── manual_verification.md
│   └── triage_stage1_codebase_extract.md
├── requirements.txt
├── scripts/
│   ├── __init__.py
│   ├── _common.py
│   ├── bootstrap_workspace.py
│   ├── create_admin.py
│   ├── create_user.py
│   ├── deactivate_user.py
│   ├── run_web.py
│   ├── run_worker.py
│   └── set_password.py
├── shared/
│   ├── __init__.py
│   ├── bootstrap.py
│   ├── config.py
│   ├── db.py
│   ├── logging.py
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 20260319_0001_initial.py
│   ├── models.py
│   ├── permissions.py
│   ├── security.py
│   ├── tickets.py
│   ├── user_admin.py
│   └── workspace_contract.py
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_ops_app.py
│   ├── test_phase5_operability.py
│   ├── test_requester_app.py
│   ├── test_security.py
│   ├── test_ticket_helpers.py
│   ├── test_uploads.py
│   └── test_worker_phase4.py
└── worker/
    ├── __init__.py
    ├── codex_runner.py
    ├── main.py
    ├── queue.py
    ├── ticket_loader.py
    └── triage.py

# File: .env.example
```text
APP_BASE_URL=http://localhost:8000
APP_SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=postgresql+psycopg://triage:triage@localhost:5432/triage

UPLOADS_DIR=/opt/triage/data/uploads
TRIAGE_WORKSPACE_DIR=/opt/triage/triage_workspace
REPO_MOUNT_DIR=/opt/triage/triage_workspace/app
MANUALS_MOUNT_DIR=/opt/triage/triage_workspace/manuals

CODEX_BIN=codex
CODEX_API_KEY=replace-with-codex-api-key
CODEX_MODEL=
CODEX_TIMEOUT_SECONDS=75
WORKER_POLL_SECONDS=10

AUTO_SUPPORT_REPLY_MIN_CONFIDENCE=0.85
AUTO_CONFIRM_INTENT_MIN_CONFIDENCE=0.90

MAX_IMAGES_PER_MESSAGE=3
MAX_IMAGE_BYTES=5242880

SESSION_DEFAULT_HOURS=12
SESSION_REMEMBER_DAYS=30

# Operational notes:
# - /readyz checks DATABASE_URL plus UPLOADS_DIR, TRIAGE_WORKSPACE_DIR,
#   REPO_MOUNT_DIR, MANUALS_MOUNT_DIR, TRIAGE_WORKSPACE_DIR/runs,
#   TRIAGE_WORKSPACE_DIR/AGENTS.md, and
#   TRIAGE_WORKSPACE_DIR/.agents/skills/stage1-triage/SKILL.md.
# - python scripts/bootstrap_workspace.py initializes the workspace git repo,
#   writes the exact agent artifacts, and records system_state.bootstrap_version.

```
# End of file: .env.example

# File: alembic.ini
```text
[alembic]
script_location = shared/migrations
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s

```
# End of file: alembic.ini

# File: requirements.txt
```text
fastapi
uvicorn
jinja2
sqlalchemy>=2.0
alembic
psycopg[binary]
pydantic>=2.0
pillow
markdown-it-py
bleach
argon2-cffi
httpx
python-multipart
pytest

```
# End of file: requirements.txt

# File: README.md
```markdown
# Stage 1 AI Triage MVP

This subproject contains the isolated implementation for the Stage 1 custom Python triage application described in the frozen PRD.

Current implementation coverage includes:
- FastAPI requester and Dev/TI UI surfaces with PostgreSQL-backed auth/session state
- worker queue processing and read-only Codex orchestration
- bootstrap and operability scripts for the mandated WSL workspace layout
- local CLI administration for user creation, password reset, and deactivation
- health/readiness endpoints, structured JSON logs, and worker heartbeat persistence

Additional acceptance artifacts:
- [docs/acceptance_matrix.md](/workspace/docloop/triage-stage1/docs/acceptance_matrix.md)
- [docs/manual_verification.md](/workspace/docloop/triage-stage1/docs/manual_verification.md)

**Local Setup**

Create an isolated Python 3.12 environment and install the Stage 1 dependencies:

```bash
cd triage-stage1
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

**Environment**

Copy `.env.example` and provide all required values. Recommended defaults already match the PRD for:
- `UPLOADS_DIR=/opt/triage/data/uploads`
- `TRIAGE_WORKSPACE_DIR=/opt/triage/triage_workspace`
- `REPO_MOUNT_DIR=/opt/triage/triage_workspace/app`
- `MANUALS_MOUNT_DIR=/opt/triage/triage_workspace/manuals`
- `CODEX_TIMEOUT_SECONDS=75`
- `WORKER_POLL_SECONDS=10`

The repo and manuals mounts must exist and be readable before `/readyz` will report ready.

**Database**

Apply the Alembic schema before bootstrapping the workspace:

```bash
alembic upgrade head
```

**Bootstrap**

Run the bootstrap script after migrations and before starting the services:

```bash
python scripts/bootstrap_workspace.py
```

It creates or validates:
- the uploads directory
- the workspace root and `runs/`
- the workspace Git repository and initial empty commit
- the exact `AGENTS.md` and `.agents/skills/stage1-triage/SKILL.md`
- the `system_state.bootstrap_version` marker

**Management commands**

```bash
python scripts/create_admin.py --email admin@example.com --display-name "Admin User" --password "change-me"
python scripts/create_user.py --email requester@example.com --display-name "Requester User" --password "change-me" --role requester
python scripts/set_password.py --email requester@example.com --password "new-secret"
python scripts/deactivate_user.py --email requester@example.com
```

**Run**

Start the web app and worker in separate shells after the database, mounts, and workspace bootstrap are ready:

```bash
python scripts/run_web.py --host 0.0.0.0 --port 8000
python scripts/run_worker.py
```

Health endpoints:
- `GET /healthz` returns process liveness
- `GET /readyz` verifies database reachability plus uploads/workspace/mount/agent artifact readiness

**Acceptance Coverage**

- Automated regression coverage lives under `tests/` and now includes session behavior, requester isolation, upload validation limits, unread tracking, worker queue invariants, draft handling, and non-leak safeguards.
- AC1-AC19 traceability is captured in [docs/acceptance_matrix.md](/workspace/docloop/triage-stage1/docs/acceptance_matrix.md).
- A concise operator smoke test is captured in [docs/manual_verification.md](/workspace/docloop/triage-stage1/docs/manual_verification.md).

```
# End of file: README.md

# File: app/routes_auth.py
```python
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

```
# End of file: app/routes_auth.py

# File: app/routes_requester.py
```python
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.auth import (
    AuthContext,
    get_db_session,
    get_settings,
    get_templates,
    require_auth_context,
    require_requester,
    require_session_csrf,
    template_context,
)
from app.render import markdown_to_plain_text, markdown_to_safe_html
from app.uploads import (
    UploadValidationError,
    cleanup_written_uploads,
    persist_validated_uploads,
    validate_public_image_uploads,
)
from shared.models import AttachmentVisibility, MessageVisibility, Ticket, TicketAttachment, TicketMessage, TicketView, TicketStatus
from shared.permissions import PermissionDeniedError, ensure_dev_ti, ensure_requester_attachment_access
from shared.tickets import (
    add_requester_reply,
    create_requester_ticket,
    mark_ticket_resolved,
    upsert_ticket_view,
)


router = APIRouter()


REQUESTER_STATUS_LABELS = {
    TicketStatus.NEW.value: "Reviewing",
    TicketStatus.AI_TRIAGE.value: "Reviewing",
    TicketStatus.WAITING_ON_USER.value: "Waiting for your reply",
    TicketStatus.WAITING_ON_DEV_TI.value: "Waiting on team",
    TicketStatus.RESOLVED.value: "Resolved",
}


def requester_status_label(status: str) -> str:
    return REQUESTER_STATUS_LABELS.get(status, status.replace("_", " ").title())


def _get_owned_ticket_or_404(db: Session, *, reference: str, user_id) -> Ticket:
    ticket = db.scalar(
        select(Ticket).where(
            Ticket.reference == reference,
            Ticket.created_by_user_id == user_id,
        )
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def _build_ticket_thread(
    db: Session,
    *,
    ticket_id,
) -> list[dict[str, object]]:
    messages = db.scalars(
        select(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.visibility == MessageVisibility.PUBLIC.value,
        )
        .order_by(TicketMessage.created_at.asc(), TicketMessage.id.asc())
    ).all()
    message_ids = [message.id for message in messages]
    attachments_by_message: dict[object, list[TicketAttachment]] = defaultdict(list)
    if message_ids:
        attachments = db.scalars(
            select(TicketAttachment)
            .where(
                TicketAttachment.message_id.in_(message_ids),
                TicketAttachment.visibility == AttachmentVisibility.PUBLIC.value,
            )
            .order_by(TicketAttachment.created_at.asc(), TicketAttachment.id.asc())
        ).all()
        for attachment in attachments:
            attachments_by_message[attachment.message_id].append(attachment)

    rendered: list[dict[str, object]] = []
    for message in messages:
        author_label = "You" if message.author_type == "requester" else message.author_type.replace("_", " ").title()
        rendered.append(
            {
                "id": str(message.id),
                "author_label": author_label,
                "created_at": message.created_at,
                "body_html": markdown_to_safe_html(message.body_markdown),
                "attachments": attachments_by_message.get(message.id, []),
            }
        )
    return rendered


def _render_ticket_detail(
    request: Request,
    *,
    auth: AuthContext,
    db: Session,
    ticket: Ticket,
    error: str | None = None,
    reply_body: str = "",
):
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "tickets/detail.html",
        template_context(
            request,
            auth=auth,
            ticket=ticket,
            requester_status=requester_status_label(ticket.status),
            thread=_build_ticket_thread(db, ticket_id=ticket.id),
            error=error,
            reply_body=reply_body,
        ),
    )


@router.get("/app")
def requester_home(
    auth: AuthContext = Depends(require_requester),
):
    return RedirectResponse(url="/app/tickets", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/app/tickets")
def ticket_list(
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    templates = get_templates(request)
    rows = db.execute(
        select(Ticket, TicketView.last_viewed_at)
        .outerjoin(
            TicketView,
            and_(
                TicketView.ticket_id == Ticket.id,
                TicketView.user_id == auth.user.id,
            ),
        )
        .where(Ticket.created_by_user_id == auth.user.id)
        .order_by(Ticket.updated_at.desc(), Ticket.id.desc())
    ).all()

    tickets = []
    for ticket, last_viewed_at in rows:
        tickets.append(
            {
                "reference": ticket.reference,
                "title": ticket.title,
                "status": requester_status_label(ticket.status),
                "urgent": ticket.urgent,
                "updated": last_viewed_at is None or ticket.updated_at > last_viewed_at,
                "updated_at": ticket.updated_at,
            }
        )

    return templates.TemplateResponse(
        request,
        "tickets/list.html",
        template_context(request, auth=auth, tickets=tickets),
    )


@router.get("/app/tickets/new")
def new_ticket_page(
    request: Request,
    auth: AuthContext = Depends(require_requester),
):
    templates = get_templates(request)
    return templates.TemplateResponse(
        request,
        "tickets/new.html",
        template_context(
            request,
            auth=auth,
            title_value="",
            description_value="",
            urgent=False,
            error=None,
        ),
    )


@router.post("/app/tickets")
async def create_ticket_submit(
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    settings = get_settings(request)
    templates = get_templates(request)
    form = await request.form(
        max_files=settings.max_images_per_message,
        max_part_size=settings.max_image_bytes,
    )
    require_session_csrf(auth, str(form.get("csrf_token", "")))

    title = str(form.get("title", "")).strip()
    description_markdown = str(form.get("description", "")).strip()
    urgent = str(form.get("urgent", "")).lower() in {"1", "true", "on", "yes"}
    if not description_markdown:
        return templates.TemplateResponse(
            request,
            "tickets/new.html",
            template_context(
                request,
                auth=auth,
                title_value=title,
                description_value=description_markdown,
                urgent=urgent,
                error="Description is required.",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validated_uploads = await validate_public_image_uploads(form, settings)
    except UploadValidationError as exc:
        return templates.TemplateResponse(
            request,
            "tickets/new.html",
            template_context(
                request,
                auth=auth,
                title_value=title,
                description_value=description_markdown,
                urgent=urgent,
                error=str(exc),
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    written_paths = []
    description_text = markdown_to_plain_text(description_markdown)
    try:
        ticket, message, _ = create_requester_ticket(
            db,
            creator=auth.user,
            title=title or None,
            description_markdown=description_markdown,
            description_text=description_text,
            urgent=urgent,
        )
        db.flush()
        attachments, written_paths = persist_validated_uploads(
            validated_uploads,
            uploads_dir=settings.uploads_dir,
            ticket_id=ticket.id,
            message_id=message.id,
        )
        for attachment in attachments:
            db.add(attachment)
        db.commit()
    except Exception:
        db.rollback()
        cleanup_written_uploads(written_paths)
        raise

    return RedirectResponse(
        url=f"/app/tickets/{ticket.reference}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/app/tickets/{reference}")
def ticket_detail(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    ticket = _get_owned_ticket_or_404(db, reference=reference, user_id=auth.user.id)
    upsert_ticket_view(db, user_id=auth.user.id, ticket_id=ticket.id)
    db.commit()
    return _render_ticket_detail(request, auth=auth, db=db, ticket=ticket)


@router.post("/app/tickets/{reference}/reply")
async def ticket_reply(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    settings = get_settings(request)
    form = await request.form(
        max_files=settings.max_images_per_message,
        max_part_size=settings.max_image_bytes,
    )
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_owned_ticket_or_404(db, reference=reference, user_id=auth.user.id)

    body_markdown = str(form.get("body", "")).strip()
    try:
        validated_uploads = await validate_public_image_uploads(form, settings)
    except UploadValidationError as exc:
        return _render_ticket_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error=str(exc),
            reply_body=body_markdown,
        )

    if not body_markdown and not validated_uploads:
        return _render_ticket_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Reply text or an image is required.",
            reply_body=body_markdown,
        )

    written_paths = []
    try:
        message, _ = add_requester_reply(
            db,
            ticket=ticket,
            requester=auth.user,
            body_markdown=body_markdown,
            body_text=markdown_to_plain_text(body_markdown) if body_markdown else "",
        )
        db.flush()
        attachments, written_paths = persist_validated_uploads(
            validated_uploads,
            uploads_dir=settings.uploads_dir,
            ticket_id=ticket.id,
            message_id=message.id,
        )
        for attachment in attachments:
            db.add(attachment)
        db.commit()
    except Exception:
        db.rollback()
        cleanup_written_uploads(written_paths)
        raise

    return RedirectResponse(
        url=f"/app/tickets/{ticket.reference}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/app/tickets/{reference}/resolve")
async def ticket_resolve(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_requester),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_owned_ticket_or_404(db, reference=reference, user_id=auth.user.id)
    mark_ticket_resolved(
        db,
        ticket=ticket,
        user=auth.user,
        changed_by_type="requester",
    )
    db.commit()
    return RedirectResponse(
        url=f"/app/tickets/{ticket.reference}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/attachments/{attachment_id}")
def download_attachment(
    attachment_id: str,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_auth_context),
):
    try:
        attachment_uuid = uuid.UUID(attachment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found") from exc

    attachment = db.get(TicketAttachment, attachment_uuid)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    ticket = db.get(Ticket, attachment.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    try:
        if auth.user.role == "requester":
            ensure_requester_attachment_access(auth.user, ticket, attachment)
        else:
            ensure_dev_ti(auth.user)
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return FileResponse(
        Path(attachment.stored_path),
        media_type=attachment.mime_type,
        filename=attachment.original_filename,
    )

```
# End of file: app/routes_requester.py

# File: app/uploads.py
```python
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import hashlib
import uuid

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from starlette.datastructures import FormData, UploadFile as StarletteUploadFile

from shared.config import Settings
from shared.models import AttachmentVisibility, TicketAttachment


ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
}


class UploadValidationError(ValueError):
    """Raised when an uploaded file violates Stage 1 rules."""


@dataclass(frozen=True)
class ValidatedImageUpload:
    attachment_id: uuid.UUID
    original_filename: str
    mime_type: str
    data: bytes
    sha256: str
    size_bytes: int
    width: int
    height: int
    suffix: str


def extract_upload_files(form: FormData, *, field_name: str = "attachments") -> list[UploadFile]:
    files: list[UploadFile] = []
    for value in form.getlist(field_name):
        if isinstance(value, (UploadFile, StarletteUploadFile)) and value.filename:
            files.append(value)
    return files


async def validate_public_image_uploads(
    form: FormData,
    settings: Settings,
    *,
    field_name: str = "attachments",
) -> list[ValidatedImageUpload]:
    files = extract_upload_files(form, field_name=field_name)
    if len(files) > settings.max_images_per_message:
        raise UploadValidationError(
            f"You can upload at most {settings.max_images_per_message} images per message."
        )

    validated: list[ValidatedImageUpload] = []
    for upload in files:
        mime_type = (upload.content_type or "").lower()
        suffix = ALLOWED_IMAGE_TYPES.get(mime_type)
        if suffix is None:
            raise UploadValidationError("Only PNG and JPEG images are allowed.")

        data = await upload.read()
        await upload.close()
        size_bytes = len(data)
        if size_bytes > settings.max_image_bytes:
            raise UploadValidationError(
                f"Each image must be {settings.max_image_bytes} bytes or smaller."
            )
        if size_bytes == 0:
            raise UploadValidationError("Uploaded images must not be empty.")

        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
            with Image.open(BytesIO(data)) as image:
                width, height = image.size
        except (UnidentifiedImageError, OSError) as exc:
            raise UploadValidationError("Uploaded files must be valid images.") from exc

        validated.append(
            ValidatedImageUpload(
                attachment_id=uuid.uuid4(),
                original_filename=upload.filename or "image",
                mime_type=mime_type,
                data=data,
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=size_bytes,
                width=width,
                height=height,
                suffix=suffix,
            )
        )
    return validated


def persist_validated_uploads(
    uploads: list[ValidatedImageUpload],
    *,
    uploads_dir: Path,
    ticket_id: uuid.UUID,
    message_id: uuid.UUID,
) -> tuple[list[TicketAttachment], list[Path]]:
    attachments: list[TicketAttachment] = []
    written_paths: list[Path] = []

    target_dir = uploads_dir / str(ticket_id) / str(message_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    for upload in uploads:
        stored_path = target_dir / f"{upload.attachment_id}{upload.suffix}"
        with stored_path.open("wb") as handle:
            handle.write(upload.data)
        written_paths.append(stored_path)
        attachments.append(
            TicketAttachment(
                id=upload.attachment_id,
                ticket_id=ticket_id,
                message_id=message_id,
                visibility=AttachmentVisibility.PUBLIC.value,
                original_filename=upload.original_filename,
                stored_path=str(stored_path),
                mime_type=upload.mime_type,
                sha256=upload.sha256,
                size_bytes=upload.size_bytes,
                width=upload.width,
                height=upload.height,
            )
        )
    return attachments, written_paths


def cleanup_written_uploads(paths: list[Path]) -> None:
    for path in reversed(paths):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue
        parent = path.parent
        while parent.name and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

```
# End of file: app/uploads.py

# File: app/auth.py
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from shared.config import Settings
from shared.models import SessionRecord, User, UserRole
from shared.security import (
    LOGIN_CSRF_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    generate_csrf_token,
    generate_login_csrf_token,
    generate_session_token,
    hash_token,
    session_expires_at,
    session_max_age,
    should_use_secure_cookies,
    utcnow,
    validate_login_csrf_token,
)


@dataclass
class AuthContext:
    user: User
    session_record: SessionRecord


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_templates(request: Request):
    return request.app.state.templates


def get_db_session(request: Request) -> Iterator[Session]:
    session_factory = get_session_factory(request)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def _get_session_record(db: Session, raw_token: str | None) -> SessionRecord | None:
    if not raw_token:
        return None
    return db.scalar(
        select(SessionRecord).where(SessionRecord.token_hash == hash_token(raw_token))
    )


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_optional_auth_context(
    request: Request,
    db: Session = Depends(get_db_session),
) -> AuthContext | None:
    record = _get_session_record(db, request.cookies.get(SESSION_COOKIE_NAME))
    if record is None:
        return None
    if _normalize_datetime(record.expires_at) <= utcnow():
        return None

    user = db.scalar(
        select(User).where(
            User.id == record.user_id,
            User.is_active.is_(True),
        )
    )
    if user is None:
        return None
    return AuthContext(user=user, session_record=record)


def require_auth_context(
    auth: AuthContext | None = Depends(get_optional_auth_context),
) -> AuthContext:
    if auth is None:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return auth


def require_requester(
    auth: AuthContext = Depends(require_auth_context),
) -> AuthContext:
    if auth.user.role != UserRole.REQUESTER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requester access required")
    return auth


def require_dev_ti(
    auth: AuthContext = Depends(require_auth_context),
) -> AuthContext:
    if auth.user.role not in {UserRole.DEV_TI.value, UserRole.ADMIN.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dev/TI access required")
    return auth


def create_session(
    db: Session,
    *,
    user: User,
    settings: Settings,
    remember_me: bool,
    user_agent: str | None,
    ip_address: str | None,
    now: datetime | None = None,
) -> tuple[SessionRecord, str]:
    now = now or utcnow()
    raw_token = generate_session_token()
    record = SessionRecord(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        csrf_token=generate_csrf_token(),
        remember_me=remember_me,
        expires_at=session_expires_at(settings, remember_me=remember_me, now=now),
        last_seen_at=now,
        created_at=now,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    user.last_login_at = now
    db.add(record)
    db.flush()
    return record, raw_token


def set_session_cookie(
    response: Response,
    *,
    settings: Settings,
    raw_token: str,
    remember_me: bool,
) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        raw_token,
        httponly=True,
        secure=should_use_secure_cookies(settings),
        samesite="lax",
        max_age=session_max_age(settings, remember_me=remember_me),
        path="/",
    )


def clear_session_cookie(response: Response, *, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=should_use_secure_cookies(settings),
        samesite="lax",
    )


def issue_login_csrf(response: Response, settings: Settings) -> str:
    token = generate_login_csrf_token(settings.app_secret_key)
    response.set_cookie(
        LOGIN_CSRF_COOKIE_NAME,
        token,
        httponly=True,
        secure=should_use_secure_cookies(settings),
        samesite="lax",
        path="/",
    )
    return token


def clear_login_csrf(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        LOGIN_CSRF_COOKIE_NAME,
        path="/",
        secure=should_use_secure_cookies(settings),
        samesite="lax",
    )


def validate_login_csrf(request: Request, submitted_token: str, settings: Settings) -> bool:
    cookie_token = request.cookies.get(LOGIN_CSRF_COOKIE_NAME, "")
    if not submitted_token or submitted_token != cookie_token:
        return False
    return validate_login_csrf_token(settings.app_secret_key, submitted_token)


def require_session_csrf(auth: AuthContext, submitted_token: str) -> None:
    if not submitted_token or submitted_token != auth.session_record.csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def template_context(
    request: Request,
    *,
    auth: AuthContext | None,
    csrf_token: str | None = None,
    **extra: object,
) -> dict[str, object]:
    context: dict[str, object] = {
        "request": request,
        "current_user": auth.user if auth else None,
        "session_csrf_token": auth.session_record.csrf_token if auth else "",
        "csrf_token": csrf_token if csrf_token is not None else (auth.session_record.csrf_token if auth else ""),
    }
    context.update(extra)
    return context

```
# End of file: app/auth.py

# File: app/main.py
```python
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

```
# End of file: app/main.py

# File: app/__init__.py
```python
"""Web application package for later phases."""

```
# End of file: app/__init__.py

# File: app/render.py
```python
from __future__ import annotations

import re

import bleach
from markdown_it import MarkdownIt
from markupsafe import Markup


_MARKDOWN = MarkdownIt("commonmark", {"html": False})
_ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS).union(
    {"p", "pre", "code", "br", "ul", "ol", "li", "strong", "em", "blockquote"}
)
_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
}


def normalize_plain_text(text: str) -> str:
    collapsed = text.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = re.sub(r"[ \t]+", " ", collapsed)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def markdown_to_plain_text(markdown: str) -> str:
    rendered = _MARKDOWN.render(markdown or "")
    text = bleach.clean(rendered, tags=[], strip=True)
    return normalize_plain_text(text)


def markdown_to_safe_html(markdown: str) -> Markup:
    rendered = _MARKDOWN.render(markdown or "")
    sanitized = bleach.clean(
        rendered,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        strip=True,
    )
    linkified = bleach.linkify(sanitized)
    return Markup(linkified)

```
# End of file: app/render.py

# File: app/routes_ops.py
```python
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import uuid

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session

from app.auth import (
    AuthContext,
    get_db_session,
    get_templates,
    require_dev_ti,
    require_session_csrf,
    template_context,
)
from app.render import markdown_to_plain_text, markdown_to_safe_html
from shared.models import (
    AiDraft,
    AiDraftStatus,
    AiRun,
    AttachmentVisibility,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    Ticket,
    TicketAttachment,
    TicketClass,
    TicketMessage,
    TicketStatus,
    TicketView,
    User,
    UserRole,
)
from shared.permissions import ensure_dev_ti
from shared.tickets import (
    InvalidDraftStateError,
    add_internal_note,
    add_public_reply,
    approve_ai_draft,
    request_manual_rerun,
    reject_ai_draft,
    set_ticket_assignment,
    set_ticket_status_for_ops,
    upsert_ticket_view,
)


router = APIRouter()


OPS_STATUS_ORDER = [
    TicketStatus.NEW.value,
    TicketStatus.AI_TRIAGE.value,
    TicketStatus.WAITING_ON_USER.value,
    TicketStatus.WAITING_ON_DEV_TI.value,
    TicketStatus.RESOLVED.value,
]
OPS_STATUS_LABELS = {
    TicketStatus.NEW.value: "New",
    TicketStatus.AI_TRIAGE.value: "AI Triage",
    TicketStatus.WAITING_ON_USER.value: "Waiting on User",
    TicketStatus.WAITING_ON_DEV_TI.value: "Waiting on Dev/TI",
    TicketStatus.RESOLVED.value: "Resolved",
}
REPLY_STATUS_OPTIONS = [
    TicketStatus.WAITING_ON_USER.value,
    TicketStatus.WAITING_ON_DEV_TI.value,
    TicketStatus.RESOLVED.value,
]


def ops_status_label(value: str) -> str:
    return OPS_STATUS_LABELS.get(value, value.replace("_", " ").title())


def _parse_bool(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "on", "yes"}


def _get_ticket_or_404(db: Session, *, reference: str) -> Ticket:
    ticket = db.scalar(select(Ticket).where(Ticket.reference == reference))
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def _get_draft_or_404(db: Session, *, draft_id: str) -> AiDraft:
    try:
        draft_uuid = uuid.UUID(draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found") from exc
    draft = db.get(AiDraft, draft_uuid)
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return draft


def _load_ops_users(db: Session) -> list[User]:
    return db.scalars(
        select(User)
        .where(
            User.is_active.is_(True),
            User.role.in_([UserRole.DEV_TI.value, UserRole.ADMIN.value]),
        )
        .order_by(User.display_name.asc(), User.email.asc())
    ).all()


def _build_thread(
    db: Session,
    *,
    ticket_id: uuid.UUID,
    visibility: str,
) -> list[dict[str, object]]:
    messages = db.scalars(
        select(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.visibility == visibility,
        )
        .order_by(TicketMessage.created_at.asc(), TicketMessage.id.asc())
    ).all()
    attachments_by_message: dict[uuid.UUID, list[TicketAttachment]] = defaultdict(list)
    message_ids = [message.id for message in messages]
    if message_ids:
        attachments = db.scalars(
            select(TicketAttachment)
            .where(
                TicketAttachment.message_id.in_(message_ids),
                TicketAttachment.visibility
                == (
                    AttachmentVisibility.PUBLIC.value
                    if visibility == MessageVisibility.PUBLIC.value
                    else AttachmentVisibility.INTERNAL.value
                ),
            )
            .order_by(TicketAttachment.created_at.asc(), TicketAttachment.id.asc())
        ).all()
        for attachment in attachments:
            attachments_by_message[attachment.message_id].append(attachment)

    rendered: list[dict[str, object]] = []
    for message in messages:
        author_label = "AI" if message.author_type == MessageAuthorType.AI.value else message.author_type.replace("_", " ").title()
        if message.author_type == MessageAuthorType.DEV_TI.value and message.author_user_id:
            author = db.get(User, message.author_user_id)
            if author is not None:
                author_label = author.display_name
        if message.author_type == MessageAuthorType.REQUESTER.value and message.author_user_id:
            author = db.get(User, message.author_user_id)
            if author is not None:
                author_label = author.display_name
        rendered.append(
            {
                "id": str(message.id),
                "author_label": author_label,
                "source_label": message.source.replace("_", " ").title(),
                "created_at": message.created_at,
                "body_html": markdown_to_safe_html(message.body_markdown),
                "attachments": attachments_by_message.get(message.id, []),
            }
        )
    return rendered


def _load_relevant_paths(latest_run: AiRun | None) -> list[dict[str, str]]:
    if latest_run is None or not latest_run.final_output_path:
        return []
    output_path = Path(latest_run.final_output_path)
    if not output_path.exists():
        return []
    try:
        payload = json.loads(output_path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    relevant_paths = payload.get("relevant_paths")
    if not isinstance(relevant_paths, list):
        return []
    normalized: list[dict[str, str]] = []
    for item in relevant_paths:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        reason = item.get("reason")
        if isinstance(path, str) and isinstance(reason, str):
            normalized.append({"path": path, "reason": reason})
    return normalized


def _load_ops_detail_context(db: Session, *, ticket: Ticket) -> dict[str, object]:
    creator = db.get(User, ticket.created_by_user_id)
    assignee = db.get(User, ticket.assigned_to_user_id) if ticket.assigned_to_user_id else None
    latest_ai_note = db.scalar(
        select(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket.id,
            TicketMessage.visibility == MessageVisibility.INTERNAL.value,
            TicketMessage.author_type == MessageAuthorType.AI.value,
            TicketMessage.source == MessageSource.AI_INTERNAL_NOTE.value,
        )
        .order_by(TicketMessage.created_at.desc(), TicketMessage.id.desc())
    )
    latest_run = db.scalar(
        select(AiRun)
        .where(AiRun.ticket_id == ticket.id)
        .order_by(AiRun.created_at.desc(), AiRun.id.desc())
    )
    pending_draft = db.scalar(
        select(AiDraft)
        .where(
            AiDraft.ticket_id == ticket.id,
            AiDraft.status == AiDraftStatus.PENDING_APPROVAL.value,
        )
        .order_by(AiDraft.created_at.desc(), AiDraft.id.desc())
    )
    latest_draft = db.scalar(
        select(AiDraft)
        .where(AiDraft.ticket_id == ticket.id)
        .order_by(AiDraft.created_at.desc(), AiDraft.id.desc())
    )
    return {
        "ticket": ticket,
        "creator": creator,
        "assignee": assignee,
        "public_thread": _build_thread(db, ticket_id=ticket.id, visibility=MessageVisibility.PUBLIC.value),
        "internal_thread": _build_thread(db, ticket_id=ticket.id, visibility=MessageVisibility.INTERNAL.value),
        "latest_ai_note_html": (
            markdown_to_safe_html(latest_ai_note.body_markdown) if latest_ai_note is not None else None
        ),
        "latest_ai_note_at": latest_ai_note.created_at if latest_ai_note is not None else None,
        "latest_run": latest_run,
        "relevant_paths": _load_relevant_paths(latest_run),
        "pending_draft": pending_draft,
        "pending_draft_html": (
            markdown_to_safe_html(pending_draft.body_markdown) if pending_draft is not None else None
        ),
        "latest_draft": latest_draft,
        "ops_users": _load_ops_users(db),
        "reply_status_options": [(value, ops_status_label(value)) for value in REPLY_STATUS_OPTIONS],
        "status_options": [(value, ops_status_label(value)) for value in OPS_STATUS_ORDER],
    }


def _render_ops_detail(
    request: Request,
    *,
    auth: AuthContext,
    db: Session,
    ticket: Ticket,
    error: str | None = None,
    public_reply_body: str = "",
    internal_note_body: str = "",
    next_status: str | None = None,
):
    templates = get_templates(request)
    context = _load_ops_detail_context(db, ticket=ticket)
    context.update(
        {
            "error": error,
            "public_reply_body": public_reply_body,
            "internal_note_body": internal_note_body,
            "selected_next_status": next_status or TicketStatus.WAITING_ON_USER.value,
        }
    )
    return templates.TemplateResponse(
        request,
        "ops/detail.html",
        template_context(request, auth=auth, **context),
        status_code=status.HTTP_400_BAD_REQUEST if error else status.HTTP_200_OK,
    )


def _selected_filters(request: Request) -> dict[str, str]:
    return {
        "status": request.query_params.get("status", ""),
        "ticket_class": request.query_params.get("ticket_class", ""),
        "assigned_to": request.query_params.get("assigned_to", ""),
        "urgent": request.query_params.get("urgent", ""),
        "unassigned_only": request.query_params.get("unassigned_only", ""),
        "created_by_me": request.query_params.get("created_by_me", ""),
        "needs_approval": request.query_params.get("needs_approval", ""),
        "updated_since_my_last_view": request.query_params.get("updated_since_my_last_view", ""),
    }


def _board_rows(db: Session, *, auth: AuthContext, filters: dict[str, str]) -> list[dict[str, object]]:
    last_viewed_at = TicketView.last_viewed_at.label("last_viewed_at")
    needs_approval = exists(
        select(1).where(
            AiDraft.ticket_id == Ticket.id,
            AiDraft.status == AiDraftStatus.PENDING_APPROVAL.value,
        )
    )
    query = (
        select(Ticket, User.display_name.label("creator_name"), last_viewed_at, needs_approval.label("needs_approval"))
        .join(User, User.id == Ticket.created_by_user_id)
        .outerjoin(
            TicketView,
            and_(TicketView.ticket_id == Ticket.id, TicketView.user_id == auth.user.id),
        )
    )

    if filters["status"]:
        query = query.where(Ticket.status == filters["status"])
    if filters["ticket_class"]:
        query = query.where(Ticket.ticket_class == filters["ticket_class"])
    if filters["assigned_to"]:
        try:
            assigned_uuid = uuid.UUID(filters["assigned_to"])
        except ValueError:
            assigned_uuid = None
        if assigned_uuid is not None:
            query = query.where(Ticket.assigned_to_user_id == assigned_uuid)
    if _parse_bool(filters["urgent"]):
        query = query.where(Ticket.urgent.is_(True))
    if _parse_bool(filters["unassigned_only"]):
        query = query.where(Ticket.assigned_to_user_id.is_(None))
    if _parse_bool(filters["created_by_me"]):
        query = query.where(Ticket.created_by_user_id == auth.user.id)
    if _parse_bool(filters["needs_approval"]):
        query = query.where(needs_approval)
    if _parse_bool(filters["updated_since_my_last_view"]):
        query = query.where(
            sa.or_(TicketView.last_viewed_at.is_(None), Ticket.updated_at > TicketView.last_viewed_at)
        )

    query = query.order_by(Ticket.updated_at.desc(), Ticket.id.desc())
    rows = db.execute(query).all()

    assignee_ids = {ticket.assigned_to_user_id for ticket, _, _, _ in rows if ticket.assigned_to_user_id}
    assignees = {
        user.id: user.display_name
        for user in db.scalars(select(User).where(User.id.in_(assignee_ids))).all()
    }
    rendered: list[dict[str, object]] = []
    for ticket, creator_name, viewed_at, has_pending_draft in rows:
        rendered.append(
            {
                "reference": ticket.reference,
                "title": ticket.title,
                "status": ticket.status,
                "status_label": ops_status_label(ticket.status),
                "creator_name": creator_name,
                "assignee_name": assignees.get(ticket.assigned_to_user_id),
                "ticket_class": ticket.ticket_class or "unclassified",
                "urgent": ticket.urgent,
                "needs_approval": bool(has_pending_draft),
                "updated": viewed_at is None or ticket.updated_at > viewed_at,
                "updated_at": ticket.updated_at,
            }
        )
    return rendered


@router.get("/ops")
def ops_home(auth: AuthContext = Depends(require_dev_ti)):
    return RedirectResponse(url="/ops/board", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/ops/board")
def ops_board(
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    templates = get_templates(request)
    filters = _selected_filters(request)
    rows = _board_rows(db, auth=auth, filters=filters)
    columns: list[dict[str, object]] = []
    for status_value in OPS_STATUS_ORDER:
        items = [row for row in rows if row["status"] == status_value]
        columns.append(
            {
                "status": status_value,
                "label": ops_status_label(status_value),
                "tickets": items,
            }
        )
    return templates.TemplateResponse(
        request,
        "ops/board.html",
        template_context(
            request,
            auth=auth,
            columns=columns,
            filters=filters,
            ticket_class_options=[item.value for item in TicketClass],
            assignee_options=_load_ops_users(db),
        ),
    )


@router.get("/ops/tickets/{reference}")
def ops_ticket_detail(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    ticket = _get_ticket_or_404(db, reference=reference)
    upsert_ticket_view(db, user_id=auth.user.id, ticket_id=ticket.id)
    db.commit()
    return _render_ops_detail(request, auth=auth, db=db, ticket=ticket)


@router.post("/ops/tickets/{reference}/assign")
async def assign_ticket(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    raw_assignee = str(form.get("assigned_to_user_id", "")).strip()
    assigned_to_user_id: uuid.UUID | None = None
    if raw_assignee:
        try:
            assigned_to_user_id = uuid.UUID(raw_assignee)
        except ValueError:
            return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error="Invalid assignee.")
        assignee = db.get(User, assigned_to_user_id)
        if assignee is None:
            return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error="Assignee not found.")
        try:
            ensure_dev_ti(assignee)
        except ValueError:
            return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error="Assignee must be a Dev/TI or admin user.")
    set_ticket_assignment(db, ticket=ticket, assigned_to_user_id=assigned_to_user_id, actor=auth.user)
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/tickets/{reference}/set-status")
async def set_status(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    target_status = str(form.get("status", "")).strip()
    if target_status not in OPS_STATUS_LABELS:
        return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error="Invalid status.")
    set_ticket_status_for_ops(db, ticket=ticket, actor=auth.user, to_status=target_status)
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/tickets/{reference}/reply-public")
async def reply_public(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    body_markdown = str(form.get("body", "")).strip()
    next_status = str(form.get("next_status", "")).strip()
    if not body_markdown:
        return _render_ops_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Public reply text is required.",
            public_reply_body=body_markdown,
            next_status=next_status,
        )
    if next_status not in REPLY_STATUS_OPTIONS:
        return _render_ops_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Choose the next public status.",
            public_reply_body=body_markdown,
            next_status=next_status,
        )
    add_public_reply(
        db,
        ticket=ticket,
        actor=auth.user,
        body_markdown=body_markdown,
        body_text=markdown_to_plain_text(body_markdown),
        next_status=next_status,
    )
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/tickets/{reference}/note-internal")
async def note_internal(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    body_markdown = str(form.get("body", "")).strip()
    if not body_markdown:
        return _render_ops_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Internal note text is required.",
            internal_note_body=body_markdown,
        )
    add_internal_note(
        db,
        ticket=ticket,
        actor=auth.user,
        body_markdown=body_markdown,
        body_text=markdown_to_plain_text(body_markdown),
    )
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/tickets/{reference}/rerun-ai")
async def rerun_ai(
    reference: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    ticket = _get_ticket_or_404(db, reference=reference)
    request_manual_rerun(db, ticket=ticket, actor=auth.user)
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/drafts/{draft_id}/approve-publish")
async def approve_draft_publish(
    draft_id: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    draft = _get_draft_or_404(db, draft_id=draft_id)
    ticket = db.get(Ticket, draft.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    next_status = str(form.get("next_status", "")).strip()
    if next_status not in REPLY_STATUS_OPTIONS:
        return _render_ops_detail(
            request,
            auth=auth,
            db=db,
            ticket=ticket,
            error="Choose the next public status before publishing the draft.",
            next_status=next_status,
        )
    try:
        approve_ai_draft(db, ticket=ticket, draft=draft, actor=auth.user, next_status=next_status)
    except InvalidDraftStateError as exc:
        return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error=str(exc))
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/ops/drafts/{draft_id}/reject")
async def reject_draft(
    draft_id: str,
    request: Request,
    db: Session = Depends(get_db_session),
    auth: AuthContext = Depends(require_dev_ti),
):
    form = await request.form()
    require_session_csrf(auth, str(form.get("csrf_token", "")))
    draft = _get_draft_or_404(db, draft_id=draft_id)
    ticket = db.get(Ticket, draft.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    try:
        reject_ai_draft(db, ticket=ticket, draft=draft, actor=auth.user)
    except InvalidDraftStateError as exc:
        return _render_ops_detail(request, auth=auth, db=db, ticket=ticket, error=str(exc))
    db.commit()
    return RedirectResponse(url=f"/ops/tickets/{ticket.reference}", status_code=status.HTTP_303_SEE_OTHER)

```
# End of file: app/routes_ops.py

# File: app/templates/login.html
```html
{% extends "base.html" %}

{% block title %}Login{% endblock %}

{% block content %}
<section class="panel narrow">
  <h1>Sign in</h1>
  {% if error %}
  <p class="alert">{{ error }}</p>
  {% endif %}

  {% if current_user and current_user.role != "requester" %}
  <p>Signed in as <strong>{{ current_user.display_name }}</strong>.</p>
  <p>The Dev/TI surface is deferred to Phase 3, so only the requester flow is available in this phase.</p>
  {% elif not current_user %}
  <form method="post" action="/login" class="stack">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    <label>
      <span>Email</span>
      <input type="email" name="email" autocomplete="username" required>
    </label>
    <label>
      <span>Password</span>
      <input type="password" name="password" autocomplete="current-password" required>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="remember_me">
      <span>Remember me</span>
    </label>
    <button type="submit" class="button">Log in</button>
  </form>
  {% endif %}

  {% if ops_pending %}
  <p class="note">Login succeeded, but the Dev/TI UI is intentionally deferred to Phase 3.</p>
  {% endif %}
</section>
{% endblock %}

```
# End of file: app/templates/login.html

# File: app/templates/base.html
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Stage 1 Triage{% endblock %}</title>
    <link rel="stylesheet" href="{{ request.url_for('static', path='styles.css') }}">
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
  </head>
  <body>
    <header class="site-header">
      <div>
        <a class="brand" href="{% if current_user and current_user.role != 'requester' %}/ops{% else %}/app{% endif %}">Stage 1 Triage</a>
      </div>
      {% if current_user %}
      <div class="header-actions">
        <nav class="header-nav">
          {% if current_user.role == "requester" %}
          <a href="/app/tickets">My tickets</a>
          <a href="/app/tickets/new">New ticket</a>
          {% else %}
          <a href="/ops/board">Ops board</a>
          {% endif %}
        </nav>
        <span class="user-chip">{{ current_user.display_name }}</span>
        <form method="post" action="/logout">
          <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
          <button type="submit" class="button button-secondary">Log out</button>
        </form>
      </div>
      {% endif %}
    </header>
    <main class="page-shell">
      {% block content %}{% endblock %}
    </main>
  </body>
</html>

```
# End of file: app/templates/base.html

# File: app/templates/ops/board.html
```html
{% extends "base.html" %}

{% block title %}Ops Board{% endblock %}

{% block content %}
<section class="page-head">
  <div>
    <p class="note">Dev/TI queue</p>
    <h1>Ops board</h1>
  </div>
</section>

<section class="panel wide">
  <form method="get" action="/ops/board" class="filter-grid">
    <label>
      <span>Status</span>
      <select name="status">
        <option value="">All statuses</option>
        {% for column in columns %}
        <option value="{{ column.status }}" {% if filters.status == column.status %}selected{% endif %}>{{ column.label }}</option>
        {% endfor %}
      </select>
    </label>
    <label>
      <span>Class</span>
      <select name="ticket_class">
        <option value="">All classes</option>
        {% for item in ticket_class_options %}
        <option value="{{ item }}" {% if filters.ticket_class == item %}selected{% endif %}>{{ item }}</option>
        {% endfor %}
      </select>
    </label>
    <label>
      <span>Assigned to</span>
      <select name="assigned_to">
        <option value="">Anyone</option>
        {% for user in assignee_options %}
        <option value="{{ user.id }}" {% if filters.assigned_to == (user.id|string) %}selected{% endif %}>{{ user.display_name }}</option>
        {% endfor %}
      </select>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="urgent" value="1" {% if filters.urgent %}checked{% endif %}>
      <span>Urgent only</span>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="unassigned_only" value="1" {% if filters.unassigned_only %}checked{% endif %}>
      <span>Unassigned only</span>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="created_by_me" value="1" {% if filters.created_by_me %}checked{% endif %}>
      <span>Created by me</span>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="needs_approval" value="1" {% if filters.needs_approval %}checked{% endif %}>
      <span>Needs approval</span>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="updated_since_my_last_view" value="1" {% if filters.updated_since_my_last_view %}checked{% endif %}>
      <span>Updated since my last view</span>
    </label>
    <div class="form-actions">
      <button type="submit" class="button">Apply filters</button>
      <a href="/ops/board" class="button button-secondary">Clear</a>
    </div>
  </form>
</section>

<section class="ops-board">
  {% for column in columns %}
  <section class="panel board-column">
    <div class="board-column-head">
      <h2>{{ column.label }}</h2>
      <span class="badge">{{ column.tickets|length }}</span>
    </div>
    <div class="board-cards">
      {% if column.tickets %}
        {% for ticket in column.tickets %}
        <article class="board-card">
          <div class="ticket-meta">
            <span class="note">{{ ticket.reference }}</span>
            {% if ticket.updated %}<span class="badge badge-updated">Updated</span>{% endif %}
          </div>
          <h3><a href="/ops/tickets/{{ ticket.reference }}">{{ ticket.title }}</a></h3>
          <p class="note">Created by {{ ticket.creator_name }}</p>
          <div class="ticket-meta">
            <span class="badge">{{ ticket.ticket_class }}</span>
            {% if ticket.urgent %}<span class="badge badge-urgent">Urgent</span>{% endif %}
            {% if ticket.needs_approval %}<span class="badge">Needs approval</span>{% endif %}
          </div>
          <p class="note">
            {% if ticket.assignee_name %}Assigned to {{ ticket.assignee_name }}{% else %}Unassigned{% endif %}
          </p>
          <p class="note">Updated {{ ticket.updated_at.strftime("%Y-%m-%d %H:%M UTC") }}</p>
        </article>
        {% endfor %}
      {% else %}
      <p class="note">No tickets match this column.</p>
      {% endif %}
    </div>
  </section>
  {% endfor %}
</section>
{% endblock %}

```
# End of file: app/templates/ops/board.html

# File: app/templates/ops/detail.html
```html
{% extends "base.html" %}

{% block title %}{{ ticket.reference }}{% endblock %}

{% block content %}
<section class="page-head">
  <div>
    <p class="note">{{ ticket.reference }}</p>
    <h1>{{ ticket.title }}</h1>
    <div class="ticket-meta">
      <span class="badge">{{ ticket.status.replace("_", " ").title() }}</span>
      {% if ticket.urgent %}<span class="badge badge-urgent">Urgent</span>{% endif %}
      {% if pending_draft %}<span class="badge">Draft pending approval</span>{% endif %}
    </div>
  </div>
  <form method="post" action="/ops/tickets/{{ ticket.reference }}/rerun-ai">
    <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
    <button type="submit" class="button button-secondary">Rerun AI</button>
  </form>
</section>

{% if error %}
<p class="alert">{{ error }}</p>
{% endif %}

<section class="ops-layout">
  <div class="ops-main">
    <section class="panel wide">
      <h2>Ticket header</h2>
      <dl class="meta-grid">
        <div><dt>Requester</dt><dd>{{ creator.display_name if creator else "Unknown" }}</dd></div>
        <div><dt>Assignee</dt><dd>{{ assignee.display_name if assignee else "Unassigned" }}</dd></div>
        <div><dt>Class</dt><dd>{{ ticket.ticket_class or "unknown" }}</dd></div>
        <div><dt>Impact</dt><dd>{{ ticket.impact_level or "unknown" }}</dd></div>
        <div><dt>Confidence</dt><dd>{{ ticket.ai_confidence if ticket.ai_confidence is not none else "n/a" }}</dd></div>
        <div><dt>Development needed</dt><dd>{{ ticket.development_needed if ticket.development_needed is not none else "unknown" }}</dd></div>
        <div><dt>Last AI action</dt><dd>{{ ticket.last_ai_action or "n/a" }}</dd></div>
        <div><dt>Requester language</dt><dd>{{ ticket.requester_language or "n/a" }}</dd></div>
      </dl>
    </section>

    <section class="panel wide">
      <h2>Public thread</h2>
      <div class="thread">
        {% if public_thread %}
          {% for message in public_thread %}
          <article class="message-card">
            <div class="message-head">
              <strong>{{ message.author_label }}</strong>
              <span class="note">{{ message.source_label }}</span>
              <span class="timestamp">{{ message.created_at.strftime("%Y-%m-%d %H:%M UTC") }}</span>
            </div>
            <div class="message-body">{{ message.body_html }}</div>
            {% if message.attachments %}
            <ul class="attachment-list">
              {% for attachment in message.attachments %}
              <li><a href="/attachments/{{ attachment.id }}">{{ attachment.original_filename }}</a></li>
              {% endfor %}
            </ul>
            {% endif %}
          </article>
          {% endfor %}
        {% else %}
        <p class="note">No public messages yet.</p>
        {% endif %}
      </div>
    </section>

    <section class="panel wide">
      <h2>Internal thread</h2>
      <div class="thread">
        {% if internal_thread %}
          {% for message in internal_thread %}
          <article class="message-card">
            <div class="message-head">
              <strong>{{ message.author_label }}</strong>
              <span class="note">{{ message.source_label }}</span>
              <span class="timestamp">{{ message.created_at.strftime("%Y-%m-%d %H:%M UTC") }}</span>
            </div>
            <div class="message-body">{{ message.body_html }}</div>
          </article>
          {% endfor %}
        {% else %}
        <p class="note">No internal notes yet.</p>
        {% endif %}
      </div>
    </section>
  </div>

  <aside class="ops-sidebar">
    <section class="panel wide">
      <h2>Assignment</h2>
      <form method="post" action="/ops/tickets/{{ ticket.reference }}/assign" class="stack">
        <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
        <label>
          <span>Assigned to</span>
          <select name="assigned_to_user_id">
            <option value="">Unassigned</option>
            {% for user in ops_users %}
            <option value="{{ user.id }}" {% if assignee and assignee.id == user.id %}selected{% endif %}>{{ user.display_name }}</option>
            {% endfor %}
          </select>
        </label>
        <button type="submit" class="button">Save assignment</button>
      </form>
    </section>

    <section class="panel wide">
      <h2>Status</h2>
      <form method="post" action="/ops/tickets/{{ ticket.reference }}/set-status" class="stack">
        <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
        <label>
          <span>Current state</span>
          <select name="status">
            {% for value, label in status_options %}
            <option value="{{ value }}" {% if ticket.status == value %}selected{% endif %}>{{ label }}</option>
            {% endfor %}
          </select>
        </label>
        <button type="submit" class="button">Update status</button>
      </form>
    </section>

    <section class="panel wide">
      <h2>AI analysis</h2>
      {% if latest_ai_note_html %}
      <div class="message-body">{{ latest_ai_note_html }}</div>
      <p class="note">Generated {{ latest_ai_note_at.strftime("%Y-%m-%d %H:%M UTC") }}</p>
      {% else %}
      <p class="note">No internal AI summary has been recorded yet.</p>
      {% endif %}
      {% if latest_run %}
      <p class="note">Latest run: {{ latest_run.status }}{% if latest_run.model_name %} via {{ latest_run.model_name }}{% endif %}</p>
      {% endif %}
    </section>

    <section class="panel wide">
      <h2>Relevant repo/docs paths</h2>
      {% if relevant_paths %}
      <ul class="path-list">
        {% for item in relevant_paths %}
        <li><code>{{ item.path }}</code> <span class="note">{{ item.reason }}</span></li>
        {% endfor %}
      </ul>
      {% else %}
      <p class="note">No relevant paths have been captured yet.</p>
      {% endif %}
    </section>

    <section class="panel wide">
      <h2>Public draft</h2>
      {% if pending_draft %}
      <div class="message-body">{{ pending_draft_html }}</div>
      <div class="split-actions">
        <form method="post" action="/ops/drafts/{{ pending_draft.id }}/approve-publish" class="stack">
          <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
          <label>
            <span>Next status</span>
            <select name="next_status">
              {% for value, label in reply_status_options %}
              <option value="{{ value }}" {% if selected_next_status == value %}selected{% endif %}>{{ label }}</option>
              {% endfor %}
            </select>
          </label>
          <button type="submit" class="button">Approve and publish</button>
        </form>
        <form method="post" action="/ops/drafts/{{ pending_draft.id }}/reject">
          <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
          <button type="submit" class="button button-secondary">Reject</button>
        </form>
      </div>
      {% elif latest_draft %}
      <p class="note">Latest draft status: {{ latest_draft.status }}</p>
      {% else %}
      <p class="note">No AI draft is waiting for review.</p>
      {% endif %}
    </section>

    <section class="panel wide">
      <h2>Public reply</h2>
      <form method="post" action="/ops/tickets/{{ ticket.reference }}/reply-public" class="stack">
        <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
        <label>
          <span>Message</span>
          <textarea name="body" rows="6">{{ public_reply_body }}</textarea>
        </label>
        <label>
          <span>Next status</span>
          <select name="next_status">
            {% for value, label in reply_status_options %}
            <option value="{{ value }}" {% if selected_next_status == value %}selected{% endif %}>{{ label }}</option>
            {% endfor %}
          </select>
        </label>
        <button type="submit" class="button">Send public reply</button>
      </form>
    </section>

    <section class="panel wide">
      <h2>Internal note</h2>
      <form method="post" action="/ops/tickets/{{ ticket.reference }}/note-internal" class="stack">
        <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
        <label>
          <span>Note</span>
          <textarea name="body" rows="5">{{ internal_note_body }}</textarea>
        </label>
        <button type="submit" class="button button-secondary">Save internal note</button>
      </form>
    </section>
  </aside>
</section>
{% endblock %}

```
# End of file: app/templates/ops/detail.html

# File: app/templates/tickets/detail.html
```html
{% extends "base.html" %}

{% block title %}{{ ticket.reference }}{% endblock %}

{% block content %}
<section class="page-head">
  <div>
    <p class="note">{{ ticket.reference }}</p>
    <h1>{{ ticket.title }}</h1>
    <div class="ticket-meta">
      <span class="badge">{{ requester_status }}</span>
      {% if ticket.urgent %}<span class="badge badge-urgent">Urgent</span>{% endif %}
    </div>
  </div>
  {% if ticket.status != "resolved" %}
  <form method="post" action="/app/tickets/{{ ticket.reference }}/resolve">
    <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
    <button type="submit" class="button button-secondary">Mark resolved</button>
  </form>
  {% endif %}
</section>

{% if error %}
<p class="alert">{{ error }}</p>
{% endif %}

<section class="thread">
  {% for message in thread %}
  <article class="panel message-card">
    <div class="message-head">
      <strong>{{ message.author_label }}</strong>
      <span class="timestamp">{{ message.created_at.strftime("%Y-%m-%d %H:%M UTC") }}</span>
    </div>
    <div class="message-body">{{ message.body_html }}</div>
    {% if message.attachments %}
    <ul class="attachment-list">
      {% for attachment in message.attachments %}
      <li>
        <a href="/attachments/{{ attachment.id }}">{{ attachment.original_filename }}</a>
        <span class="note">({{ attachment.mime_type }}, {{ attachment.size_bytes }} bytes)</span>
      </li>
      {% endfor %}
    </ul>
    {% endif %}
  </article>
  {% endfor %}
</section>

<section class="panel wide">
  <h2>Reply</h2>
  <form method="post" action="/app/tickets/{{ ticket.reference }}/reply" enctype="multipart/form-data" class="stack">
    <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
    <label>
      <span>Message</span>
      <textarea name="body" rows="6">{{ reply_body }}</textarea>
    </label>
    <label>
      <span>Images</span>
      <input type="file" name="attachments" accept="image/png,image/jpeg" multiple>
    </label>
    <button type="submit" class="button">Send reply</button>
  </form>
</section>
{% endblock %}

```
# End of file: app/templates/tickets/detail.html

# File: app/templates/tickets/list.html
```html
{% extends "base.html" %}

{% block title %}My Tickets{% endblock %}

{% block content %}
<section class="page-head">
  <div>
    <h1>My tickets</h1>
    <p class="note">Public thread view only. Internal analysis stays on the Dev/TI side.</p>
  </div>
  <a class="button" href="/app/tickets/new">New ticket</a>
</section>

<section class="panel">
  {% if tickets %}
  <ul class="ticket-list">
    {% for ticket in tickets %}
    <li class="ticket-row">
      <div>
        <a class="ticket-link" href="/app/tickets/{{ ticket.reference }}">{{ ticket.reference }}</a>
        <div class="ticket-title">{{ ticket.title }}</div>
      </div>
      <div class="ticket-meta">
        <span class="badge">{{ ticket.status }}</span>
        {% if ticket.urgent %}<span class="badge badge-urgent">Urgent</span>{% endif %}
        {% if ticket.updated %}<span class="badge badge-updated">Updated</span>{% endif %}
        <span class="timestamp">{{ ticket.updated_at.strftime("%Y-%m-%d %H:%M UTC") }}</span>
      </div>
    </li>
    {% endfor %}
  </ul>
  {% else %}
  <p>No tickets yet.</p>
  {% endif %}
</section>
{% endblock %}

```
# End of file: app/templates/tickets/list.html

# File: app/templates/tickets/new.html
```html
{% extends "base.html" %}

{% block title %}New Ticket{% endblock %}

{% block content %}
<section class="panel wide">
  <h1>Open a ticket</h1>
  {% if error %}
  <p class="alert">{{ error }}</p>
  {% endif %}
  <form method="post" action="/app/tickets" enctype="multipart/form-data" class="stack">
    <input type="hidden" name="csrf_token" value="{{ session_csrf_token }}">
    <label>
      <span>Short title</span>
      <input type="text" name="title" maxlength="120" value="{{ title_value }}">
    </label>
    <label>
      <span>Description</span>
      <textarea name="description" rows="10" required>{{ description_value }}</textarea>
    </label>
    <label>
      <span>Images</span>
      <input type="file" name="attachments" accept="image/png,image/jpeg" multiple>
    </label>
    <label class="checkbox">
      <input type="checkbox" name="urgent" {% if urgent %}checked{% endif %}>
      <span>Mark as urgent</span>
    </label>
    <div class="form-actions">
      <a class="button button-secondary" href="/app/tickets">Cancel</a>
      <button type="submit" class="button">Create ticket</button>
    </div>
  </form>
</section>
{% endblock %}

```
# End of file: app/templates/tickets/new.html

# File: app/static/styles.css
```css
body {
  margin: 0;
  font-family: "Segoe UI", Helvetica, Arial, sans-serif;
  background: linear-gradient(180deg, #f4efe6 0%, #fbfaf7 100%);
  color: #1f1f1f;
}

a {
  color: #9a3412;
}

.site-header,
.page-shell,
.page-head,
.ticket-row,
.ticket-meta,
.header-actions,
.header-nav,
.message-head,
.form-actions,
.split-actions,
.board-column-head {
  display: flex;
  gap: 1rem;
}

.site-header,
.page-head,
.ticket-row,
.message-head {
  align-items: center;
  justify-content: space-between;
}

.site-header {
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #d9cdb7;
  background: rgba(255, 251, 245, 0.95);
  position: sticky;
  top: 0;
}

.brand {
  font-weight: 700;
  text-decoration: none;
}

.page-shell {
  flex-direction: column;
  max-width: 960px;
  margin: 0 auto;
  padding: 1.5rem;
}

.header-nav {
  align-items: center;
}

.header-nav a {
  text-decoration: none;
}

.panel {
  background: white;
  border: 1px solid #e6dcc8;
  border-radius: 16px;
  padding: 1.25rem;
  box-shadow: 0 10px 30px rgba(71, 45, 7, 0.06);
}

.panel.narrow {
  max-width: 420px;
}

.panel.wide {
  width: 100%;
}

.stack {
  display: grid;
  gap: 1rem;
}

label span {
  display: block;
  font-weight: 600;
  margin-bottom: 0.35rem;
}

input[type="email"],
input[type="password"],
input[type="text"],
textarea,
select {
  width: 100%;
  box-sizing: border-box;
  padding: 0.8rem;
  border-radius: 10px;
  border: 1px solid #cfbf9f;
  background: #fffdf8;
}

.checkbox {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.button {
  border: none;
  border-radius: 999px;
  padding: 0.75rem 1rem;
  background: #9a3412;
  color: white;
  font-weight: 700;
  cursor: pointer;
  text-decoration: none;
}

.button-secondary {
  background: #57534e;
}

.badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: #f3e8d3;
  padding: 0.3rem 0.7rem;
  font-size: 0.9rem;
}

.badge-urgent {
  background: #fee2e2;
  color: #991b1b;
}

.badge-updated {
  background: #dcfce7;
  color: #166534;
}

.alert {
  padding: 0.85rem 1rem;
  border-radius: 12px;
  background: #fee2e2;
  color: #991b1b;
}

.note,
.timestamp {
  color: #6b7280;
}

.ticket-list,
.attachment-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.ticket-row {
  padding: 1rem 0;
  border-bottom: 1px solid #eee2cf;
}

.ticket-row:last-child {
  border-bottom: 0;
}

.ticket-link {
  font-weight: 700;
}

.ticket-title {
  margin-top: 0.3rem;
}

.thread {
  display: grid;
  gap: 1rem;
}

.filter-grid,
.meta-grid {
  display: grid;
  gap: 1rem;
}

.filter-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.meta-grid {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.meta-grid dt {
  color: #6b7280;
  font-size: 0.9rem;
}

.meta-grid dd {
  margin: 0.3rem 0 0;
  font-weight: 600;
}

.ops-board {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.board-column,
.board-cards,
.ops-main,
.ops-sidebar,
.ops-layout {
  display: grid;
  gap: 1rem;
}

.board-card {
  border: 1px solid #eee2cf;
  border-radius: 14px;
  padding: 1rem;
  background: #fffdfa;
}

.ops-layout {
  grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr);
  align-items: start;
}

.path-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 0.6rem;
}

.message-card {
  display: grid;
  gap: 0.75rem;
}

.message-body p:first-child {
  margin-top: 0;
}

@media (max-width: 720px) {
  .site-header,
  .page-head,
  .ticket-row,
  .header-actions,
  .header-nav,
  .form-actions,
  .split-actions,
  .message-head {
    flex-direction: column;
    align-items: stretch;
  }

  .ops-layout {
    grid-template-columns: 1fr;
  }
}

```
# End of file: app/static/styles.css

# File: shared/config.py
```python
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Mapping


class ConfigError(ValueError):
    """Raised when required environment configuration is missing or invalid."""


DEFAULT_UPLOADS_DIR = Path("/opt/triage/data/uploads")
DEFAULT_TRIAGE_WORKSPACE_DIR = Path("/opt/triage/triage_workspace")
DEFAULT_REPO_DIRNAME = "app"
DEFAULT_MANUALS_DIRNAME = "manuals"

REQUIRED_ENV_VARS = (
    "APP_BASE_URL",
    "APP_SECRET_KEY",
    "DATABASE_URL",
    "CODEX_API_KEY",
)


def _coerce_int(name: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _coerce_float(name: str, value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc


@dataclass(frozen=True)
class Settings:
    app_base_url: str
    app_secret_key: str
    database_url: str
    codex_api_key: str
    uploads_dir: Path = DEFAULT_UPLOADS_DIR
    triage_workspace_dir: Path = DEFAULT_TRIAGE_WORKSPACE_DIR
    repo_mount_dir: Path = DEFAULT_TRIAGE_WORKSPACE_DIR / DEFAULT_REPO_DIRNAME
    manuals_mount_dir: Path = DEFAULT_TRIAGE_WORKSPACE_DIR / DEFAULT_MANUALS_DIRNAME
    codex_bin: str = "codex"
    codex_model: str | None = None
    codex_timeout_seconds: int = 75
    worker_poll_seconds: int = 10
    auto_support_reply_min_confidence: float = 0.85
    auto_confirm_intent_min_confidence: float = 0.90
    max_images_per_message: int = 3
    max_image_bytes: int = 5 * 1024 * 1024
    session_default_hours: int = 12
    session_remember_days: int = 30

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        values = dict(os.environ if env is None else env)
        missing = [key for key in REQUIRED_ENV_VARS if not values.get(key)]
        if missing:
            joined = ", ".join(sorted(missing))
            raise ConfigError(f"Missing required environment variables: {joined}")

        codex_model = values.get("CODEX_MODEL") or None
        triage_workspace_dir = Path(
            values.get("TRIAGE_WORKSPACE_DIR", str(DEFAULT_TRIAGE_WORKSPACE_DIR))
        )
        repo_mount_dir = Path(
            values.get("REPO_MOUNT_DIR", str(triage_workspace_dir / DEFAULT_REPO_DIRNAME))
        )
        manuals_mount_dir = Path(
            values.get("MANUALS_MOUNT_DIR", str(triage_workspace_dir / DEFAULT_MANUALS_DIRNAME))
        )

        settings = cls(
            app_base_url=values["APP_BASE_URL"],
            app_secret_key=values["APP_SECRET_KEY"],
            database_url=values["DATABASE_URL"],
            codex_api_key=values["CODEX_API_KEY"],
            uploads_dir=Path(values.get("UPLOADS_DIR", str(DEFAULT_UPLOADS_DIR))),
            triage_workspace_dir=triage_workspace_dir,
            repo_mount_dir=repo_mount_dir,
            manuals_mount_dir=manuals_mount_dir,
            codex_bin=values.get("CODEX_BIN", "codex"),
            codex_model=codex_model,
            codex_timeout_seconds=_coerce_int(
                "CODEX_TIMEOUT_SECONDS", values.get("CODEX_TIMEOUT_SECONDS", "75")
            ),
            worker_poll_seconds=_coerce_int(
                "WORKER_POLL_SECONDS", values.get("WORKER_POLL_SECONDS", "10")
            ),
            auto_support_reply_min_confidence=_coerce_float(
                "AUTO_SUPPORT_REPLY_MIN_CONFIDENCE",
                values.get("AUTO_SUPPORT_REPLY_MIN_CONFIDENCE", "0.85"),
            ),
            auto_confirm_intent_min_confidence=_coerce_float(
                "AUTO_CONFIRM_INTENT_MIN_CONFIDENCE",
                values.get("AUTO_CONFIRM_INTENT_MIN_CONFIDENCE", "0.90"),
            ),
            max_images_per_message=_coerce_int(
                "MAX_IMAGES_PER_MESSAGE", values.get("MAX_IMAGES_PER_MESSAGE", "3")
            ),
            max_image_bytes=_coerce_int(
                "MAX_IMAGE_BYTES", values.get("MAX_IMAGE_BYTES", str(5 * 1024 * 1024))
            ),
            session_default_hours=_coerce_int(
                "SESSION_DEFAULT_HOURS", values.get("SESSION_DEFAULT_HOURS", "12")
            ),
            session_remember_days=_coerce_int(
                "SESSION_REMEMBER_DAYS", values.get("SESSION_REMEMBER_DAYS", "30")
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.max_images_per_message <= 0:
            raise ConfigError("MAX_IMAGES_PER_MESSAGE must be greater than zero")
        if self.max_image_bytes <= 0:
            raise ConfigError("MAX_IMAGE_BYTES must be greater than zero")
        if self.session_default_hours <= 0:
            raise ConfigError("SESSION_DEFAULT_HOURS must be greater than zero")
        if self.session_remember_days <= 0:
            raise ConfigError("SESSION_REMEMBER_DAYS must be greater than zero")
        if self.worker_poll_seconds <= 0:
            raise ConfigError("WORKER_POLL_SECONDS must be greater than zero")
        if self.codex_timeout_seconds <= 0:
            raise ConfigError("CODEX_TIMEOUT_SECONDS must be greater than zero")
        if not self.app_base_url.strip():
            raise ConfigError("APP_BASE_URL must not be blank")
        if not self.app_secret_key.strip():
            raise ConfigError("APP_SECRET_KEY must not be blank")
        if not self.database_url.strip():
            raise ConfigError("DATABASE_URL must not be blank")
        if not self.codex_api_key.strip():
            raise ConfigError("CODEX_API_KEY must not be blank")
        for name, value in (
            ("AUTO_SUPPORT_REPLY_MIN_CONFIDENCE", self.auto_support_reply_min_confidence),
            (
                "AUTO_CONFIRM_INTENT_MIN_CONFIDENCE",
                self.auto_confirm_intent_min_confidence,
            ),
        ):
            if not 0.0 <= value <= 1.0:
                raise ConfigError(f"{name} must be between 0.0 and 1.0")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()

```
# End of file: shared/config.py

# File: shared/models.py
```python
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
import uuid

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, PrimaryKeyConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UserRole(StrEnum):
    REQUESTER = "requester"
    DEV_TI = "dev_ti"
    ADMIN = "admin"


class TicketStatus(StrEnum):
    NEW = "new"
    AI_TRIAGE = "ai_triage"
    WAITING_ON_USER = "waiting_on_user"
    WAITING_ON_DEV_TI = "waiting_on_dev_ti"
    RESOLVED = "resolved"


class TicketClass(StrEnum):
    SUPPORT = "support"
    ACCESS_CONFIG = "access_config"
    DATA_OPS = "data_ops"
    BUG = "bug"
    FEATURE = "feature"
    UNKNOWN = "unknown"


class ImpactLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class MessageAuthorType(StrEnum):
    REQUESTER = "requester"
    DEV_TI = "dev_ti"
    AI = "ai"
    SYSTEM = "system"


class MessageVisibility(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"


class MessageSource(StrEnum):
    TICKET_CREATE = "ticket_create"
    REQUESTER_REPLY = "requester_reply"
    HUMAN_PUBLIC_REPLY = "human_public_reply"
    HUMAN_INTERNAL_NOTE = "human_internal_note"
    AI_AUTO_PUBLIC = "ai_auto_public"
    AI_INTERNAL_NOTE = "ai_internal_note"
    AI_DRAFT_PUBLISHED = "ai_draft_published"
    SYSTEM = "system"


class AttachmentVisibility(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"


class StatusChangedByType(StrEnum):
    REQUESTER = "requester"
    DEV_TI = "dev_ti"
    AI = "ai"
    SYSTEM = "system"


class AiRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    SUPERSEDED = "superseded"


class AiRunTrigger(StrEnum):
    NEW_TICKET = "new_ticket"
    REQUESTER_REPLY = "requester_reply"
    MANUAL_RERUN = "manual_rerun"
    REOPEN = "reopen"


class TicketRequeueTrigger(StrEnum):
    REQUESTER_REPLY = "requester_reply"
    MANUAL_RERUN = "manual_rerun"
    REOPEN = "reopen"


class AiDraftKind(StrEnum):
    PUBLIC_REPLY = "public_reply"


class AiDraftStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    PUBLISHED = "published"


def enum_values(enum_cls: type[StrEnum]) -> tuple[str, ...]:
    return tuple(item.value for item in enum_cls)


def enum_type(enum_cls: type[StrEnum], *, name: str) -> sa.Enum:
    return sa.Enum(
        *enum_values(enum_cls),
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(sa.Text(), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    password_hash: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    role: Mapped[str] = mapped_column(enum_type(UserRole, name="user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(sa.Text(), nullable=False, unique=True)
    csrf_token: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    remember_me: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    user_agent: Mapped[str | None] = mapped_column(sa.Text())
    ip_address: Mapped[str | None] = mapped_column(sa.Text())


class Ticket(TimestampMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("ix_tickets_status_updated_at", "status", sa.text("updated_at DESC")),
        Index(
            "ix_tickets_created_by_updated_at",
            "created_by_user_id",
            sa.text("updated_at DESC"),
        ),
        Index(
            "ix_tickets_assigned_to_updated_at",
            "assigned_to_user_id",
            sa.text("updated_at DESC"),
        ),
        Index(
            "ix_tickets_urgent_status_updated_at",
            "urgent",
            "status",
            sa.text("updated_at DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    reference_num: Mapped[int] = mapped_column(
        sa.BigInteger(),
        Identity(start=1),
        nullable=False,
        unique=True,
    )
    reference: Mapped[str] = mapped_column(sa.Text(), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="RESTRICT"),
    )
    status: Mapped[str] = mapped_column(enum_type(TicketStatus, name="ticket_status"), nullable=False)
    urgent: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )
    ticket_class: Mapped[str | None] = mapped_column(enum_type(TicketClass, name="ticket_class"))
    ai_confidence: Mapped[Decimal | None] = mapped_column(sa.Numeric(4, 3))
    impact_level: Mapped[str | None] = mapped_column(enum_type(ImpactLevel, name="impact_level"))
    development_needed: Mapped[bool | None] = mapped_column(sa.Boolean())
    clarification_rounds: Mapped[int] = mapped_column(
        sa.Integer(),
        nullable=False,
        default=0,
        server_default=sa.text("0"),
    )
    requester_language: Mapped[str | None] = mapped_column(sa.Text())
    last_processed_hash: Mapped[str | None] = mapped_column(sa.Text())
    last_ai_action: Mapped[str | None] = mapped_column(sa.Text())
    requeue_requested: Mapped[bool] = mapped_column(
        sa.Boolean(),
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )
    requeue_trigger: Mapped[str | None] = mapped_column(
        enum_type(TicketRequeueTrigger, name="ticket_requeue_trigger")
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class AiRun(TimestampMixin, Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
        Index("ix_ai_runs_status_created_at", "status", "created_at"),
        Index("ix_ai_runs_ticket_created_at_desc", "ticket_id", sa.text("created_at DESC")),
        Index(
            "uq_ai_runs_ticket_active",
            "ticket_id",
            unique=True,
            postgresql_where=sa.text("status IN ('pending', 'running')"),
            sqlite_where=sa.text("status IN ('pending', 'running')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(enum_type(AiRunStatus, name="ai_run_status"), nullable=False)
    triggered_by: Mapped[str] = mapped_column(
        enum_type(AiRunTrigger, name="ai_run_trigger"),
        nullable=False,
    )
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    input_hash: Mapped[str | None] = mapped_column(sa.Text())
    model_name: Mapped[str | None] = mapped_column(sa.Text())
    prompt_path: Mapped[str | None] = mapped_column(sa.Text())
    schema_path: Mapped[str | None] = mapped_column(sa.Text())
    final_output_path: Mapped[str | None] = mapped_column(sa.Text())
    stdout_jsonl_path: Mapped[str | None] = mapped_column(sa.Text())
    stderr_path: Mapped[str | None] = mapped_column(sa.Text())
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    error_text: Mapped[str | None] = mapped_column(sa.Text())


class TicketMessage(TimestampMixin, Base):
    __tablename__ = "ticket_messages"
    __table_args__ = (
        Index("ix_ticket_messages_ticket_created_at", "ticket_id", "created_at"),
        Index(
            "ix_ticket_messages_ticket_visibility_created_at",
            "ticket_id",
            "visibility",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    author_type: Mapped[str] = mapped_column(
        enum_type(MessageAuthorType, name="message_author_type"),
        nullable=False,
    )
    visibility: Mapped[str] = mapped_column(
        enum_type(MessageVisibility, name="message_visibility"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(enum_type(MessageSource, name="message_source"), nullable=False)
    body_markdown: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    body_text: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("ai_runs.id", ondelete="SET NULL"),
    )


class TicketAttachment(TimestampMixin, Base):
    __tablename__ = "ticket_attachments"
    __table_args__ = (
        Index("ix_ticket_attachments_ticket_id", "ticket_id"),
        Index("ix_ticket_attachments_message_id", "message_id"),
        Index("ix_ticket_attachments_sha256", "sha256"),
        CheckConstraint(
            "visibility = 'public' OR visibility = 'internal'",
            name="ck_ticket_attachments_visibility_allowed",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("ticket_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    visibility: Mapped[str] = mapped_column(
        enum_type(AttachmentVisibility, name="attachment_visibility"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    stored_path: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    mime_type: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    sha256: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    size_bytes: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    width: Mapped[int | None] = mapped_column(sa.Integer())
    height: Mapped[int | None] = mapped_column(sa.Integer())


class TicketStatusHistory(TimestampMixin, Base):
    __tablename__ = "ticket_status_history"
    __table_args__ = (Index("ix_ticket_status_history_ticket_created_at", "ticket_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(enum_type(TicketStatus, name="history_from_status"))
    to_status: Mapped[str] = mapped_column(enum_type(TicketStatus, name="history_to_status"), nullable=False)
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    changed_by_type: Mapped[str] = mapped_column(
        enum_type(StatusChangedByType, name="status_changed_by_type"),
        nullable=False,
    )
    note: Mapped[str | None] = mapped_column(sa.Text())


class TicketView(Base):
    __tablename__ = "ticket_views"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "ticket_id", name="pk_ticket_views"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    last_viewed_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )


class AiDraft(TimestampMixin, Base):
    __tablename__ = "ai_drafts"
    __table_args__ = (
        Index("ix_ai_drafts_ticket_status_created_at_desc", "ticket_id", "status", sa.text("created_at DESC")),
        Index("ix_ai_drafts_ai_run_id", "ai_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid(), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    ai_run_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid(),
        ForeignKey("ai_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(enum_type(AiDraftKind, name="ai_draft_kind"), nullable=False)
    body_markdown: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    body_text: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    status: Mapped[str] = mapped_column(enum_type(AiDraftStatus, name="ai_draft_status"), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    published_message_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.Uuid(),
        ForeignKey("ticket_messages.id", ondelete="SET NULL"),
    )


class SystemState(Base):
    __tablename__ = "system_state"

    key: Mapped[str] = mapped_column(sa.Text(), primary_key=True)
    value_json: Mapped[dict] = mapped_column(sa.JSON(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=sa.text("CURRENT_TIMESTAMP"),
    )

```
# End of file: shared/models.py

# File: shared/logging.py
```python
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import sys
from typing import Any


class JsonFormatter(logging.Formatter):
    def __init__(self, *, default_service: str) -> None:
        super().__init__()
        self.default_service = default_service

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service": self.default_service,
            "level": record.levelname.lower(),
            "logger": record.name,
        }
        structured = getattr(record, "structured_payload", None)
        if isinstance(structured, dict):
            payload.update(structured)
        else:
            payload["message"] = record.getMessage()
        payload.setdefault("service", self.default_service)
        return json.dumps(payload, default=str)


def configure_logging(*, service: str, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(default_service=service))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def log_event(
    logger: logging.Logger,
    *,
    service: str,
    event: str,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    payload = {"service": service, "event": event, **fields}
    logger.log(level, event, extra={"structured_payload": payload})

```
# End of file: shared/logging.py

# File: shared/user_admin.py
```python
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.models import User, UserRole
from shared.security import hash_password, normalize_email


class UserAdminError(RuntimeError):
    """Raised when a user administration command cannot be completed."""


def _require_role(role: str) -> str:
    allowed = {item.value for item in UserRole}
    if role not in allowed:
        joined = ", ".join(sorted(allowed))
        raise UserAdminError(f"Invalid role '{role}'. Allowed roles: {joined}")
    return role


def create_user_account(
    session: Session,
    *,
    email: str,
    display_name: str,
    password: str,
    role: str,
) -> User:
    normalized_email = normalize_email(email)
    role = _require_role(role)
    existing = session.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        raise UserAdminError(f"User already exists: {normalized_email}")

    user = User(
        email=normalized_email,
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def get_user_by_email(session: Session, *, email: str) -> User:
    normalized_email = normalize_email(email)
    user = session.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        raise UserAdminError(f"User not found: {normalized_email}")
    return user


def set_user_password(session: Session, *, email: str, password: str) -> User:
    user = get_user_by_email(session, email=email)
    user.password_hash = hash_password(password)
    session.flush()
    return user


def deactivate_user_account(session: Session, *, email: str) -> User:
    user = get_user_by_email(session, email=email)
    user.is_active = False
    session.flush()
    return user

```
# End of file: shared/user_admin.py

# File: shared/security.py
```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from urllib.parse import urlparse

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from shared.config import Settings


SESSION_COOKIE_NAME = "triage_session"
LOGIN_CSRF_COOKIE_NAME = "triage_login_csrf"
_PASSWORD_HASHER = PasswordHasher()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(24)


def session_expires_at(
    settings: Settings,
    *,
    remember_me: bool,
    now: datetime | None = None,
) -> datetime:
    now = now or utcnow()
    if remember_me:
        return now + timedelta(days=settings.session_remember_days)
    return now + timedelta(hours=settings.session_default_hours)


def session_max_age(settings: Settings, *, remember_me: bool) -> int | None:
    if not remember_me:
        return None
    return settings.session_remember_days * 24 * 60 * 60


def should_use_secure_cookies(settings: Settings) -> bool:
    return urlparse(settings.app_base_url).scheme == "https"


def constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def sign_login_csrf(secret_key: str, raw_token: str) -> str:
    digest = hmac.new(
        secret_key.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    )
    return digest.hexdigest()


def generate_login_csrf_token(secret_key: str) -> str:
    raw_token = generate_csrf_token()
    signature = sign_login_csrf(secret_key, raw_token)
    return f"{raw_token}.{signature}"


def validate_login_csrf_token(secret_key: str, token: str) -> bool:
    raw_token, separator, signature = token.partition(".")
    if not separator or not raw_token or not signature:
        return False
    expected = sign_login_csrf(secret_key, raw_token)
    return constant_time_equals(signature, expected)

```
# End of file: shared/security.py

# File: shared/permissions.py
```python
from __future__ import annotations

from shared.models import (
    AttachmentVisibility,
    Ticket,
    TicketAttachment,
    User,
    UserRole,
)


class PermissionDeniedError(ValueError):
    """Raised when a user attempts an unauthorized action."""


def has_role(user: User, *roles: UserRole | str) -> bool:
    allowed = {role.value if isinstance(role, UserRole) else role for role in roles}
    return user.role in allowed


def ensure_role(user: User, *roles: UserRole | str) -> None:
    if not has_role(user, *roles):
        joined = ", ".join(sorted(role.value if isinstance(role, UserRole) else role for role in roles))
        raise PermissionDeniedError(f"User role {user.role!r} does not satisfy required roles: {joined}")


def ensure_requester(user: User) -> None:
    ensure_role(user, UserRole.REQUESTER)


def ensure_dev_ti(user: User) -> None:
    ensure_role(user, UserRole.DEV_TI, UserRole.ADMIN)


def ensure_requester_ticket_access(user: User, ticket: Ticket) -> None:
    ensure_requester(user)
    if ticket.created_by_user_id != user.id:
        raise PermissionDeniedError("Requester does not own this ticket")


def ensure_requester_attachment_access(
    user: User,
    ticket: Ticket,
    attachment: TicketAttachment,
) -> None:
    ensure_requester_ticket_access(user, ticket)
    if attachment.visibility != AttachmentVisibility.PUBLIC.value:
        raise PermissionDeniedError("Requester cannot access non-public attachments")

```
# End of file: shared/permissions.py

# File: shared/bootstrap.py
```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from shared.config import Settings
from shared.db import session_scope
from shared.models import SystemState
from shared.workspace_contract import EXACT_AGENTS_MD, EXACT_SKILL_MD


DEFAULT_BOOTSTRAP_VERSION = "1.2-custom-final"


class WorkspaceBootstrapError(RuntimeError):
    """Raised when the workspace bootstrap contract cannot be satisfied."""


@dataclass(frozen=True)
class WorkspaceBootstrapResult:
    uploads_dir: str
    workspace_dir: str
    repo_mount_dir: str
    manuals_mount_dir: str
    git_initialized: bool
    initial_commit_created: bool
    agents_written: bool
    skill_written: bool
    bootstrap_version_written: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def workspace_agents_path(settings: Settings) -> Path:
    return settings.triage_workspace_dir / "AGENTS.md"


def workspace_skill_path(settings: Settings) -> Path:
    return settings.triage_workspace_dir / ".agents" / "skills" / "stage1-triage" / "SKILL.md"


def workspace_runs_dir(settings: Settings) -> Path:
    return settings.triage_workspace_dir / "runs"


def _write_if_changed(path: Path, content: str) -> bool:
    existing = None
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    if existing == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def ensure_workspace_files(settings: Settings) -> tuple[bool, bool]:
    settings.triage_workspace_dir.mkdir(parents=True, exist_ok=True)
    workspace_runs_dir(settings).mkdir(parents=True, exist_ok=True)
    agents_written = _write_if_changed(workspace_agents_path(settings), EXACT_AGENTS_MD)
    skill_written = _write_if_changed(workspace_skill_path(settings), EXACT_SKILL_MD)
    return agents_written, skill_written


def _run_git(settings: Settings, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(settings.triage_workspace_dir), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def ensure_workspace_git_repository(settings: Settings) -> tuple[bool, bool]:
    git_dir = settings.triage_workspace_dir / ".git"
    git_initialized = False
    initial_commit_created = False

    if not git_dir.exists():
        settings.triage_workspace_dir.mkdir(parents=True, exist_ok=True)
        completed = _run_git(settings, "init")
        if completed.returncode != 0:
            raise WorkspaceBootstrapError(completed.stderr.strip() or "git init failed")
        git_initialized = True

    head_check = _run_git(settings, "rev-parse", "--verify", "HEAD")
    if head_check.returncode != 0:
        commit = _run_git(
            settings,
            "-c",
            "user.name=Stage 1 Bootstrap",
            "-c",
            "user.email=stage1-triage@local",
            "commit",
            "--allow-empty",
            "-m",
            "Initialize workspace",
        )
        if commit.returncode != 0:
            raise WorkspaceBootstrapError(commit.stderr.strip() or "git commit --allow-empty failed")
        initial_commit_created = True

    return git_initialized, initial_commit_created


def verify_required_path(path: Path, *, label: str, must_be_directory: bool = True) -> None:
    if not path.exists():
        raise WorkspaceBootstrapError(f"{label} is missing: {path}")
    if must_be_directory and not path.is_dir():
        raise WorkspaceBootstrapError(f"{label} is not a directory: {path}")
    if not os.access(path, os.R_OK):
        raise WorkspaceBootstrapError(f"{label} is not readable: {path}")


def workspace_readiness_issues(settings: Settings) -> list[str]:
    issues: list[str] = []

    def check(path: Path, *, label: str, must_be_directory: bool = True, exact_text: str | None = None) -> None:
        if not path.exists():
            issues.append(f"{label} missing: {path}")
            return
        if must_be_directory and not path.is_dir():
            issues.append(f"{label} not a directory: {path}")
            return
        if not os.access(path, os.R_OK):
            issues.append(f"{label} not readable: {path}")
            return
        if exact_text is not None and path.read_text(encoding="utf-8") != exact_text:
            issues.append(f"{label} content mismatch: {path}")

    check(settings.uploads_dir, label="uploads_dir")
    check(settings.triage_workspace_dir, label="triage_workspace_dir")
    check(settings.repo_mount_dir, label="repo_mount_dir")
    check(settings.manuals_mount_dir, label="manuals_mount_dir")
    check(workspace_runs_dir(settings), label="workspace_runs_dir")
    check(workspace_agents_path(settings), label="agents_md", must_be_directory=False, exact_text=EXACT_AGENTS_MD)
    check(workspace_skill_path(settings), label="skill_md", must_be_directory=False, exact_text=EXACT_SKILL_MD)
    return issues


def check_database_readiness(session_factory: sessionmaker[Session]) -> str | None:
    try:
        with session_scope(session_factory) as session:
            session.execute(sa.text("SELECT 1"))
        return None
    except Exception as exc:  # pragma: no cover - error path exercised in app tests via monkeypatch
        return str(exc)


def write_bootstrap_version(
    session_factory: sessionmaker[Session],
    *,
    version: str = DEFAULT_BOOTSTRAP_VERSION,
    updated_at: datetime | None = None,
) -> bool:
    updated_at = updated_at or now_utc()
    with session_scope(session_factory) as session:
        row = session.get(SystemState, "bootstrap_version")
        payload = {"version": version, "updated_at": updated_at.isoformat()}
        if row is None:
            session.add(SystemState(key="bootstrap_version", value_json=payload, updated_at=updated_at))
            return True
        row.value_json = payload
        row.updated_at = updated_at
        return True


def bootstrap_workspace(
    settings: Settings,
    *,
    session_factory: sessionmaker[Session] | None = None,
    bootstrap_version: str = DEFAULT_BOOTSTRAP_VERSION,
) -> WorkspaceBootstrapResult:
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.triage_workspace_dir.mkdir(parents=True, exist_ok=True)

    git_initialized, initial_commit_created = ensure_workspace_git_repository(settings)
    verify_required_path(settings.repo_mount_dir, label="repo mount")
    verify_required_path(settings.manuals_mount_dir, label="manuals mount")
    agents_written, skill_written = ensure_workspace_files(settings)

    bootstrap_version_written = False
    if session_factory is not None:
        bootstrap_version_written = write_bootstrap_version(
            session_factory,
            version=bootstrap_version,
        )

    return WorkspaceBootstrapResult(
        uploads_dir=str(settings.uploads_dir),
        workspace_dir=str(settings.triage_workspace_dir),
        repo_mount_dir=str(settings.repo_mount_dir),
        manuals_mount_dir=str(settings.manuals_mount_dir),
        git_initialized=git_initialized,
        initial_commit_created=initial_commit_created,
        agents_written=agents_written,
        skill_written=skill_written,
        bootstrap_version_written=bootstrap_version_written,
    )

```
# End of file: shared/bootstrap.py

# File: shared/__init__.py
```python
"""Shared persistence, configuration, and domain helpers for Stage 1."""

```
# End of file: shared/__init__.py

# File: shared/workspace_contract.py
```python
from __future__ import annotations


EXACT_AGENTS_MD = """This repository is the Stage 1 custom triage workspace.

You are performing Stage 1 ticket triage only.

Hard rules:
1. Stage 1 is read-only.
2. Do not modify files under app/ or manuals/.
3. Do not inspect databases, DDL, schema dumps, or logs.
4. Do not use web search.
5. Use only the ticket title, public and internal ticket messages, attached images, files under manuals/, and files under app/.
6. Search manuals/ first for support, access, and operations guidance.
7. Inspect app/ when repository understanding is needed.
8. Distinguish among: support, access_config, data_ops, bug, feature, unknown.
9. Ask at most 3 clarifying questions.
10. Never promise a fix, implementation, release, or timeline.
11. Prefer concise requester-facing replies.
12. Auto-answer support/access questions only when the available evidence strongly supports the answer.
13. If information is ambiguous, missing, conflicting, or likely incorrect, ask clarifying questions instead of guessing.
14. Return only the final JSON object that matches the provided schema.
15. Treat screenshots as evidence but do not claim certainty beyond what is visible.
16. If evidence is weak or absent, do not invent procedural answers.
17. impact_level means business/user impact in Stage 1, not technical blast radius.
18. development_needed is a triage estimate only.
19. Never propose edits, patches, commits, branches, migrations, or database changes in Stage 1.
20. Internal messages may inform internal analysis and routing.
21. Do not disclose internal-only information in automatic public replies unless the same information is already present in public ticket content.
"""


EXACT_SKILL_MD = """---
name: stage1-triage
description: Classify a ticket, search manuals/ and app/ as needed, ask concise clarifying questions when needed, and draft either a safe public reply or an internal routing note. Never modify code, never inspect databases, and never propose patches.
---

Use this skill when:
- the task is a support ticket, internal request, bug report, or feature request written in natural language
- screenshots may help clarify the request
- the workspace contains app/ and manuals/
- the output must be structured JSON for automation

Do not use this skill when:
- code modification is required
- patch generation is required
- database or DDL analysis is required
- external web research is required

Workflow:
1. Read the ticket title and all relevant ticket messages carefully.
2. Search manuals/ first when support, access, or operations guidance may exist.
3. Inspect app/ when repository understanding is needed.
4. Use attached images when relevant.
5. Classify the ticket into exactly one class.
6. Determine if the ticket likely needs development.
7. Determine if clarification is needed.
8. If clarification is needed, ask only the minimum high-value questions, maximum 3.
9. If the available evidence strongly supports an answer and confidence is high, draft a concise public reply.
10. If the request is clearly understood but should go to Dev/TI, draft a concise public confirmation only if it is safe and useful.
11. Always produce a concise internal summary.
12. Internal-only notes may inform internal summaries and routing, but must not be disclosed in automatic public replies unless already public.
13. Return only the final JSON matching the provided schema.

Quality bar:
- do not repeat information already present
- do not ask questions that the image or files already answer
- do not claim certainty without evidence
- keep public text concise and practical
"""

```
# End of file: shared/workspace_contract.py

# File: shared/tickets.py
```python
from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from shared.models import (
    AiDraft,
    AiDraftStatus,
    AiRun,
    AiRunStatus,
    AiRunTrigger,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    StatusChangedByType,
    Ticket,
    TicketAttachment,
    TicketMessage,
    TicketStatus,
    TicketStatusHistory,
    TicketRequeueTrigger,
    TicketView,
    User,
)


class TicketError(ValueError):
    """Base class for shared ticket-domain helper errors."""


class MissingTicketReferenceNumberError(TicketError):
    """Raised when a ticket reference cannot be derived yet."""


class ActiveAIRunExistsError(TicketError):
    """Raised when a second active AI run is requested for the same ticket."""


class InvalidDraftStateError(TicketError):
    """Raised when a draft transition is attempted from the wrong state."""


ACTIVE_AI_RUN_STATUSES = (
    AiRunStatus.PENDING.value,
    AiRunStatus.RUNNING.value,
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_requeue_trigger(value: TicketRequeueTrigger | str) -> str:
    return value.value if isinstance(value, TicketRequeueTrigger) else value


def normalize_status(value: TicketStatus | str) -> str:
    return value.value if isinstance(value, TicketStatus) else value


def normalize_changed_by_type(value: StatusChangedByType | str) -> str:
    return value.value if isinstance(value, StatusChangedByType) else value


def normalize_run_trigger(value: AiRunTrigger | str) -> str:
    return value.value if isinstance(value, AiRunTrigger) else value


def format_ticket_reference(reference_num: int) -> str:
    return f"T-{reference_num:06d}"


def assign_ticket_reference(ticket: Ticket) -> str:
    if ticket.reference_num is None:
        raise MissingTicketReferenceNumberError(
            "Ticket reference_num must be assigned before formatting the reference"
        )
    ticket.reference = format_ticket_reference(ticket.reference_num)
    return ticket.reference


def bump_ticket_updated_at(ticket: Ticket, when: datetime | None = None) -> datetime:
    ticket.updated_at = when or now_utc()
    return ticket.updated_at


def change_ticket_status(
    session: Session,
    ticket: Ticket,
    to_status: TicketStatus | str,
    *,
    changed_by_type: StatusChangedByType | str,
    changed_by_user_id: uuid.UUID | None = None,
    note: str | None = None,
    changed_at: datetime | None = None,
) -> TicketStatusHistory | None:
    target_status = normalize_status(to_status)
    previous_status = ticket.status
    if previous_status == target_status:
        return None

    changed_at = changed_at or now_utc()
    ticket.status = target_status
    ticket.resolved_at = changed_at if target_status == TicketStatus.RESOLVED.value else None
    bump_ticket_updated_at(ticket, changed_at)

    history = TicketStatusHistory(
        ticket_id=ticket.id,
        from_status=previous_status,
        to_status=target_status,
        changed_by_user_id=changed_by_user_id,
        changed_by_type=normalize_changed_by_type(changed_by_type),
        note=note,
        created_at=changed_at,
    )
    session.add(history)
    return history


def first_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "Untitled ticket"
    parts = re.split(r"(?<=[.!?])\s+|\n+", stripped, maxsplit=1)
    candidate = parts[0].strip() if parts else stripped
    return candidate or "Untitled ticket"


def derive_ticket_title(title: str | None, description_text: str) -> str:
    candidate = (title or "").strip()
    if candidate:
        return candidate[:120]
    return first_sentence(description_text)[:120]


def _needs_manual_reference_assignment(session: Session) -> bool:
    bind = session.get_bind()
    return bind is not None and bind.dialect.name == "sqlite"


def _next_reference_num(session: Session) -> int:
    next_value = session.scalar(sa.select(sa.func.coalesce(sa.func.max(Ticket.reference_num), 0) + 1))
    return int(next_value or 1)


def upsert_ticket_view(
    session: Session,
    *,
    user_id: uuid.UUID,
    ticket_id: uuid.UUID,
    viewed_at: datetime | None = None,
) -> TicketView:
    viewed_at = viewed_at or now_utc()
    ticket_view = session.scalar(
        sa.select(TicketView).where(
            TicketView.user_id == user_id,
            TicketView.ticket_id == ticket_id,
        )
    )
    if ticket_view is None:
        ticket_view = TicketView(user_id=user_id, ticket_id=ticket_id, last_viewed_at=viewed_at)
        session.add(ticket_view)
    else:
        ticket_view.last_viewed_at = viewed_at
    return ticket_view


def supersede_pending_drafts(
    session: Session,
    *,
    ticket_id: uuid.UUID,
    keep_draft_id: uuid.UUID | None = None,
) -> int:
    drafts = session.scalars(
        sa.select(AiDraft).where(
            AiDraft.ticket_id == ticket_id,
            AiDraft.status == AiDraftStatus.PENDING_APPROVAL.value,
        )
    ).all()
    updated = 0
    for draft in drafts:
        if keep_draft_id is not None and draft.id == keep_draft_id:
            continue
        draft.status = AiDraftStatus.SUPERSEDED.value
        updated += 1
    return updated


def find_active_ai_run(session: Session, *, ticket_id: uuid.UUID) -> AiRun | None:
    return session.scalar(
        sa.select(AiRun).where(
            AiRun.ticket_id == ticket_id,
            AiRun.status.in_(ACTIVE_AI_RUN_STATUSES),
        )
    )


def create_pending_ai_run(
    session: Session,
    *,
    ticket_id: uuid.UUID,
    triggered_by: AiRunTrigger | str,
    requested_by_user_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
) -> AiRun:
    existing = find_active_ai_run(session, ticket_id=ticket_id)
    if existing is not None:
        raise ActiveAIRunExistsError(
            f"Ticket {ticket_id} already has an active AI run ({existing.id})"
        )

    run = AiRun(
        ticket_id=ticket_id,
        status=AiRunStatus.PENDING.value,
        triggered_by=normalize_run_trigger(triggered_by),
        requested_by_user_id=requested_by_user_id,
        created_at=created_at or now_utc(),
    )
    session.add(run)
    return run


def create_ticket_message(
    session: Session,
    *,
    ticket_id: uuid.UUID,
    author_user_id: uuid.UUID | None,
    author_type: MessageAuthorType | str,
    visibility: MessageVisibility | str,
    source: MessageSource | str,
    body_markdown: str,
    body_text: str,
    ai_run_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
) -> TicketMessage:
    message = TicketMessage(
        ticket_id=ticket_id,
        author_user_id=author_user_id,
        author_type=author_type.value if isinstance(author_type, MessageAuthorType) else author_type,
        visibility=visibility.value if isinstance(visibility, MessageVisibility) else visibility,
        source=source.value if isinstance(source, MessageSource) else source,
        body_markdown=body_markdown,
        body_text=body_text,
        ai_run_id=ai_run_id,
        created_at=created_at or now_utc(),
    )
    session.add(message)
    return message


def create_requester_ticket(
    session: Session,
    *,
    creator: User,
    title: str | None,
    description_markdown: str,
    description_text: str,
    urgent: bool,
    created_at: datetime | None = None,
) -> tuple[Ticket, TicketMessage, AiRun]:
    created_at = created_at or now_utc()
    reference_num = _next_reference_num(session) if _needs_manual_reference_assignment(session) else None

    ticket = Ticket(
        reference_num=reference_num,
        reference="pending",
        title=derive_ticket_title(title, description_text),
        created_by_user_id=creator.id,
        status=TicketStatus.NEW.value,
        urgent=urgent,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(ticket)
    session.flush()

    if ticket.reference_num is None:
        ticket.reference_num = _next_reference_num(session)
        session.flush()
    assign_ticket_reference(ticket)

    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=creator.id,
        author_type=MessageAuthorType.REQUESTER,
        visibility=MessageVisibility.PUBLIC,
        source=MessageSource.TICKET_CREATE,
        body_markdown=description_markdown,
        body_text=description_text,
        created_at=created_at,
    )
    run = create_pending_ai_run(
        session,
        ticket_id=ticket.id,
        triggered_by=AiRunTrigger.NEW_TICKET,
        requested_by_user_id=creator.id,
        created_at=created_at,
    )
    session.add(
        TicketStatusHistory(
            ticket_id=ticket.id,
            from_status=None,
            to_status=TicketStatus.NEW.value,
            changed_by_user_id=creator.id,
            changed_by_type=StatusChangedByType.REQUESTER.value,
            created_at=created_at,
        )
    )
    upsert_ticket_view(session, user_id=creator.id, ticket_id=ticket.id, viewed_at=created_at)
    return ticket, message, run


def add_requester_reply(
    session: Session,
    *,
    ticket: Ticket,
    requester: User,
    body_markdown: str,
    body_text: str,
    created_at: datetime | None = None,
) -> tuple[TicketMessage, AiRun | None]:
    created_at = created_at or now_utc()
    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=requester.id,
        author_type=MessageAuthorType.REQUESTER,
        visibility=MessageVisibility.PUBLIC,
        source=MessageSource.REQUESTER_REPLY,
        body_markdown=body_markdown,
        body_text=body_text,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)

    trigger = (
        AiRunTrigger.REOPEN.value
        if ticket.status == TicketStatus.RESOLVED.value
        else AiRunTrigger.REQUESTER_REPLY.value
    )
    run: AiRun | None = None
    active_run = find_active_ai_run(session, ticket_id=ticket.id)
    if active_run is None:
        run = create_pending_ai_run(
            session,
            ticket_id=ticket.id,
            triggered_by=trigger,
            requested_by_user_id=requester.id,
            created_at=created_at,
        )
    else:
        ticket.requeue_requested = True
        ticket.requeue_trigger = normalize_requeue_trigger(trigger)

    change_ticket_status(
        session,
        ticket,
        TicketStatus.AI_TRIAGE,
        changed_by_type=StatusChangedByType.REQUESTER,
        changed_by_user_id=requester.id,
        changed_at=created_at,
    )
    upsert_ticket_view(session, user_id=requester.id, ticket_id=ticket.id, viewed_at=created_at)
    return message, run


def mark_ticket_resolved(
    session: Session,
    *,
    ticket: Ticket,
    user: User,
    changed_by_type: StatusChangedByType | str,
    changed_at: datetime | None = None,
) -> TicketStatusHistory | None:
    changed_at = changed_at or now_utc()
    history = change_ticket_status(
        session,
        ticket,
        TicketStatus.RESOLVED,
        changed_by_type=changed_by_type,
        changed_by_user_id=user.id,
        changed_at=changed_at,
    )
    upsert_ticket_view(session, user_id=user.id, ticket_id=ticket.id, viewed_at=changed_at)
    return history


def set_ticket_assignment(
    session: Session,
    *,
    ticket: Ticket,
    assigned_to_user_id: uuid.UUID | None,
    actor: User,
    changed_at: datetime | None = None,
) -> bool:
    changed_at = changed_at or now_utc()
    changed = ticket.assigned_to_user_id != assigned_to_user_id
    if changed:
        ticket.assigned_to_user_id = assigned_to_user_id
        bump_ticket_updated_at(ticket, changed_at)
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=changed_at)
    return changed


def set_ticket_status_for_ops(
    session: Session,
    *,
    ticket: Ticket,
    actor: User,
    to_status: TicketStatus | str,
    note: str | None = None,
    changed_at: datetime | None = None,
) -> TicketStatusHistory | None:
    changed_at = changed_at or now_utc()
    history = change_ticket_status(
        session,
        ticket,
        to_status,
        changed_by_type=StatusChangedByType.DEV_TI,
        changed_by_user_id=actor.id,
        note=note,
        changed_at=changed_at,
    )
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=changed_at)
    return history


def add_public_reply(
    session: Session,
    *,
    ticket: Ticket,
    actor: User,
    body_markdown: str,
    body_text: str,
    next_status: TicketStatus | str,
    created_at: datetime | None = None,
) -> tuple[TicketMessage, TicketStatusHistory | None]:
    created_at = created_at or now_utc()
    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=actor.id,
        author_type=MessageAuthorType.DEV_TI,
        visibility=MessageVisibility.PUBLIC,
        source=MessageSource.HUMAN_PUBLIC_REPLY,
        body_markdown=body_markdown,
        body_text=body_text,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)
    history = change_ticket_status(
        session,
        ticket,
        next_status,
        changed_by_type=StatusChangedByType.DEV_TI,
        changed_by_user_id=actor.id,
        changed_at=created_at,
    )
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=created_at)
    return message, history


def add_internal_note(
    session: Session,
    *,
    ticket: Ticket,
    actor: User,
    body_markdown: str,
    body_text: str,
    created_at: datetime | None = None,
) -> TicketMessage:
    created_at = created_at or now_utc()
    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=actor.id,
        author_type=MessageAuthorType.DEV_TI,
        visibility=MessageVisibility.INTERNAL,
        source=MessageSource.HUMAN_INTERNAL_NOTE,
        body_markdown=body_markdown,
        body_text=body_text,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=created_at)
    return message


def request_manual_rerun(
    session: Session,
    *,
    ticket: Ticket,
    actor: User,
    requested_at: datetime | None = None,
) -> AiRun | None:
    requested_at = requested_at or now_utc()
    run = find_active_ai_run(session, ticket_id=ticket.id)
    if run is None:
        run = create_pending_ai_run(
            session,
            ticket_id=ticket.id,
            triggered_by=AiRunTrigger.MANUAL_RERUN,
            requested_by_user_id=actor.id,
            created_at=requested_at,
        )
        change_ticket_status(
            session,
            ticket,
            TicketStatus.AI_TRIAGE,
            changed_by_type=StatusChangedByType.DEV_TI,
            changed_by_user_id=actor.id,
            changed_at=requested_at,
        )
    else:
        ticket.requeue_requested = True
        ticket.requeue_trigger = TicketRequeueTrigger.MANUAL_RERUN.value
        bump_ticket_updated_at(ticket, requested_at)
        run = None
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=requested_at)
    return run


def approve_ai_draft(
    session: Session,
    *,
    ticket: Ticket,
    draft: AiDraft,
    actor: User,
    next_status: TicketStatus | str,
    published_at: datetime | None = None,
) -> tuple[TicketMessage, TicketStatusHistory | None]:
    if draft.status != AiDraftStatus.PENDING_APPROVAL.value:
        raise InvalidDraftStateError("Only pending approval drafts can be published")

    published_at = published_at or now_utc()
    message = create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=None,
        author_type=MessageAuthorType.AI,
        visibility=MessageVisibility.PUBLIC,
        source=MessageSource.AI_DRAFT_PUBLISHED,
        body_markdown=draft.body_markdown,
        body_text=draft.body_text,
        ai_run_id=draft.ai_run_id,
        created_at=published_at,
    )
    draft.status = AiDraftStatus.PUBLISHED.value
    draft.reviewed_by_user_id = actor.id
    draft.reviewed_at = published_at
    draft.published_message_id = message.id
    bump_ticket_updated_at(ticket, published_at)
    history = change_ticket_status(
        session,
        ticket,
        next_status,
        changed_by_type=StatusChangedByType.DEV_TI,
        changed_by_user_id=actor.id,
        changed_at=published_at,
    )
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=published_at)
    return message, history


def reject_ai_draft(
    session: Session,
    *,
    ticket: Ticket,
    draft: AiDraft,
    actor: User,
    rejected_at: datetime | None = None,
) -> None:
    if draft.status != AiDraftStatus.PENDING_APPROVAL.value:
        raise InvalidDraftStateError("Only pending approval drafts can be rejected")

    rejected_at = rejected_at or now_utc()
    draft.status = AiDraftStatus.REJECTED.value
    draft.reviewed_by_user_id = actor.id
    draft.reviewed_at = rejected_at
    bump_ticket_updated_at(ticket, rejected_at)
    upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=rejected_at)

```
# End of file: shared/tickets.py

# File: shared/db.py
```python
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from shared.config import Settings, get_settings


def get_database_url(settings: Settings | None = None) -> str:
    resolved = settings or get_settings()
    return resolved.database_url


def make_engine(settings: Settings | None = None, url: str | None = None) -> Engine:
    database_url = url or get_database_url(settings)
    return create_engine(database_url, future=True)


def make_session_factory(
    settings: Settings | None = None,
    url: str | None = None,
) -> sessionmaker[Session]:
    engine = make_engine(settings=settings, url=url)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

```
# End of file: shared/db.py

# File: shared/migrations/env.py
```python
from __future__ import annotations

from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import get_settings
from shared.models import Base


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

```
# End of file: shared/migrations/env.py

# File: shared/migrations/script.py.mako
```text
"""${message}"""

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}

```
# End of file: shared/migrations/script.py.mako

# File: shared/migrations/versions/20260319_0001_initial.py
```python
"""Initial Stage 1 triage schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260319_0001"
down_revision = None
branch_labels = None
depends_on = None


def enum_type(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "role",
            enum_type("user_role", "requester", "dev_ti", "admin"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("csrf_token", sa.Text(), nullable=False),
        sa.Column("remember_me", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("user_agent", sa.Text()),
        sa.Column("ip_address", sa.Text()),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("reference_num", sa.BigInteger(), sa.Identity(start=1), nullable=False),
        sa.Column("reference", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assigned_to_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "status",
            enum_type(
                "ticket_status",
                "new",
                "ai_triage",
                "waiting_on_user",
                "waiting_on_dev_ti",
                "resolved",
            ),
            nullable=False,
        ),
        sa.Column("urgent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "ticket_class",
            enum_type(
                "ticket_class",
                "support",
                "access_config",
                "data_ops",
                "bug",
                "feature",
                "unknown",
            ),
        ),
        sa.Column("ai_confidence", sa.Numeric(4, 3)),
        sa.Column("impact_level", enum_type("impact_level", "low", "medium", "high", "unknown")),
        sa.Column("development_needed", sa.Boolean()),
        sa.Column(
            "clarification_rounds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("requester_language", sa.Text()),
        sa.Column("last_processed_hash", sa.Text()),
        sa.Column("last_ai_action", sa.Text()),
        sa.Column("requeue_requested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "requeue_trigger",
            enum_type("ticket_requeue_trigger", "requester_reply", "manual_rerun", "reopen"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("reference_num"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_tickets_status_updated_at", "tickets", ["status", sa.text("updated_at DESC")])
    op.create_index(
        "ix_tickets_created_by_updated_at",
        "tickets",
        ["created_by_user_id", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_tickets_assigned_to_updated_at",
        "tickets",
        ["assigned_to_user_id", sa.text("updated_at DESC")],
    )
    op.create_index(
        "ix_tickets_urgent_status_updated_at",
        "tickets",
        ["urgent", "status", sa.text("updated_at DESC")],
    )

    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "status",
            enum_type(
                "ai_run_status",
                "pending",
                "running",
                "succeeded",
                "failed",
                "skipped",
                "superseded",
            ),
            nullable=False,
        ),
        sa.Column(
            "triggered_by",
            enum_type("ai_run_trigger", "new_ticket", "requester_reply", "manual_rerun", "reopen"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("input_hash", sa.Text()),
        sa.Column("model_name", sa.Text()),
        sa.Column("prompt_path", sa.Text()),
        sa.Column("schema_path", sa.Text()),
        sa.Column("final_output_path", sa.Text()),
        sa.Column("stdout_jsonl_path", sa.Text()),
        sa.Column("stderr_path", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("error_text", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_ai_runs_status_created_at", "ai_runs", ["status", "created_at"])
    op.create_index("ix_ai_runs_ticket_created_at_desc", "ai_runs", ["ticket_id", sa.text("created_at DESC")])
    op.create_index(
        "uq_ai_runs_ticket_active",
        "ai_runs",
        ["ticket_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )

    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "author_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "author_type",
            enum_type("message_author_type", "requester", "dev_ti", "ai", "system"),
            nullable=False,
        ),
        sa.Column(
            "visibility",
            enum_type("message_visibility", "public", "internal"),
            nullable=False,
        ),
        sa.Column(
            "source",
            enum_type(
                "message_source",
                "ticket_create",
                "requester_reply",
                "human_public_reply",
                "human_internal_note",
                "ai_auto_public",
                "ai_internal_note",
                "ai_draft_published",
                "system",
            ),
            nullable=False,
        ),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column(
            "ai_run_id",
            sa.Uuid(),
            sa.ForeignKey("ai_runs.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_ticket_messages_ticket_created_at", "ticket_messages", ["ticket_id", "created_at"])
    op.create_index(
        "ix_ticket_messages_ticket_visibility_created_at",
        "ticket_messages",
        ["ticket_id", "visibility", "created_at"],
    )

    op.create_table(
        "ticket_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "message_id",
            sa.Uuid(),
            sa.ForeignKey("ticket_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "visibility",
            enum_type("attachment_visibility", "public", "internal"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_ticket_attachments_ticket_id", "ticket_attachments", ["ticket_id"])
    op.create_index("ix_ticket_attachments_message_id", "ticket_attachments", ["message_id"])
    op.create_index("ix_ticket_attachments_sha256", "ticket_attachments", ["sha256"])

    op.create_table(
        "ticket_status_history",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "from_status",
            enum_type(
                "history_from_status",
                "new",
                "ai_triage",
                "waiting_on_user",
                "waiting_on_dev_ti",
                "resolved",
            ),
        ),
        sa.Column(
            "to_status",
            enum_type(
                "history_to_status",
                "new",
                "ai_triage",
                "waiting_on_user",
                "waiting_on_dev_ti",
                "resolved",
            ),
            nullable=False,
        ),
        sa.Column(
            "changed_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "changed_by_type",
            enum_type("status_changed_by_type", "requester", "dev_ti", "ai", "system"),
            nullable=False,
        ),
        sa.Column("note", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_ticket_status_history_ticket_created_at",
        "ticket_status_history",
        ["ticket_id", "created_at"],
    )

    op.create_table(
        "ticket_views",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "last_viewed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("user_id", "ticket_id", name="pk_ticket_views"),
    )

    op.create_table(
        "ai_drafts",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), sa.ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "kind",
            enum_type("ai_draft_kind", "public_reply"),
            nullable=False,
        ),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            enum_type(
                "ai_draft_status",
                "pending_approval",
                "approved",
                "rejected",
                "superseded",
                "published",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "reviewed_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "published_message_id",
            sa.Uuid(),
            sa.ForeignKey("ticket_messages.id", ondelete="SET NULL"),
        ),
    )
    op.create_index(
        "ix_ai_drafts_ticket_status_created_at_desc",
        "ai_drafts",
        ["ticket_id", "status", sa.text("created_at DESC")],
    )
    op.create_index("ix_ai_drafts_ai_run_id", "ai_drafts", ["ai_run_id"])

    op.create_table(
        "system_state",
        sa.Column("key", sa.Text(), primary_key=True, nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_table("system_state")
    op.drop_index("ix_ai_drafts_ai_run_id", table_name="ai_drafts")
    op.drop_index("ix_ai_drafts_ticket_status_created_at_desc", table_name="ai_drafts")
    op.drop_table("ai_drafts")
    op.drop_table("ticket_views")
    op.drop_index("ix_ticket_status_history_ticket_created_at", table_name="ticket_status_history")
    op.drop_table("ticket_status_history")
    op.drop_index("ix_ticket_attachments_sha256", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_message_id", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_ticket_id", table_name="ticket_attachments")
    op.drop_table("ticket_attachments")
    op.drop_index("ix_ticket_messages_ticket_visibility_created_at", table_name="ticket_messages")
    op.drop_index("ix_ticket_messages_ticket_created_at", table_name="ticket_messages")
    op.drop_table("ticket_messages")
    op.drop_index("uq_ai_runs_ticket_active", table_name="ai_runs")
    op.drop_index("ix_ai_runs_ticket_created_at_desc", table_name="ai_runs")
    op.drop_index("ix_ai_runs_status_created_at", table_name="ai_runs")
    op.drop_table("ai_runs")
    op.drop_index("ix_tickets_urgent_status_updated_at", table_name="tickets")
    op.drop_index("ix_tickets_assigned_to_updated_at", table_name="tickets")
    op.drop_index("ix_tickets_created_by_updated_at", table_name="tickets")
    op.drop_index("ix_tickets_status_updated_at", table_name="tickets")
    op.drop_table("tickets")
    op.drop_table("sessions")
    op.drop_table("users")

```
# End of file: shared/migrations/versions/20260319_0001_initial.py

# File: scripts/create_user.py
```python
from __future__ import annotations

import argparse

try:
    from _common import print_json, resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import print_json, resolve_runtime
from shared.db import session_scope
from shared.user_admin import UserAdminError, create_user_account


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a local triage user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", required=True, choices=["requester", "dev_ti", "admin"])
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    _, resolved_session_factory = resolve_runtime(settings=settings, session_factory=session_factory)
    try:
        with session_scope(resolved_session_factory) as session:
            user = create_user_account(
                session,
                email=args.email,
                display_name=args.display_name,
                password=args.password,
                role=args.role,
            )
            payload = {
                "status": "ok",
                "user_id": str(user.id),
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
            }
    except UserAdminError as exc:
        print_json({"status": "error", "error": str(exc)})
        return 1

    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/create_user.py

# File: scripts/create_admin.py
```python
from __future__ import annotations

import argparse

try:
    from _common import print_json, resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import print_json, resolve_runtime
from shared.db import session_scope
from shared.models import UserRole
from shared.user_admin import UserAdminError, create_user_account


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create an admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--password", required=True)
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    _, resolved_session_factory = resolve_runtime(settings=settings, session_factory=session_factory)
    try:
        with session_scope(resolved_session_factory) as session:
            user = create_user_account(
                session,
                email=args.email,
                display_name=args.display_name,
                password=args.password,
                role=UserRole.ADMIN.value,
            )
            payload = {
                "status": "ok",
                "user_id": str(user.id),
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
            }
    except UserAdminError as exc:
        print_json({"status": "error", "error": str(exc)})
        return 1

    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/create_admin.py

# File: scripts/set_password.py
```python
from __future__ import annotations

import argparse

try:
    from _common import print_json, resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import print_json, resolve_runtime
from shared.db import session_scope
from shared.user_admin import UserAdminError, set_user_password


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reset a local triage user password.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    _, resolved_session_factory = resolve_runtime(settings=settings, session_factory=session_factory)
    try:
        with session_scope(resolved_session_factory) as session:
            user = set_user_password(session, email=args.email, password=args.password)
            payload = {
                "status": "ok",
                "user_id": str(user.id),
                "email": user.email,
            }
    except UserAdminError as exc:
        print_json({"status": "error", "error": str(exc)})
        return 1

    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/set_password.py

# File: scripts/_common.py
```python
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.config import Settings, get_settings  # noqa: E402
from shared.db import make_session_factory  # noqa: E402


def resolve_runtime(
    *,
    settings: Settings | None = None,
    session_factory=None,
):
    resolved_settings = settings or get_settings()
    resolved_session_factory = session_factory or make_session_factory(settings=resolved_settings)
    return resolved_settings, resolved_session_factory


def print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, default=str))

```
# End of file: scripts/_common.py

# File: scripts/run_worker.py
```python
from __future__ import annotations

import argparse

try:
    from _common import resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import resolve_runtime
from shared.logging import configure_logging
from worker.main import run_worker_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Stage 1 worker.")
    parser.add_argument("--once", action="store_true", help="Process at most one polling iteration.")
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    resolved_settings, resolved_session_factory = resolve_runtime(
        settings=settings,
        session_factory=session_factory,
    )
    configure_logging(service="worker")
    run_worker_loop(
        settings=resolved_settings,
        session_factory=resolved_session_factory,
        once=args.once,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/run_worker.py

# File: scripts/deactivate_user.py
```python
from __future__ import annotations

import argparse

try:
    from _common import print_json, resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import print_json, resolve_runtime
from shared.db import session_scope
from shared.user_admin import UserAdminError, deactivate_user_account


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deactivate a local triage user.")
    parser.add_argument("--email", required=True)
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    _, resolved_session_factory = resolve_runtime(settings=settings, session_factory=session_factory)
    try:
        with session_scope(resolved_session_factory) as session:
            user = deactivate_user_account(session, email=args.email)
            payload = {
                "status": "ok",
                "user_id": str(user.id),
                "email": user.email,
                "is_active": user.is_active,
            }
    except UserAdminError as exc:
        print_json({"status": "error", "error": str(exc)})
        return 1

    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/deactivate_user.py

# File: scripts/__init__.py
```python
"""Executable management scripts for the Stage 1 triage app."""

```
# End of file: scripts/__init__.py

# File: scripts/bootstrap_workspace.py
```python
from __future__ import annotations

import argparse

try:
    from _common import print_json, resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import print_json, resolve_runtime
from shared.bootstrap import DEFAULT_BOOTSTRAP_VERSION, WorkspaceBootstrapError, bootstrap_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap the Stage 1 triage workspace.")
    parser.add_argument(
        "--bootstrap-version",
        default=DEFAULT_BOOTSTRAP_VERSION,
        help="Value written to system_state.bootstrap_version.",
    )
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    resolved_settings, resolved_session_factory = resolve_runtime(
        settings=settings,
        session_factory=session_factory,
    )
    try:
        result = bootstrap_workspace(
            resolved_settings,
            session_factory=resolved_session_factory,
            bootstrap_version=args.bootstrap_version,
        )
    except WorkspaceBootstrapError as exc:
        print_json({"status": "error", "error": str(exc)})
        return 1

    payload = {"status": "ok"}
    payload.update(result.as_dict())
    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/bootstrap_workspace.py

# File: scripts/run_web.py
```python
from __future__ import annotations

import argparse

import uvicorn

try:
    from _common import resolve_runtime
except ImportError:  # pragma: no cover
    from scripts._common import resolve_runtime
from app.main import create_app
from shared.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Stage 1 web app.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    return parser


def main(argv: list[str] | None = None, *, settings=None, session_factory=None) -> int:
    args = build_parser().parse_args(argv)
    resolved_settings, resolved_session_factory = resolve_runtime(
        settings=settings,
        session_factory=session_factory,
    )
    configure_logging(service="web")
    app = create_app(settings=resolved_settings, session_factory=resolved_session_factory)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_config=None,
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

```
# End of file: scripts/run_web.py

# File: tests/test_security.py
```python
from __future__ import annotations

from shared.config import Settings
from shared.security import (
    generate_login_csrf_token,
    hash_password,
    hash_token,
    session_max_age,
    validate_login_csrf_token,
    verify_password,
)


def make_settings() -> Settings:
    return Settings.from_env(
        {
            "APP_BASE_URL": "https://triage.example.test",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "CODEX_API_KEY": "codex-secret",
        }
    )


def test_password_hash_round_trip() -> None:
    hashed = hash_password("hunter2")

    assert hashed != "hunter2"
    assert verify_password(hashed, "hunter2") is True
    assert verify_password(hashed, "wrong") is False


def test_login_csrf_token_round_trip() -> None:
    token = generate_login_csrf_token("secret")

    assert validate_login_csrf_token("secret", token) is True
    assert validate_login_csrf_token("secret", f"{token}x") is False


def test_session_max_age_only_for_remember_me() -> None:
    settings = make_settings()

    assert session_max_age(settings, remember_me=False) is None
    assert session_max_age(settings, remember_me=True) == 30 * 24 * 60 * 60


def test_hash_token_is_sha256_hex() -> None:
    digest = hash_token("plain-token")

    assert len(digest) == 64
    assert digest != "plain-token"

```
# End of file: tests/test_security.py

# File: tests/test_ticket_helpers.py
```python
from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from shared.models import (
    AiDraft,
    AiDraftStatus,
    AiRunStatus,
    AiRunTrigger,
    Base,
    StatusChangedByType,
    Ticket,
    TicketStatus,
    User,
    UserRole,
)
from shared.tickets import (
    ActiveAIRunExistsError,
    assign_ticket_reference,
    change_ticket_status,
    create_pending_ai_run,
    format_ticket_reference,
    supersede_pending_drafts,
    upsert_ticket_view,
)


@pytest.fixture
def session() -> Session:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        yield db


def make_user(email: str) -> User:
    return User(
        email=email,
        display_name=email.split("@", 1)[0],
        password_hash="hashed",
        role=UserRole.REQUESTER.value,
    )


def make_ticket(user_id: uuid.UUID, reference_num: int = 1) -> Ticket:
    ticket = Ticket(
        reference_num=reference_num,
        reference=format_ticket_reference(reference_num),
        title="Title",
        created_by_user_id=user_id,
        status=TicketStatus.NEW.value,
    )
    return ticket


def test_format_ticket_reference_zero_pads() -> None:
    assert format_ticket_reference(42) == "T-000042"


def test_assign_ticket_reference_uses_reference_num() -> None:
    ticket = Ticket(reference_num=12, reference="placeholder", title="x", created_by_user_id=uuid.uuid4(), status="new")
    assert assign_ticket_reference(ticket) == "T-000012"


def test_change_ticket_status_writes_history_and_resolved_at(session: Session) -> None:
    actor = make_user("user@example.com")
    session.add(actor)
    session.flush()
    ticket = make_ticket(actor.id)
    session.add(ticket)
    session.flush()

    changed_at = datetime(2026, 3, 19, tzinfo=timezone.utc)
    history = change_ticket_status(
        session,
        ticket,
        TicketStatus.RESOLVED,
        changed_by_type=StatusChangedByType.DEV_TI,
        changed_by_user_id=actor.id,
        changed_at=changed_at,
    )
    session.flush()

    assert history is not None
    assert ticket.status == TicketStatus.RESOLVED.value
    assert ticket.resolved_at == changed_at
    assert ticket.updated_at == changed_at


def test_upsert_ticket_view_updates_existing_row(session: Session) -> None:
    actor = make_user("viewer@example.com")
    session.add(actor)
    session.flush()
    ticket = make_ticket(actor.id)
    session.add(ticket)
    session.flush()

    first_seen = datetime(2026, 3, 19, 10, tzinfo=timezone.utc)
    second_seen = datetime(2026, 3, 19, 12, tzinfo=timezone.utc)
    first = upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=first_seen)
    session.flush()
    second = upsert_ticket_view(session, user_id=actor.id, ticket_id=ticket.id, viewed_at=second_seen)

    assert first.user_id == second.user_id
    assert second.last_viewed_at == second_seen


def test_supersede_pending_drafts_only_touches_pending_approval(session: Session) -> None:
    actor = make_user("author@example.com")
    session.add(actor)
    session.flush()
    ticket = make_ticket(actor.id)
    session.add(ticket)
    session.flush()
    run = create_pending_ai_run(session, ticket_id=ticket.id, triggered_by=AiRunTrigger.NEW_TICKET)
    run.status = AiRunStatus.SUCCEEDED.value
    session.flush()

    kept = AiDraft(
        ticket_id=ticket.id,
        ai_run_id=run.id,
        kind="public_reply",
        body_markdown="one",
        body_text="one",
        status=AiDraftStatus.PENDING_APPROVAL.value,
    )
    stale = AiDraft(
        ticket_id=ticket.id,
        ai_run_id=run.id,
        kind="public_reply",
        body_markdown="two",
        body_text="two",
        status=AiDraftStatus.PENDING_APPROVAL.value,
    )
    published = AiDraft(
        ticket_id=ticket.id,
        ai_run_id=run.id,
        kind="public_reply",
        body_markdown="three",
        body_text="three",
        status=AiDraftStatus.PUBLISHED.value,
    )
    session.add_all([kept, stale, published])
    session.flush()

    updated = supersede_pending_drafts(session, ticket_id=ticket.id, keep_draft_id=kept.id)

    assert updated == 1
    assert kept.status == AiDraftStatus.PENDING_APPROVAL.value
    assert stale.status == AiDraftStatus.SUPERSEDED.value
    assert published.status == AiDraftStatus.PUBLISHED.value


def test_create_pending_ai_run_rejects_second_active_run(session: Session) -> None:
    actor = make_user("queue@example.com")
    session.add(actor)
    session.flush()
    ticket = make_ticket(actor.id)
    session.add(ticket)
    session.flush()

    create_pending_ai_run(session, ticket_id=ticket.id, triggered_by=AiRunTrigger.NEW_TICKET)
    with pytest.raises(ActiveAIRunExistsError):
        create_pending_ai_run(session, ticket_id=ticket.id, triggered_by=AiRunTrigger.REQUESTER_REPLY)

```
# End of file: tests/test_ticket_helpers.py

# File: tests/test_models.py
```python
from __future__ import annotations

from pathlib import Path

from shared.models import AiRun, Base, TicketView


def test_ai_runs_has_partial_unique_index_for_active_statuses() -> None:
    index = next(index for index in AiRun.__table__.indexes if index.name == "uq_ai_runs_ticket_active")
    predicate = str(index.dialect_options["postgresql"]["where"])

    assert index.unique is True
    assert "pending" in predicate
    assert "running" in predicate


def test_ticket_views_primary_key_matches_prd() -> None:
    primary_key = TicketView.__table__.primary_key

    assert [column.name for column in primary_key.columns] == ["user_id", "ticket_id"]


def test_initial_migration_declares_active_run_partial_index() -> None:
    migration_path = (
        Path(__file__).resolve().parent.parent
        / "shared"
        / "migrations"
        / "versions"
        / "20260319_0001_initial.py"
    )
    content = migration_path.read_text()

    assert "uq_ai_runs_ticket_active" in content
    assert "status IN ('pending', 'running')" in content


def test_metadata_contains_all_prd_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "sessions",
        "tickets",
        "ticket_messages",
        "ticket_attachments",
        "ticket_status_history",
        "ticket_views",
        "ai_runs",
        "ai_drafts",
        "system_state",
    }

```
# End of file: tests/test_models.py

# File: tests/test_config.py
```python
from __future__ import annotations

from pathlib import Path

import pytest

from shared.config import ConfigError, Settings


def test_settings_from_env_applies_required_defaults() -> None:
    settings = Settings.from_env(
        {
            "APP_BASE_URL": "http://localhost:8000",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": "postgresql+psycopg://triage:triage@localhost/triage",
            "CODEX_API_KEY": "codex-secret",
        }
    )

    assert settings.uploads_dir.as_posix() == "/opt/triage/data/uploads"
    assert settings.triage_workspace_dir.as_posix() == "/opt/triage/triage_workspace"
    assert settings.repo_mount_dir.as_posix() == "/opt/triage/triage_workspace/app"
    assert settings.manuals_mount_dir.as_posix() == "/opt/triage/triage_workspace/manuals"
    assert settings.max_images_per_message == 3
    assert settings.max_image_bytes == 5 * 1024 * 1024
    assert settings.session_remember_days == 30


def test_settings_require_core_secrets_database_url_and_codex_key() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env({"APP_BASE_URL": "http://localhost:8000"})


def test_settings_derive_repo_and_manual_paths_from_workspace_override() -> None:
    settings = Settings.from_env(
        {
            "APP_BASE_URL": "http://localhost:8000",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": "postgresql+psycopg://triage:triage@localhost/triage",
            "CODEX_API_KEY": "codex-secret",
            "TRIAGE_WORKSPACE_DIR": "/srv/triage/workspace",
        }
    )

    assert settings.repo_mount_dir == Path("/srv/triage/workspace/app")
    assert settings.manuals_mount_dir == Path("/srv/triage/workspace/manuals")


def test_settings_validate_confidence_bounds() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env(
            {
                "APP_BASE_URL": "http://localhost:8000",
                "APP_SECRET_KEY": "secret",
                "DATABASE_URL": "postgresql+psycopg://triage:triage@localhost/triage",
                "CODEX_API_KEY": "codex-secret",
                "AUTO_SUPPORT_REPLY_MIN_CONFIDENCE": "1.1",
            }
        )


def test_env_example_documents_all_required_inputs() -> None:
    env_example = (
        Path(__file__).resolve().parent.parent / ".env.example"
    ).read_text()

    for variable in (
        "APP_BASE_URL",
        "APP_SECRET_KEY",
        "DATABASE_URL",
        "CODEX_API_KEY",
        "TRIAGE_WORKSPACE_DIR",
        "REPO_MOUNT_DIR",
        "MANUALS_MOUNT_DIR",
    ):
        assert f"{variable}=" in env_example

```
# End of file: tests/test_config.py

# File: tests/test_uploads.py
```python
from __future__ import annotations

import asyncio
from io import BytesIO

from PIL import Image
import pytest
from starlette.datastructures import FormData, Headers, UploadFile

from app.uploads import UploadValidationError, validate_public_image_uploads
from shared.config import Settings


def make_settings(*, max_images_per_message: int = 3, max_image_bytes: int = 5 * 1024 * 1024) -> Settings:
    return Settings.from_env(
        {
            "APP_BASE_URL": "http://testserver",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "CODEX_API_KEY": "codex-secret",
            "MAX_IMAGES_PER_MESSAGE": str(max_images_per_message),
            "MAX_IMAGE_BYTES": str(max_image_bytes),
        }
    )


def make_png_bytes(color: str = "red") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def make_upload(filename: str, data: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_validate_public_image_uploads_rejects_more_than_max_files() -> None:
    settings = make_settings(max_images_per_message=3)
    form = FormData(
        [
            ("attachments", make_upload("1.png", make_png_bytes("red"), "image/png")),
            ("attachments", make_upload("2.png", make_png_bytes("green"), "image/png")),
            ("attachments", make_upload("3.png", make_png_bytes("blue"), "image/png")),
            ("attachments", make_upload("4.png", make_png_bytes("yellow"), "image/png")),
        ]
    )

    with pytest.raises(UploadValidationError, match="at most 3 images"):
        asyncio.run(validate_public_image_uploads(form, settings))


def test_validate_public_image_uploads_rejects_files_over_size_limit() -> None:
    settings = make_settings(max_image_bytes=10)
    form = FormData(
        [
            ("attachments", make_upload("large.png", b"x" * 11, "image/png")),
        ]
    )

    with pytest.raises(UploadValidationError, match="10 bytes or smaller"):
        asyncio.run(validate_public_image_uploads(form, settings))

```
# End of file: tests/test_uploads.py

# File: tests/test_ops_app.py
```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.main import create_app
from shared.config import Settings
from shared.models import (
    AiDraft,
    AiDraftKind,
    AiDraftStatus,
    AiRun,
    AiRunStatus,
    Base,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    Ticket,
    TicketAttachment,
    TicketMessage,
    TicketStatus,
    TicketStatusHistory,
    TicketView,
    User,
    UserRole,
)
from shared.security import hash_password
from shared.tickets import (
    change_ticket_status,
    create_requester_ticket,
    create_ticket_message,
    format_ticket_reference,
    upsert_ticket_view,
)


def make_settings(database_url: str, uploads_dir: Path) -> Settings:
    return Settings.from_env(
        {
            "APP_BASE_URL": "http://testserver",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": database_url,
            "CODEX_API_KEY": "codex-secret",
            "UPLOADS_DIR": str(uploads_dir),
        }
    )


def build_client():
    temp_dir = Path(tempfile.mkdtemp(prefix="triage-stage1-ops-test-"))
    db_path = temp_dir / "test.db"
    uploads_dir = temp_dir / "uploads"
    engine = sa.create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    settings = make_settings(f"sqlite+pysqlite:///{db_path}", uploads_dir)
    app = create_app(settings=settings, session_factory=session_factory)
    client = TestClient(app)
    return client, session_factory


def seed_user(session_factory: sessionmaker[Session], *, email: str, role: str) -> User:
    with session_factory() as session:
        user = User(
            email=email,
            display_name=email.split("@", 1)[0],
            password_hash=hash_password("password123"),
            role=role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def login(client: TestClient, email: str, password: str = "password123"):
    response = client.get("/login")
    csrf_token = response.cookies.get("triage_login_csrf")
    return client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": csrf_token},
        follow_redirects=False,
    )


def create_ticket_fixture(
    session_factory: sessionmaker[Session],
    *,
    creator: User,
    title: str,
    body: str,
    status: str = TicketStatus.NEW.value,
    ticket_class: str | None = None,
    urgent: bool = False,
    assigned_to_user_id=None,
    created_at: datetime | None = None,
    ai_run_status: str = AiRunStatus.SUCCEEDED.value,
) -> tuple[Ticket, AiRun]:
    created_at = created_at or datetime.now(timezone.utc)
    with session_factory() as session:
        creator_db = session.get(User, creator.id)
        assert creator_db is not None
        ticket, _, run = create_requester_ticket(
            session,
            creator=creator_db,
            title=title,
            description_markdown=body,
            description_text=body,
            urgent=urgent,
            created_at=created_at,
        )
        session.flush()
        run.status = ai_run_status
        run.ended_at = created_at
        ticket.ticket_class = ticket_class
        ticket.assigned_to_user_id = assigned_to_user_id
        if status != TicketStatus.NEW.value:
            change_ticket_status(
                session,
                ticket,
                status,
                changed_by_type="system",
                changed_at=created_at + timedelta(minutes=5),
            )
        session.commit()
        session.refresh(ticket)
        session.refresh(run)
        return ticket, run


def extract_csrf(html: str) -> str:
    return html.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]


def normalize_dt(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def test_ops_board_filters_and_human_actions() -> None:
    client, session_factory = build_client()
    ops_user = seed_user(session_factory, email="ops@example.com", role=UserRole.DEV_TI.value)
    requester = seed_user(session_factory, email="requester@example.com", role=UserRole.REQUESTER.value)

    base_time = datetime(2026, 3, 20, 8, tzinfo=timezone.utc)
    filtered_ticket, filtered_run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Bug in import flow",
        body="Import crashes after upload.",
        status=TicketStatus.WAITING_ON_DEV_TI.value,
        ticket_class="bug",
        urgent=True,
        assigned_to_user_id=ops_user.id,
        created_at=base_time,
    )
    self_ticket, _ = create_ticket_fixture(
        session_factory,
        creator=ops_user,
        title="Ops-owned ticket",
        body="Created by ops.",
        status=TicketStatus.WAITING_ON_DEV_TI.value,
        ticket_class="support",
        created_at=base_time + timedelta(hours=1),
    )
    other_ticket, _ = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Resolved support request",
        body="Issue already fixed.",
        status=TicketStatus.RESOLVED.value,
        ticket_class="support",
        created_at=base_time + timedelta(hours=2),
    )

    with session_factory() as session:
        ticket = session.get(Ticket, filtered_ticket.id)
        ops = session.get(User, ops_user.id)
        assert ticket is not None
        assert ops is not None
        upsert_ticket_view(
            session,
            user_id=ops.id,
            ticket_id=ticket.id,
            viewed_at=base_time - timedelta(days=1),
        )
        session.add(
            AiDraft(
                ticket_id=ticket.id,
                ai_run_id=filtered_run.id,
                kind=AiDraftKind.PUBLIC_REPLY.value,
                body_markdown="Please retry the import with a CSV export from the new screen.",
                body_text="Please retry the import with a CSV export from the new screen.",
                status=AiDraftStatus.PENDING_APPROVAL.value,
            )
        )
        session.commit()

    assert login(client, ops_user.email).status_code == 303

    board_response = client.get(
        "/ops/board",
        params={
            "status": TicketStatus.WAITING_ON_DEV_TI.value,
            "ticket_class": "bug",
            "assigned_to": str(ops_user.id),
            "urgent": "1",
            "needs_approval": "1",
            "updated_since_my_last_view": "1",
        },
    )
    assert board_response.status_code == 200
    assert filtered_ticket.reference in board_response.text
    assert other_ticket.reference not in board_response.text

    created_by_me_response = client.get("/ops/board", params={"created_by_me": "1"})
    assert created_by_me_response.status_code == 200
    assert self_ticket.reference in created_by_me_response.text
    assert filtered_ticket.reference not in created_by_me_response.text

    detail_response = client.get(f"/ops/tickets/{filtered_ticket.reference}")
    csrf_token = extract_csrf(detail_response.text)

    assign_response = client.post(
        f"/ops/tickets/{filtered_ticket.reference}/assign",
        data={"csrf_token": csrf_token, "assigned_to_user_id": ""},
        follow_redirects=False,
    )
    assert assign_response.status_code == 303

    detail_response = client.get(f"/ops/tickets/{filtered_ticket.reference}")
    csrf_token = extract_csrf(detail_response.text)
    note_response = client.post(
        f"/ops/tickets/{filtered_ticket.reference}/note-internal",
        data={"csrf_token": csrf_token, "body": "Investigating app-side validation mismatch."},
        follow_redirects=False,
    )
    assert note_response.status_code == 303

    detail_response = client.get(f"/ops/tickets/{filtered_ticket.reference}")
    csrf_token = extract_csrf(detail_response.text)
    reply_response = client.post(
        f"/ops/tickets/{filtered_ticket.reference}/reply-public",
        data={
            "csrf_token": csrf_token,
            "body": "We are reviewing this with the team and will follow up here.",
            "next_status": TicketStatus.WAITING_ON_USER.value,
        },
        follow_redirects=False,
    )
    assert reply_response.status_code == 303

    detail_response = client.get(f"/ops/tickets/{filtered_ticket.reference}")
    csrf_token = extract_csrf(detail_response.text)
    rerun_response = client.post(
        f"/ops/tickets/{filtered_ticket.reference}/rerun-ai",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert rerun_response.status_code == 303

    with session_factory() as session:
        ticket = session.get(Ticket, filtered_ticket.id)
        assert ticket is not None
        assert ticket.assigned_to_user_id is None
        assert ticket.status == TicketStatus.AI_TRIAGE.value

        internal_note = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.INTERNAL.value,
                TicketMessage.source == MessageSource.HUMAN_INTERNAL_NOTE.value,
            )
        )
        public_reply = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.PUBLIC.value,
                TicketMessage.source == MessageSource.HUMAN_PUBLIC_REPLY.value,
            )
        )
        manual_rerun = session.scalar(
            sa.select(AiRun)
            .where(
                AiRun.ticket_id == ticket.id,
                AiRun.triggered_by == "manual_rerun",
            )
            .order_by(AiRun.created_at.desc())
        )
        ticket_view = session.get(TicketView, (ops_user.id, ticket.id))

        assert internal_note is not None
        assert public_reply is not None
        assert manual_rerun is not None
        assert manual_rerun.status == AiRunStatus.PENDING.value
        assert ticket_view is not None


def test_ops_view_tracking_only_updates_on_detail_and_successful_mutations() -> None:
    client, session_factory = build_client()
    ops_user = seed_user(session_factory, email="ops2@example.com", role=UserRole.DEV_TI.value)
    requester = seed_user(session_factory, email="owner@example.com", role=UserRole.REQUESTER.value)
    ticket, _ = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Visibility check",
        body="Please inspect this ticket.",
        status=TicketStatus.NEW.value,
    )

    old_seen = datetime(2026, 3, 1, tzinfo=timezone.utc)
    with session_factory() as session:
        upsert_ticket_view(session, user_id=ops_user.id, ticket_id=ticket.id, viewed_at=old_seen)
        session.commit()

    assert login(client, ops_user.email).status_code == 303

    board_response = client.get("/ops/board")
    assert board_response.status_code == 200
    with session_factory() as session:
        view_after_board = session.get(TicketView, (ops_user.id, ticket.id))
        assert view_after_board is not None
        assert normalize_dt(view_after_board.last_viewed_at) == old_seen

    detail_response = client.get(f"/ops/tickets/{ticket.reference}")
    assert detail_response.status_code == 200
    with session_factory() as session:
        view_after_detail = session.get(TicketView, (ops_user.id, ticket.id))
        assert view_after_detail is not None
        assert normalize_dt(view_after_detail.last_viewed_at) > old_seen
        detail_seen = normalize_dt(view_after_detail.last_viewed_at)

    csrf_token = extract_csrf(detail_response.text)
    note_response = client.post(
        f"/ops/tickets/{ticket.reference}/note-internal",
        data={"csrf_token": csrf_token, "body": "Operator note."},
        follow_redirects=False,
    )
    assert note_response.status_code == 303

    with session_factory() as session:
        view_after_post = session.get(TicketView, (ops_user.id, ticket.id))
        assert view_after_post is not None
        assert normalize_dt(view_after_post.last_viewed_at) >= detail_seen


def test_ops_invalid_public_reply_does_not_change_ticket_or_view_timestamp() -> None:
    client, session_factory = build_client()
    ops_user = seed_user(session_factory, email="ops-invalid@example.com", role=UserRole.DEV_TI.value)
    requester = seed_user(session_factory, email="owner-invalid@example.com", role=UserRole.REQUESTER.value)
    ticket, _ = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Reply validation",
        body="Need a safe validation path.",
        status=TicketStatus.WAITING_ON_DEV_TI.value,
    )

    original_updated_at = normalize_dt(ticket.updated_at)
    old_seen = datetime(2026, 3, 10, tzinfo=timezone.utc)
    with session_factory() as session:
        upsert_ticket_view(session, user_id=ops_user.id, ticket_id=ticket.id, viewed_at=old_seen)
        session.commit()

    assert login(client, ops_user.email).status_code == 303

    detail_response = client.get(f"/ops/tickets/{ticket.reference}")
    assert detail_response.status_code == 200
    csrf_token = extract_csrf(detail_response.text)
    with session_factory() as session:
        view_after_detail = session.get(TicketView, (ops_user.id, ticket.id))
        assert view_after_detail is not None
        detail_seen = normalize_dt(view_after_detail.last_viewed_at)
        assert detail_seen > old_seen

    invalid_reply_response = client.post(
        f"/ops/tickets/{ticket.reference}/reply-public",
        data={
            "csrf_token": csrf_token,
            "body": "This should not persist.",
            "next_status": "not-a-valid-status",
        },
    )
    assert invalid_reply_response.status_code == 400
    assert "Choose the next public status." in invalid_reply_response.text

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        ticket_view = session.get(TicketView, (ops_user.id, ticket.id))
        public_reply = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.PUBLIC.value,
                TicketMessage.source == MessageSource.HUMAN_PUBLIC_REPLY.value,
            )
        )
        assert ticket_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value
        assert normalize_dt(ticket_db.updated_at) == original_updated_at
        assert ticket_view is not None
        assert normalize_dt(ticket_view.last_viewed_at) == detail_seen
        assert public_reply is None


def test_ops_manual_status_route_updates_history_and_rejects_invalid_status() -> None:
    client, session_factory = build_client()
    ops_user = seed_user(session_factory, email="ops-status@example.com", role=UserRole.DEV_TI.value)
    requester = seed_user(session_factory, email="owner-status@example.com", role=UserRole.REQUESTER.value)
    ticket, _ = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Status control",
        body="Please test the manual status flow.",
        status=TicketStatus.WAITING_ON_DEV_TI.value,
    )

    with session_factory() as session:
        initial_history_count = session.scalar(
            sa.select(sa.func.count()).select_from(TicketStatusHistory).where(TicketStatusHistory.ticket_id == ticket.id)
        )
        upsert_ticket_view(
            session,
            user_id=ops_user.id,
            ticket_id=ticket.id,
            viewed_at=datetime(2026, 3, 12, tzinfo=timezone.utc),
        )
        session.commit()

    assert login(client, ops_user.email).status_code == 303

    detail_response = client.get(f"/ops/tickets/{ticket.reference}")
    assert detail_response.status_code == 200
    csrf_token = extract_csrf(detail_response.text)
    with session_factory() as session:
        view_after_detail = session.get(TicketView, (ops_user.id, ticket.id))
        assert view_after_detail is not None
        detail_seen = normalize_dt(view_after_detail.last_viewed_at)

    invalid_status_response = client.post(
        f"/ops/tickets/{ticket.reference}/set-status",
        data={"csrf_token": csrf_token, "status": "not-a-status"},
    )
    assert invalid_status_response.status_code == 400
    assert "Invalid status." in invalid_status_response.text

    with session_factory() as session:
        ticket_after_invalid = session.get(Ticket, ticket.id)
        view_after_invalid = session.get(TicketView, (ops_user.id, ticket.id))
        history_after_invalid = session.scalar(
            sa.select(sa.func.count()).select_from(TicketStatusHistory).where(TicketStatusHistory.ticket_id == ticket.id)
        )
        assert ticket_after_invalid is not None
        assert ticket_after_invalid.status == TicketStatus.WAITING_ON_DEV_TI.value
        assert ticket_after_invalid.resolved_at is None
        assert view_after_invalid is not None
        assert normalize_dt(view_after_invalid.last_viewed_at) == detail_seen
        assert history_after_invalid == initial_history_count

    detail_response = client.get(f"/ops/tickets/{ticket.reference}")
    assert detail_response.status_code == 200
    csrf_token = extract_csrf(detail_response.text)

    valid_status_response = client.post(
        f"/ops/tickets/{ticket.reference}/set-status",
        data={"csrf_token": csrf_token, "status": TicketStatus.RESOLVED.value},
        follow_redirects=False,
    )
    assert valid_status_response.status_code == 303

    with session_factory() as session:
        ticket_after_valid = session.get(Ticket, ticket.id)
        view_after_valid = session.get(TicketView, (ops_user.id, ticket.id))
        resolved_history = session.scalar(
            sa.select(TicketStatusHistory)
            .where(
                TicketStatusHistory.ticket_id == ticket.id,
                TicketStatusHistory.to_status == TicketStatus.RESOLVED.value,
            )
            .order_by(TicketStatusHistory.created_at.desc(), TicketStatusHistory.id.desc())
        )
        history_after_valid = session.scalar(
            sa.select(sa.func.count()).select_from(TicketStatusHistory).where(TicketStatusHistory.ticket_id == ticket.id)
        )
        assert ticket_after_valid is not None
        assert ticket_after_valid.status == TicketStatus.RESOLVED.value
        assert ticket_after_valid.resolved_at is not None
        assert view_after_valid is not None
        assert normalize_dt(view_after_valid.last_viewed_at) > detail_seen
        assert resolved_history is not None
        assert resolved_history.from_status == TicketStatus.WAITING_ON_DEV_TI.value
        assert resolved_history.to_status == TicketStatus.RESOLVED.value
        assert resolved_history.changed_by_user_id == ops_user.id
        assert history_after_valid == initial_history_count + 1


def test_ops_can_publish_ai_draft_without_exposing_internal_note_to_requester() -> None:
    client, session_factory = build_client()
    ops_user = seed_user(session_factory, email="ops3@example.com", role=UserRole.DEV_TI.value)
    requester = seed_user(session_factory, email="requester2@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Need guidance",
        body="Where do I find the export button?",
        status=TicketStatus.WAITING_ON_DEV_TI.value,
        ticket_class="support",
    )

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        assert ticket_db is not None
        create_ticket_message(
            session,
            ticket_id=ticket_db.id,
            author_user_id=ops_user.id,
            author_type=MessageAuthorType.DEV_TI,
            visibility=MessageVisibility.INTERNAL,
            source=MessageSource.HUMAN_INTERNAL_NOTE,
            body_markdown="Internal: this user is part of the finance pilot.",
            body_text="Internal: this user is part of the finance pilot.",
        )
        draft = AiDraft(
            ticket_id=ticket_db.id,
            ai_run_id=run.id,
            kind=AiDraftKind.PUBLIC_REPLY.value,
            body_markdown="Open **Exports** from the Reports screen and choose CSV.",
            body_text="Open Exports from the Reports screen and choose CSV.",
            status=AiDraftStatus.PENDING_APPROVAL.value,
        )
        session.add(draft)
        session.commit()
        draft_id = draft.id

    assert login(client, ops_user.email).status_code == 303
    detail_response = client.get(f"/ops/tickets/{ticket.reference}")
    assert "finance pilot" in detail_response.text
    csrf_token = extract_csrf(detail_response.text)

    approve_response = client.post(
        f"/ops/drafts/{draft_id}/approve-publish",
        data={"csrf_token": csrf_token, "next_status": TicketStatus.RESOLVED.value},
        follow_redirects=False,
    )
    assert approve_response.status_code == 303

    with session_factory() as session:
        draft = session.get(AiDraft, draft_id)
        ticket_db = session.get(Ticket, ticket.id)
        published = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.source == MessageSource.AI_DRAFT_PUBLISHED.value,
            )
        )
        assert draft is not None
        assert draft.status == AiDraftStatus.PUBLISHED.value
        assert ticket_db is not None
        assert ticket_db.status == TicketStatus.RESOLVED.value
        assert published is not None
        assert published.author_type == MessageAuthorType.AI.value

    client = TestClient(client.app)
    assert login(client, requester.email).status_code == 303
    requester_detail = client.get(f"/app/tickets/{ticket.reference}")
    assert requester_detail.status_code == 200
    assert "Open <strong>Exports</strong> from the Reports screen and choose CSV." in requester_detail.text
    assert "finance pilot" not in requester_detail.text


def test_ops_can_reject_pending_draft_without_publishing_message() -> None:
    client, session_factory = build_client()
    ops_user = seed_user(session_factory, email="ops4@example.com", role=UserRole.DEV_TI.value)
    requester = seed_user(session_factory, email="requester4@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Draft rejection",
        body="I need a response draft.",
        status=TicketStatus.WAITING_ON_DEV_TI.value,
    )

    with session_factory() as session:
        draft = AiDraft(
            ticket_id=ticket.id,
            ai_run_id=run.id,
            kind=AiDraftKind.PUBLIC_REPLY.value,
            body_markdown="Draft body.",
            body_text="Draft body.",
            status=AiDraftStatus.PENDING_APPROVAL.value,
        )
        session.add(draft)
        session.commit()
        draft_id = draft.id

    assert login(client, ops_user.email).status_code == 303
    detail_response = client.get(f"/ops/tickets/{ticket.reference}")
    csrf_token = extract_csrf(detail_response.text)
    reject_response = client.post(
        f"/ops/drafts/{draft_id}/reject",
        data={"csrf_token": csrf_token},
        follow_redirects=False,
    )
    assert reject_response.status_code == 303

    with session_factory() as session:
        draft = session.get(AiDraft, draft_id)
        published = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.source == MessageSource.AI_DRAFT_PUBLISHED.value,
            )
        )
        ticket_db = session.get(Ticket, ticket.id)
        assert draft is not None
        assert draft.status == AiDraftStatus.REJECTED.value
        assert published is None
        assert ticket_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value

```
# End of file: tests/test_ops_app.py

# File: tests/conftest.py
```python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

```
# End of file: tests/conftest.py

# File: tests/test_requester_app.py
```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient
from PIL import Image
import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.main import create_app
from shared.config import Settings
from shared.models import (
    AiRun,
    AttachmentVisibility,
    Base,
    SessionRecord,
    Ticket,
    TicketAttachment,
    TicketMessage,
    TicketStatus,
    TicketView,
    User,
    UserRole,
)
from shared.security import SESSION_COOKIE_NAME, hash_password, hash_token
from shared.tickets import add_public_reply


def make_png_bytes(color: str = "red") -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (8, 8), color=color)
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_settings(database_url: str, uploads_dir: Path) -> Settings:
    return Settings.from_env(
        {
            "APP_BASE_URL": "http://testserver",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": database_url,
            "CODEX_API_KEY": "codex-secret",
            "UPLOADS_DIR": str(uploads_dir),
        }
    )


def login(client: TestClient, email: str, password: str, remember_me: bool = False):
    response = client.get("/login")
    csrf_token = response.cookies.get("triage_login_csrf")
    data = {
        "email": email,
        "password": password,
        "csrf_token": csrf_token,
    }
    if remember_me:
        data["remember_me"] = "on"
    return client.post("/login", data=data, follow_redirects=False)


def build_client():
    temp_dir = Path(tempfile.mkdtemp(prefix="triage-stage1-test-"))
    db_path = temp_dir / "test.db"
    uploads_dir = temp_dir / "uploads"
    engine = sa.create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    settings = make_settings(f"sqlite+pysqlite:///{db_path}", uploads_dir)
    app = create_app(settings=settings, session_factory=session_factory)
    client = TestClient(app)
    return client, session_factory, uploads_dir


def seed_user(session_factory: sessionmaker[Session], *, email: str, role: str = "requester") -> User:
    with session_factory() as session:
        user = User(
            email=email,
            display_name=email.split("@", 1)[0],
            password_hash=hash_password("password123"),
            role=role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def test_login_creates_server_side_session_with_opaque_cookie() -> None:
    client, session_factory, _ = build_client()
    user = seed_user(session_factory, email="requester@example.com")

    response = login(client, user.email, "password123", remember_me=True)

    assert response.status_code == 303
    raw_token = response.cookies.get(SESSION_COOKIE_NAME)
    assert raw_token

    with session_factory() as session:
        record = session.scalar(sa.select(SessionRecord))
        assert record is not None
        assert record.user_id == user.id
        assert record.token_hash == hash_token(raw_token)
        assert record.csrf_token
        assert record.remember_me is True


def test_login_cookie_persistence_matches_remember_me_choice() -> None:
    client, session_factory, _ = build_client()
    user = seed_user(session_factory, email="session@example.com")
    fresh_client = TestClient(client.app)

    default_response = login(client, user.email, "password123", remember_me=False)
    remember_response = login(fresh_client, user.email, "password123", remember_me=True)

    default_cookie_headers = ",".join(default_response.headers.get_list("set-cookie"))
    remember_cookie_headers = ",".join(remember_response.headers.get_list("set-cookie"))

    assert "triage_session=" in default_cookie_headers
    assert "Max-Age=2592000" not in default_cookie_headers
    assert "triage_session=" in remember_cookie_headers
    assert "Max-Age=2592000" in remember_cookie_headers

    with session_factory() as session:
        records = session.scalars(sa.select(SessionRecord).order_by(SessionRecord.created_at.asc())).all()
        assert len(records) == 2
        assert records[0].remember_me is False
        assert records[1].remember_me is True
        default_duration = records[0].expires_at - records[0].created_at
        remember_duration = records[1].expires_at - records[1].created_at
        assert timedelta(hours=11) <= default_duration <= timedelta(hours=13)
        assert timedelta(days=29) <= remember_duration <= timedelta(days=31)


def test_expired_session_redirects_requester_back_to_login() -> None:
    client, session_factory, _ = build_client()
    user = seed_user(session_factory, email="expired@example.com")
    assert login(client, user.email, "password123").status_code == 303

    with session_factory() as session:
        record = session.scalar(sa.select(SessionRecord))
        assert record is not None
        record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()

    response = client.get("/app", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_requester_can_create_ticket_with_attachment_and_view_it() -> None:
    client, session_factory, uploads_dir = build_client()
    user = seed_user(session_factory, email="creator@example.com")

    login_response = login(client, user.email, "password123")
    assert login_response.status_code == 303

    ticket_form = client.get("/app/tickets/new")
    csrf_token = ticket_form.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    response = client.post(
        "/app/tickets",
        data={
            "csrf_token": csrf_token,
            "title": "",
            "description": "The dashboard is blank after I sign in.",
            "urgent": "on",
        },
        files=[
            ("attachments", ("screenshot.png", make_png_bytes(), "image/png")),
        ],
        follow_redirects=False,
    )

    assert response.status_code == 303
    detail_url = response.headers["location"]
    detail_response = client.get(detail_url)
    assert detail_response.status_code == 200
    assert "The dashboard is blank after I sign in." in detail_response.text
    assert "Updated" not in detail_response.text

    with session_factory() as session:
        ticket = session.scalar(sa.select(Ticket))
        assert ticket is not None
        assert ticket.title == "The dashboard is blank after I sign in."
        assert ticket.urgent is True

        run = session.scalar(sa.select(AiRun))
        assert run is not None
        assert run.triggered_by == "new_ticket"

        attachment = session.scalar(sa.select(TicketAttachment))
        assert attachment is not None
        assert Path(attachment.stored_path).exists()
        assert str(uploads_dir) in attachment.stored_path


def test_requester_reply_on_resolved_ticket_sets_reopen_requeue_when_run_active() -> None:
    client, session_factory, _ = build_client()
    user = seed_user(session_factory, email="reply@example.com")
    assert login(client, user.email, "password123").status_code == 303

    new_page = client.get("/app/tickets/new")
    csrf_token = new_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    create_response = client.post(
        "/app/tickets",
        data={
            "csrf_token": csrf_token,
            "description": "Initial ticket body.",
        },
        follow_redirects=False,
    )
    detail_url = create_response.headers["location"]

    detail_page = client.get(detail_url)
    detail_csrf = detail_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    resolve_response = client.post(
        f"{detail_url}/resolve",
        data={"csrf_token": detail_csrf},
        follow_redirects=False,
    )
    assert resolve_response.status_code == 303

    reopened_page = client.get(detail_url)
    reply_csrf = reopened_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    reply_response = client.post(
        f"{detail_url}/reply",
        data={
            "csrf_token": reply_csrf,
            "body": "Here is more context.",
        },
        follow_redirects=False,
    )
    assert reply_response.status_code == 303

    with session_factory() as session:
        ticket = session.scalar(sa.select(Ticket))
        assert ticket is not None
        assert ticket.status == "ai_triage"
        assert ticket.requeue_requested is True
        assert ticket.requeue_trigger == "reopen"


def test_requester_cannot_access_another_users_ticket_or_attachment() -> None:
    client, session_factory, _ = build_client()
    owner = seed_user(session_factory, email="owner@example.com")
    other = seed_user(session_factory, email="other@example.com")

    assert login(client, owner.email, "password123").status_code == 303
    new_page = client.get("/app/tickets/new")
    csrf_token = new_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    create_response = client.post(
        "/app/tickets",
        data={
            "csrf_token": csrf_token,
            "description": "Ticket only the owner should see.",
        },
        files=[("attachments", ("owner.png", make_png_bytes("blue"), "image/png"))],
        follow_redirects=False,
    )
    detail_url = create_response.headers["location"]

    with session_factory() as session:
        attachment = session.scalar(sa.select(TicketAttachment))
        assert attachment is not None
        attachment_id = str(attachment.id)

    client.post("/logout", data={"csrf_token": client.get(detail_url).text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]})
    assert login(client, other.email, "password123").status_code == 303

    assert client.get(detail_url).status_code == 404
    assert client.get(f"/attachments/{attachment_id}").status_code == 404


def test_requester_list_marks_ticket_updated_until_ticket_is_opened() -> None:
    client, session_factory, _ = build_client()
    requester = seed_user(session_factory, email="updates@example.com")
    ops_user = seed_user(session_factory, email="ops-updates@example.com", role=UserRole.DEV_TI.value)

    assert login(client, requester.email, "password123").status_code == 303
    new_page = client.get("/app/tickets/new")
    csrf_token = new_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    create_response = client.post(
        "/app/tickets",
        data={
            "csrf_token": csrf_token,
            "description": "Show me unread marker behavior.",
        },
        follow_redirects=False,
    )
    detail_url = create_response.headers["location"]

    list_response = client.get("/app/tickets")
    assert "Updated" not in list_response.text

    with session_factory() as session:
        ticket = session.scalar(sa.select(Ticket))
        ticket_view = session.scalar(sa.select(TicketView))
        ops_db = session.get(User, ops_user.id)
        assert ticket is not None
        assert ticket_view is not None
        assert ops_db is not None
        seen_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        ticket_view.last_viewed_at = seen_at
        add_public_reply(
            session,
            ticket=ticket,
            actor=ops_db,
            body_markdown="We need one more screenshot.",
            body_text="We need one more screenshot.",
            next_status=TicketStatus.WAITING_ON_USER,
            created_at=seen_at + timedelta(minutes=5),
        )
        session.commit()

    updated_list_response = client.get("/app/tickets")
    assert updated_list_response.status_code == 200
    assert "Updated" in updated_list_response.text

    detail_response = client.get(detail_url)
    assert detail_response.status_code == 200
    assert "We need one more screenshot." in detail_response.text

    cleared_list_response = client.get("/app/tickets")
    assert cleared_list_response.status_code == 200
    assert "Updated" not in cleared_list_response.text


def test_invalid_attachment_type_is_rejected() -> None:
    client, session_factory, _ = build_client()
    user = seed_user(session_factory, email="upload@example.com")
    assert login(client, user.email, "password123").status_code == 303

    new_page = client.get("/app/tickets/new")
    csrf_token = new_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    response = client.post(
        "/app/tickets",
        data={
            "csrf_token": csrf_token,
            "description": "Ticket with invalid attachment.",
        },
        files=[("attachments", ("notes.txt", b"plain text", "text/plain"))],
    )

    assert response.status_code == 400
    assert "Only PNG and JPEG images are allowed." in response.text


def test_requester_detail_only_shows_public_attachments() -> None:
    client, session_factory, uploads_dir = build_client()
    user = seed_user(session_factory, email="visibility@example.com")
    assert login(client, user.email, "password123").status_code == 303

    new_page = client.get("/app/tickets/new")
    csrf_token = new_page.text.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]
    create_response = client.post(
        "/app/tickets",
        data={
            "csrf_token": csrf_token,
            "description": "Ticket with one public and one internal attachment row.",
        },
        files=[("attachments", ("public.png", make_png_bytes("green"), "image/png"))],
        follow_redirects=False,
    )
    detail_url = create_response.headers["location"]

    with session_factory() as session:
        ticket = session.scalar(sa.select(Ticket))
        message = session.scalar(sa.select(TicketMessage))
        assert ticket is not None
        assert message is not None
        internal_path = uploads_dir / str(ticket.id) / str(message.id) / "internal-note.png"
        internal_path.parent.mkdir(parents=True, exist_ok=True)
        internal_path.write_bytes(make_png_bytes("black"))
        session.add(
            TicketAttachment(
                ticket_id=ticket.id,
                message_id=message.id,
                visibility=AttachmentVisibility.INTERNAL.value,
                original_filename="internal-note.png",
                stored_path=str(internal_path),
                mime_type="image/png",
                sha256="deadbeef",
                size_bytes=internal_path.stat().st_size,
                width=8,
                height=8,
            )
        )
        session.commit()

    detail_response = client.get(detail_url)

    assert detail_response.status_code == 200
    assert "public.png" in detail_response.text
    assert "internal-note.png" not in detail_response.text

```
# End of file: tests/test_requester_app.py

# File: tests/test_worker_phase4.py
```python
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.render import markdown_to_plain_text
from shared.config import Settings
from shared.models import (
    AiDraft,
    AiDraftStatus,
    AiRun,
    AiRunStatus,
    AttachmentVisibility,
    Base,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    Ticket,
    TicketAttachment,
    TicketMessage,
    TicketStatus,
    User,
    UserRole,
)
from shared.tickets import (
    add_requester_reply,
    create_pending_ai_run,
    create_requester_ticket,
    create_ticket_message,
)
from worker.codex_runner import CodexExecutionError, CodexRunResult, EXACT_AGENTS_MD, EXACT_SKILL_MD
from worker.main import claim_next_run, finish_prepared_run, process_next_run
from worker.ticket_loader import compute_publication_fingerprint, load_ticket_run_context


def make_settings(database_url: str, workspace_dir: Path, uploads_dir: Path) -> Settings:
    return Settings.from_env(
        {
            "APP_BASE_URL": "http://testserver",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": database_url,
            "CODEX_API_KEY": "codex-secret",
            "TRIAGE_WORKSPACE_DIR": str(workspace_dir),
            "REPO_MOUNT_DIR": str(workspace_dir / "app"),
            "MANUALS_MOUNT_DIR": str(workspace_dir / "manuals"),
            "UPLOADS_DIR": str(uploads_dir),
            "CODEX_BIN": "/bin/echo",
        }
    )


def build_session_factory():
    temp_dir = Path(tempfile.mkdtemp(prefix="triage-stage1-worker-test-"))
    db_path = temp_dir / "test.db"
    workspace_dir = temp_dir / "workspace"
    uploads_dir = temp_dir / "uploads"
    (workspace_dir / "app").mkdir(parents=True, exist_ok=True)
    (workspace_dir / "manuals").mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    engine = sa.create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    settings = make_settings(f"sqlite+pysqlite:///{db_path}", workspace_dir, uploads_dir)
    return session_factory, settings, temp_dir


def seed_user(session_factory: sessionmaker[Session], *, email: str, role: str) -> User:
    with session_factory() as session:
        user = User(
            email=email,
            display_name=email.split("@", 1)[0],
            password_hash="hashed",
            role=role,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def create_ticket_fixture(
    session_factory: sessionmaker[Session],
    *,
    creator: User,
    title: str,
    body: str,
    created_at: datetime | None = None,
) -> tuple[Ticket, AiRun]:
    created_at = created_at or datetime.now(timezone.utc)
    with session_factory() as session:
        creator_db = session.get(User, creator.id)
        assert creator_db is not None
        ticket, _, run = create_requester_ticket(
            session,
            creator=creator_db,
            title=title,
            description_markdown=body,
            description_text=body,
            urgent=False,
            created_at=created_at,
        )
        session.commit()
        session.refresh(ticket)
        session.refresh(run)
        return ticket, run


def _success_payload(public_reply_markdown: str = "Please try the documented export flow.") -> dict[str, object]:
    return {
        "ticket_class": "support",
        "confidence": 0.96,
        "impact_level": "medium",
        "requester_language": "en",
        "summary_short": "Export guidance",
        "summary_internal": "The ticket matches a documented support workflow.",
        "development_needed": False,
        "needs_clarification": False,
        "clarifying_questions": [],
        "incorrect_or_conflicting_details": [],
        "evidence_found": True,
        "relevant_paths": [{"path": "manuals/export.md", "reason": "Contains the export steps."}],
        "recommended_next_action": "auto_public_reply",
        "auto_public_reply_allowed": True,
        "public_reply_markdown": public_reply_markdown,
        "internal_note_markdown": "Internal summary for Dev/TI.",
    }


def _clarification_payload(question: str = "Which export screen are you using?") -> dict[str, object]:
    return {
        "ticket_class": "unknown",
        "confidence": 0.62,
        "impact_level": "unknown",
        "requester_language": "en",
        "summary_short": "Need clarification",
        "summary_internal": "The request is ambiguous.",
        "development_needed": False,
        "needs_clarification": True,
        "clarifying_questions": [question],
        "incorrect_or_conflicting_details": [],
        "evidence_found": False,
        "relevant_paths": [],
        "recommended_next_action": "ask_clarification",
        "auto_public_reply_allowed": False,
        "public_reply_markdown": question,
        "internal_note_markdown": "Internal ambiguity summary.",
    }


def _draft_payload(public_reply_markdown: str = "Please review this draft reply.") -> dict[str, object]:
    return {
        "ticket_class": "bug",
        "confidence": 0.72,
        "impact_level": "medium",
        "requester_language": "en",
        "summary_short": "Needs review",
        "summary_internal": "The ticket needs a human-reviewed public response.",
        "development_needed": True,
        "needs_clarification": False,
        "clarifying_questions": [],
        "incorrect_or_conflicting_details": [],
        "evidence_found": True,
        "relevant_paths": [{"path": "app/import.py", "reason": "Likely related implementation path."}],
        "recommended_next_action": "draft_public_reply",
        "auto_public_reply_allowed": False,
        "public_reply_markdown": public_reply_markdown,
        "internal_note_markdown": "Internal summary for reviewer approval.",
    }


def test_worker_success_writes_workspace_artifacts_and_publishes_once(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="requester@example.com", role=UserRole.REQUESTER.value)
    ticket, _run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Need export help",
        body="I cannot find the export button.",
        created_at=datetime(2026, 3, 20, 9, tzinfo=timezone.utc),
    )

    attachment_path = settings.uploads_dir / "evidence.png"
    attachment_path.write_bytes(b"png")
    with session_factory() as session:
        initial_message = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.source == MessageSource.TICKET_CREATE.value,
            )
        )
        assert initial_message is not None
        session.add(
            TicketAttachment(
                ticket_id=ticket.id,
                message_id=initial_message.id,
                visibility=AttachmentVisibility.PUBLIC.value,
                original_filename="evidence.png",
                stored_path=str(attachment_path),
                mime_type="image/png",
                sha256="abc123",
                size_bytes=3,
                width=1,
                height=1,
            )
        )
        session.commit()

    execution = claim_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 10, tzinfo=timezone.utc),
    )
    assert execution is not None
    command = execution.prepared_run.command
    assert "--sandbox" in command
    assert "read-only" in command
    assert "--ask-for-approval" in command
    assert "never" in command
    assert "--json" in command
    assert "--output-schema" in command
    assert "--output-last-message" in command
    assert "--image" in command
    assert 'web_search="disabled"' in command
    assert execution.prepared_run.prompt_path.read_text(encoding="utf-8").startswith("$stage1-triage")
    assert (settings.triage_workspace_dir / "AGENTS.md").read_text(encoding="utf-8") == EXACT_AGENTS_MD
    assert (
        settings.triage_workspace_dir / ".agents" / "skills" / "stage1-triage" / "SKILL.md"
    ).read_text(encoding="utf-8") == EXACT_SKILL_MD

    payload = _success_payload()

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout='{"event":"done"}\n', stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = finish_prepared_run(
        session_factory,
        settings=settings,
        execution=execution,
        completed_at=datetime(2026, 3, 20, 10, 1, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value
    assert execution.prepared_run.final_output_path.exists()

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        run_db = session.get(AiRun, execution.run_id)
        ai_internal_notes = session.scalars(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.INTERNAL.value,
                TicketMessage.source == MessageSource.AI_INTERNAL_NOTE.value,
            )
        ).all()
        ai_public_messages = session.scalars(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.PUBLIC.value,
                TicketMessage.source == MessageSource.AI_AUTO_PUBLIC.value,
            )
        ).all()

        assert ticket_db is not None
        assert run_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_USER.value
        assert ticket_db.last_ai_action == "auto_public_reply"
        assert ticket_db.ticket_class == "support"
        assert ticket_db.last_processed_hash
        assert run_db.status == AiRunStatus.SUCCEEDED.value
        assert len(ai_internal_notes) == 1
        assert len(ai_public_messages) == 1
        assert ai_public_messages[0].body_text == markdown_to_plain_text(payload["public_reply_markdown"])


def test_worker_marks_run_superseded_and_enqueues_single_requeue(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="requeue@example.com", role=UserRole.REQUESTER.value)
    ticket, original_run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Intermittent export issue",
        body="The export is failing.",
        created_at=datetime(2026, 3, 20, 11, tzinfo=timezone.utc),
    )

    execution = claim_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 11, 1, tzinfo=timezone.utc),
    )
    assert execution is not None

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        requester_db = session.get(User, requester.id)
        assert ticket_db is not None
        assert requester_db is not None
        add_requester_reply(
            session,
            ticket=ticket_db,
            requester=requester_db,
            body_markdown="More detail: it fails only for large files.",
            body_text="More detail: it fails only for large files.",
            created_at=datetime(2026, 3, 20, 11, 2, tzinfo=timezone.utc),
        )
        session.commit()

    payload = _success_payload()

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = finish_prepared_run(
        session_factory,
        settings=settings,
        execution=execution,
        completed_at=datetime(2026, 3, 20, 11, 3, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUPERSEDED.value

    with session_factory() as session:
        original_run_db = session.get(AiRun, original_run.id)
        queued_runs = session.scalars(
            sa.select(AiRun)
            .where(AiRun.ticket_id == ticket.id)
            .order_by(AiRun.created_at.asc(), AiRun.id.asc())
        ).all()
        ai_messages = session.scalars(
            sa.select(TicketMessage).where(TicketMessage.ai_run_id == original_run.id)
        ).all()
        ticket_db = session.get(Ticket, ticket.id)

        assert original_run_db is not None
        assert ticket_db is not None
        assert original_run_db.status == AiRunStatus.SUPERSEDED.value
        assert len(queued_runs) == 2
        assert queued_runs[-1].status == AiRunStatus.PENDING.value
        assert queued_runs[-1].triggered_by == "requester_reply"
        assert ticket_db.requeue_requested is False
        assert ticket_db.requeue_trigger is None
        assert ai_messages == []


def test_worker_disables_automatic_publication_when_internal_notes_exist(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="leak@example.com", role=UserRole.REQUESTER.value)
    ticket, _run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Need help",
        body="I need help with the import flow.",
        created_at=datetime(2026, 3, 20, 11, 30, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.DEV_TI,
            visibility=MessageVisibility.INTERNAL,
            source=MessageSource.HUMAN_INTERNAL_NOTE,
            body_markdown="Reset the finance export entitlement for this requester before replying.",
            body_text="Reset the finance export entitlement for this requester before replying.",
        )
        session.commit()

    payload = _success_payload(public_reply_markdown="Please retry now.")

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 11, 31, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 11, 32, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        public_message = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.PUBLIC.value,
                TicketMessage.source == MessageSource.AI_AUTO_PUBLIC.value,
            )
        )
        pending_draft = session.scalar(
            sa.select(AiDraft).where(
                AiDraft.ticket_id == ticket.id,
                AiDraft.status == AiDraftStatus.PENDING_APPROVAL.value,
            )
        )
        assert ticket_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value
        assert ticket_db.last_ai_action == "draft_public_reply"
        assert public_message is None
        assert pending_draft is not None


def test_worker_routes_to_dev_ti_instead_of_asking_clarification_when_internal_notes_exist(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="clarify@example.com", role=UserRole.REQUESTER.value)
    ticket, _run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Unsure which screen",
        body="The export is not working.",
        created_at=datetime(2026, 3, 20, 11, 45, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.DEV_TI,
            visibility=MessageVisibility.INTERNAL,
            source=MessageSource.HUMAN_INTERNAL_NOTE,
            body_markdown="Ops already suspects the legacy export screen is involved.",
            body_text="Ops already suspects the legacy export screen is involved.",
        )
        session.commit()

    payload = _clarification_payload()

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 11, 46, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 11, 47, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        public_message = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.PUBLIC.value,
                TicketMessage.source == MessageSource.AI_AUTO_PUBLIC.value,
            )
        )
        assert ticket_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value
        assert ticket_db.last_ai_action == "route_dev_ti"
        assert public_message is None


def test_worker_skips_non_manual_run_when_fingerprint_matches_last_processed_hash() -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="skip@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Repeatable request",
        body="Please help with the same issue.",
        created_at=datetime(2026, 3, 20, 12, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        context = load_ticket_run_context(session, ticket_id=ticket.id)
        ticket_db = session.get(Ticket, ticket.id)
        assert ticket_db is not None
        ticket_db.last_processed_hash = compute_publication_fingerprint(context)
        session.commit()

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 12, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 12, 1, tzinfo=timezone.utc),
    )
    assert status is None

    with session_factory() as session:
        run_db = session.get(AiRun, run.id)
        ai_messages = session.scalars(
            sa.select(TicketMessage).where(TicketMessage.ticket_id == ticket.id, TicketMessage.ai_run_id == run.id)
        ).all()
        assert run_db is not None
        assert run_db.status == AiRunStatus.SKIPPED.value
        assert ai_messages == []


def test_worker_processes_manual_rerun_even_when_fingerprint_matches_last_processed_hash(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="manual@example.com", role=UserRole.REQUESTER.value)
    ops_user = seed_user(session_factory, email="ops-manual@example.com", role=UserRole.DEV_TI.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Manual rerun request",
        body="Please retry triage.",
        created_at=datetime(2026, 3, 20, 12, 30, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        ops_db = session.get(User, ops_user.id)
        run_db = session.get(AiRun, run.id)
        assert ticket_db is not None
        assert ops_db is not None
        assert run_db is not None
        context = load_ticket_run_context(session, ticket_id=ticket.id)
        ticket_db.last_processed_hash = compute_publication_fingerprint(context)
        run_db.status = AiRunStatus.SUCCEEDED.value
        run_db.ended_at = datetime(2026, 3, 20, 12, 31, tzinfo=timezone.utc)
        session.flush()
        create_pending_ai_run(
            session,
            ticket_id=ticket.id,
            triggered_by="manual_rerun",
            requested_by_user_id=ops_db.id,
            created_at=datetime(2026, 3, 20, 12, 32, tzinfo=timezone.utc),
        )
        session.commit()

    payload = _success_payload(public_reply_markdown="Manual rerun completed successfully.")

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 12, 33, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 12, 34, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value

    with session_factory() as session:
        runs = session.scalars(
            sa.select(AiRun).where(AiRun.ticket_id == ticket.id).order_by(AiRun.created_at.asc(), AiRun.id.asc())
        ).all()
        public_messages = session.scalars(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.source == MessageSource.AI_AUTO_PUBLIC.value,
            )
        ).all()
        assert [item.status for item in runs] == [AiRunStatus.SUCCEEDED.value, AiRunStatus.SUCCEEDED.value]
        assert runs[-1].triggered_by == "manual_rerun"
        assert len(public_messages) == 1


def test_worker_new_draft_supersedes_older_pending_draft(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="drafts@example.com", role=UserRole.REQUESTER.value)
    ticket, current_run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Draft supersede",
        body="Need a reviewed reply.",
        created_at=datetime(2026, 3, 20, 12, 45, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        current_run_db = session.get(AiRun, current_run.id)
        assert current_run_db is not None
        historical_run = AiRun(
            ticket_id=ticket.id,
            status=AiRunStatus.SUCCEEDED.value,
            triggered_by="new_ticket",
            requested_by_user_id=requester.id,
            created_at=datetime(2026, 3, 20, 12, 44, tzinfo=timezone.utc),
            ended_at=datetime(2026, 3, 20, 12, 44, tzinfo=timezone.utc),
        )
        session.add(historical_run)
        session.flush()
        session.add(
            AiDraft(
                ticket_id=ticket.id,
                ai_run_id=historical_run.id,
                kind="public_reply",
                body_markdown="Older pending draft.",
                body_text="Older pending draft.",
                status=AiDraftStatus.PENDING_APPROVAL.value,
                created_at=datetime(2026, 3, 20, 12, 44, tzinfo=timezone.utc),
            )
        )
        session.commit()

    payload = _draft_payload(public_reply_markdown="New draft awaiting review.")

    def fake_run_codex(prepared_run, *, settings):
        prepared_run.final_output_path.write_text(json.dumps(payload), encoding="utf-8")
        return CodexRunResult(payload=payload, stdout="", stderr="")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 12, 46, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 12, 47, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.SUCCEEDED.value

    with session_factory() as session:
        drafts = session.scalars(
            sa.select(AiDraft).where(AiDraft.ticket_id == ticket.id).order_by(AiDraft.created_at.asc(), AiDraft.id.asc())
        ).all()
        assert len(drafts) == 2
        assert drafts[0].status == AiDraftStatus.SUPERSEDED.value
        assert drafts[1].status == AiDraftStatus.PENDING_APPROVAL.value
        assert drafts[1].body_text == "New draft awaiting review."


def test_worker_failure_routes_ticket_to_dev_ti_and_adds_internal_failure_note(monkeypatch) -> None:
    session_factory, settings, _ = build_session_factory()
    requester = seed_user(session_factory, email="failure@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Broken triage",
        body="This should fail.",
        created_at=datetime(2026, 3, 20, 13, tzinfo=timezone.utc),
    )

    def fake_run_codex(_prepared_run, *, settings):
        raise CodexExecutionError("Codex exited with status 2")

    monkeypatch.setattr("worker.main.run_codex", fake_run_codex)

    status = process_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 13, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 3, 20, 13, 2, tzinfo=timezone.utc),
    )
    assert status == AiRunStatus.FAILED.value

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        run_db = session.get(AiRun, run.id)
        failure_note = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.visibility == MessageVisibility.INTERNAL.value,
                TicketMessage.source == MessageSource.SYSTEM.value,
            )
        )
        assert ticket_db is not None
        assert run_db is not None
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value
        assert run_db.status == AiRunStatus.FAILED.value
        assert run_db.error_text == "Codex exited with status 2"
        assert failure_note is not None

```
# End of file: tests/test_worker_phase4.py

# File: tests/test_phase5_operability.py
```python
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from scripts import bootstrap_workspace as bootstrap_workspace_script
from scripts import create_admin as create_admin_script
from scripts import create_user as create_user_script
from scripts import deactivate_user as deactivate_user_script
from scripts import run_web as run_web_script
from scripts import run_worker as run_worker_script
from scripts import set_password as set_password_script
from shared.bootstrap import bootstrap_workspace
from shared.config import Settings
from shared.models import Base, SystemState, User, UserRole
from shared.security import verify_password
from worker.main import run_worker_loop


def build_runtime(tmp_path: Path) -> tuple[sessionmaker, Settings]:
    db_path = tmp_path / "test.db"
    workspace_dir = tmp_path / "workspace"
    uploads_dir = tmp_path / "uploads"
    (workspace_dir / "app").mkdir(parents=True, exist_ok=True)
    (workspace_dir / "manuals").mkdir(parents=True, exist_ok=True)

    engine = sa.create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    settings = Settings.from_env(
        {
            "APP_BASE_URL": "http://testserver",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": f"sqlite+pysqlite:///{db_path}",
            "CODEX_API_KEY": "codex-secret",
            "TRIAGE_WORKSPACE_DIR": str(workspace_dir),
            "REPO_MOUNT_DIR": str(workspace_dir / "app"),
            "MANUALS_MOUNT_DIR": str(workspace_dir / "manuals"),
            "UPLOADS_DIR": str(uploads_dir),
            "CODEX_BIN": "/bin/echo",
        }
    )
    return session_factory, settings


def test_bootstrap_workspace_script_creates_git_artifacts_and_bootstrap_state(
    tmp_path: Path,
    capsys,
) -> None:
    session_factory, settings = build_runtime(tmp_path)

    exit_code = bootstrap_workspace_script.main(
        ["--bootstrap-version", "phase5-test"],
        settings=settings,
        session_factory=session_factory,
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "ok"
    assert Path(payload["workspace_dir"], ".git").exists()
    assert Path(payload["uploads_dir"]).is_dir()
    assert Path(payload["workspace_dir"], "AGENTS.md").is_file()
    assert Path(payload["workspace_dir"], ".agents", "skills", "stage1-triage", "SKILL.md").is_file()
    assert Path(payload["workspace_dir"], "runs").is_dir()

    head = subprocess.run(
        ["git", "-C", str(settings.triage_workspace_dir), "rev-parse", "--verify", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert head.returncode == 0
    assert head.stdout.strip()

    with session_factory() as session:
        bootstrap_row = session.get(SystemState, "bootstrap_version")
        assert bootstrap_row is not None
        assert bootstrap_row.value_json["version"] == "phase5-test"


def test_bootstrap_workspace_script_returns_error_when_required_mount_is_missing(
    tmp_path: Path,
    capsys,
) -> None:
    session_factory, settings = build_runtime(tmp_path)
    settings.manuals_mount_dir.rmdir()

    exit_code = bootstrap_workspace_script.main(
        [],
        settings=settings,
        session_factory=session_factory,
    )

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "error"
    assert "manuals mount is missing" in payload["error"]


def test_user_management_scripts_create_reset_and_deactivate_accounts(
    tmp_path: Path,
    capsys,
) -> None:
    session_factory, settings = build_runtime(tmp_path)

    assert (
        create_admin_script.main(
            [
                "--email",
                "Admin@Example.com",
                "--display-name",
                "Admin User",
                "--password",
                "secret-1",
            ],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )
    assert (
        create_user_script.main(
            [
                "--email",
                "requester@example.com",
                "--display-name",
                "Requester User",
                "--password",
                "secret-2",
                "--role",
                "requester",
            ],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )
    assert (
        set_password_script.main(
            ["--email", "requester@example.com", "--password", "changed-password"],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )
    assert (
        deactivate_user_script.main(
            ["--email", "requester@example.com"],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )

    with session_factory() as session:
        admin_user = session.scalar(sa.select(User).where(User.email == "admin@example.com"))
        requester_user = session.scalar(sa.select(User).where(User.email == "requester@example.com"))
        assert admin_user is not None
        assert requester_user is not None
        assert admin_user.role == UserRole.ADMIN.value
        assert verify_password(requester_user.password_hash, "changed-password")
        assert requester_user.is_active is False

    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert [line["status"] for line in lines] == ["ok", "ok", "ok", "ok"]


def test_user_management_scripts_report_duplicate_and_missing_user_errors(
    tmp_path: Path,
    capsys,
) -> None:
    session_factory, settings = build_runtime(tmp_path)

    assert (
        create_user_script.main(
            [
                "--email",
                "requester@example.com",
                "--display-name",
                "Requester User",
                "--password",
                "secret-2",
                "--role",
                "requester",
            ],
            settings=settings,
            session_factory=session_factory,
        )
        == 0
    )
    assert (
        create_user_script.main(
            [
                "--email",
                "requester@example.com",
                "--display-name",
                "Requester User",
                "--password",
                "secret-2",
                "--role",
                "requester",
            ],
            settings=settings,
            session_factory=session_factory,
        )
        == 1
    )
    assert (
        set_password_script.main(
            ["--email", "missing@example.com", "--password", "changed-password"],
            settings=settings,
            session_factory=session_factory,
        )
        == 1
    )

    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert lines[0]["status"] == "ok"
    assert lines[1] == {"status": "error", "error": "User already exists: requester@example.com"}
    assert lines[2] == {"status": "error", "error": "User not found: missing@example.com"}


def test_health_and_readiness_routes_report_bootstrap_state(tmp_path: Path) -> None:
    session_factory, settings = build_runtime(tmp_path)
    app = create_app(settings=settings, session_factory=session_factory)
    client = TestClient(app)

    health_response = client.get("/healthz")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}

    readiness_before = client.get("/readyz")
    assert readiness_before.status_code == 503
    issues = readiness_before.json()["issues"]
    assert any("uploads_dir missing" in issue for issue in issues)
    assert any("agents_md missing" in issue for issue in issues)

    bootstrap_workspace(settings, session_factory=session_factory)

    readiness_after = client.get("/readyz")
    assert readiness_after.status_code == 200
    assert readiness_after.json() == {"status": "ok"}


def test_readyz_reports_database_failure(tmp_path: Path, monkeypatch) -> None:
    session_factory, settings = build_runtime(tmp_path)
    bootstrap_workspace(settings, session_factory=session_factory)
    app = create_app(settings=settings, session_factory=session_factory)
    client = TestClient(app)

    monkeypatch.setattr("app.main.check_database_readiness", lambda _factory: "db offline")
    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["issues"][0] == "database not ready: db offline"


def test_worker_once_updates_heartbeat_system_state(tmp_path: Path, monkeypatch) -> None:
    session_factory, settings = build_runtime(tmp_path)

    monkeypatch.setattr("worker.main.process_next_run", lambda *args, **kwargs: None)
    run_worker_loop(settings=settings, session_factory=session_factory, once=True)

    with session_factory() as session:
        heartbeat = session.get(SystemState, "worker_heartbeat")
        assert heartbeat is not None
        timestamp = heartbeat.value_json["timestamp"]
        assert datetime.fromisoformat(timestamp).tzinfo == timezone.utc


def test_run_web_script_passes_configured_app_to_uvicorn(tmp_path: Path, monkeypatch) -> None:
    session_factory, settings = build_runtime(tmp_path)
    captured: dict[str, object] = {}

    def fake_uvicorn_run(app, **kwargs):
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr("scripts.run_web.uvicorn.run", fake_uvicorn_run)

    exit_code = run_web_script.main(
        ["--host", "127.0.0.1", "--port", "9000"],
        settings=settings,
        session_factory=session_factory,
    )

    assert exit_code == 0
    assert captured["app"].title == "Stage 1 AI Triage MVP"
    assert captured["kwargs"] == {
        "host": "127.0.0.1",
        "port": 9000,
        "reload": False,
        "log_config": None,
        "access_log": False,
    }


def test_run_worker_script_passes_once_flag_to_worker_loop(tmp_path: Path, monkeypatch) -> None:
    session_factory, settings = build_runtime(tmp_path)
    captured: dict[str, object] = {}

    def fake_run_worker_loop(*, settings, session_factory, once):
        captured["settings"] = settings
        captured["session_factory"] = session_factory
        captured["once"] = once

    monkeypatch.setattr("scripts.run_worker.run_worker_loop", fake_run_worker_loop)

    exit_code = run_worker_script.main(
        ["--once"],
        settings=settings,
        session_factory=session_factory,
    )

    assert exit_code == 0
    assert captured["settings"] == settings
    assert captured["session_factory"] is session_factory
    assert captured["once"] is True

```
# End of file: tests/test_phase5_operability.py

# File: worker/codex_runner.py
```python
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import uuid

from shared.bootstrap import ensure_workspace_files
from shared.config import Settings
from shared.workspace_contract import EXACT_AGENTS_MD, EXACT_SKILL_MD

EXACT_SCHEMA_JSON = """{
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "ticket_class": {
      "type": "string",
      "enum": ["support", "access_config", "data_ops", "bug", "feature", "unknown"]
    },
    "confidence": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0
    },
    "impact_level": {
      "type": "string",
      "enum": ["low", "medium", "high", "unknown"]
    },
    "requester_language": {
      "type": "string",
      "minLength": 2
    },
    "summary_short": {
      "type": "string",
      "minLength": 1,
      "maxLength": 120
    },
    "summary_internal": {
      "type": "string",
      "minLength": 1
    },
    "development_needed": {
      "type": "boolean"
    },
    "needs_clarification": {
      "type": "boolean"
    },
    "clarifying_questions": {
      "type": "array",
      "maxItems": 3,
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "incorrect_or_conflicting_details": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      }
    },
    "evidence_found": {
      "type": "boolean"
    },
    "relevant_paths": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "path": { "type": "string" },
          "reason": { "type": "string" }
        },
        "required": ["path", "reason"]
      }
    },
    "recommended_next_action": {
      "type": "string",
      "enum": [
        "ask_clarification",
        "auto_public_reply",
        "auto_confirm_and_route",
        "draft_public_reply",
        "route_dev_ti"
      ]
    },
    "auto_public_reply_allowed": {
      "type": "boolean"
    },
    "public_reply_markdown": {
      "type": "string"
    },
    "internal_note_markdown": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "ticket_class",
    "confidence",
    "impact_level",
    "requester_language",
    "summary_short",
    "summary_internal",
    "development_needed",
    "needs_clarification",
    "clarifying_questions",
    "incorrect_or_conflicting_details",
    "evidence_found",
    "relevant_paths",
    "recommended_next_action",
    "auto_public_reply_allowed",
    "public_reply_markdown",
    "internal_note_markdown"
  ]
}
"""


class CodexExecutionError(RuntimeError):
    """Raised when the Codex CLI execution fails or returns invalid artifacts."""


@dataclass(frozen=True)
class CodexPreparedRun:
    run_dir: Path
    prompt_path: Path
    schema_path: Path
    final_output_path: Path
    stdout_jsonl_path: Path
    stderr_path: Path
    command: tuple[str, ...]


@dataclass(frozen=True)
class CodexRunResult:
    payload: dict[str, object]
    stdout: str
    stderr: str
def _format_messages(messages: list[dict[str, str]]) -> str:
    if not messages:
        return "(none)"
    blocks: list[str] = []
    for index, message in enumerate(messages, start=1):
        blocks.append(
            "\n".join(
                [
                    f"[{index}] author_type: {message['author_type']}",
                    f"source: {message['source']}",
                    "body:",
                    message["body_markdown"] or message["body_text"] or "(empty)",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_prompt(
    *,
    reference: str,
    title: str,
    status: str,
    urgent: bool,
    public_messages: list[dict[str, str]],
    internal_messages: list[dict[str, str]],
) -> str:
    return f"""$stage1-triage

Task:
Analyze this internal ticket for Stage 1 triage only.

Constraints:
- Use only the ticket title, ticket messages, attached images, files under manuals/, and files under app/.
- Search manuals/ first when support, access, or operations guidance may exist.
- Inspect app/ when repository understanding is needed.
- Do not use databases, logs, DDL, schema dumps, or external web search.
- Return only valid JSON matching the provided schema.
- Ask at most 3 clarifying questions.
- Never promise a fix, implementation, or timeline.
- Internal messages may inform internal analysis and routing but MUST NOT be disclosed in automatic public replies unless the same information is already public on the ticket.

Ticket reference:
{reference}

Ticket title:
{title}

Current status:
{status}

Urgent:
{str(urgent)}

Public messages:
{_format_messages(public_messages)}

Internal messages:
{_format_messages(internal_messages)}

Decision policy:
- Classify into exactly one of: support, access_config, data_ops, bug, feature, unknown.
- impact_level means business/user impact only.
- development_needed is only a triage estimate.
- Search manuals/ before answering support or access/config questions.
- Inspect app/ when repository understanding is needed.
- If the available evidence strongly supports an answer and confidence is high, you may draft a concise public reply.
- If the request is understood but should go to Dev/TI, you may draft a safe public confirmation and route it.
- If information is ambiguous, missing, conflicting, or likely incorrect, ask concise clarifying questions instead of guessing.
- If no safe public reply should be prepared, leave public_reply_markdown empty and set auto_public_reply_allowed to false.

Output:
Return only the JSON object.
"""


def prepare_codex_run(
    settings: Settings,
    *,
    ticket_id: uuid.UUID,
    run_id: uuid.UUID,
    prompt: str,
    image_paths: list[Path],
) -> CodexPreparedRun:
    ensure_workspace_files(settings)

    run_dir = settings.triage_workspace_dir / "runs" / str(ticket_id) / str(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = run_dir / "prompt.txt"
    schema_path = run_dir / "schema.json"
    final_output_path = run_dir / "final.json"
    stdout_jsonl_path = run_dir / "stdout.jsonl"
    stderr_path = run_dir / "stderr.txt"

    prompt_path.write_text(prompt, encoding="utf-8")
    schema_path.write_text(EXACT_SCHEMA_JSON, encoding="utf-8")
    if not stdout_jsonl_path.exists():
        stdout_jsonl_path.write_text("", encoding="utf-8")
    if not stderr_path.exists():
        stderr_path.write_text("", encoding="utf-8")

    command: list[str] = [
        settings.codex_bin,
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--ask-for-approval",
        "never",
        "--json",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(final_output_path),
        "-c",
        'web_search="disabled"',
    ]
    if settings.codex_model:
        command.extend(["--model", settings.codex_model])
    for image_path in image_paths:
        command.extend(["--image", str(image_path)])
    command.append(prompt)

    return CodexPreparedRun(
        run_dir=run_dir,
        prompt_path=prompt_path,
        schema_path=schema_path,
        final_output_path=final_output_path,
        stdout_jsonl_path=stdout_jsonl_path,
        stderr_path=stderr_path,
        command=tuple(command),
    )


def run_codex(prepared: CodexPreparedRun, *, settings: Settings) -> CodexRunResult:
    env = os.environ.copy()
    env["CODEX_API_KEY"] = settings.codex_api_key
    try:
        completed = subprocess.run(
            prepared.command,
            cwd=settings.triage_workspace_dir,
            env=env,
            text=True,
            capture_output=True,
            timeout=settings.codex_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        prepared.stdout_jsonl_path.write_text(stdout, encoding="utf-8")
        prepared.stderr_path.write_text(stderr, encoding="utf-8")
        raise CodexExecutionError(
            f"Codex execution timed out after {settings.codex_timeout_seconds} seconds"
        ) from exc

    prepared.stdout_jsonl_path.write_text(completed.stdout or "", encoding="utf-8")
    prepared.stderr_path.write_text(completed.stderr or "", encoding="utf-8")

    if completed.returncode != 0:
        raise CodexExecutionError(f"Codex exited with status {completed.returncode}")
    if not prepared.final_output_path.exists():
        raise CodexExecutionError("Codex did not produce the canonical final output artifact")

    try:
        payload = json.loads(prepared.final_output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CodexExecutionError("Codex final output was not valid JSON") from exc

    if not isinstance(payload, dict):
        raise CodexExecutionError("Codex final output must be a JSON object")

    return CodexRunResult(
        payload=payload,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )

```
# End of file: worker/codex_runner.py

# File: worker/main.py
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time
import uuid

from sqlalchemy.orm import Session, sessionmaker

from shared.config import Settings, get_settings
from shared.db import make_session_factory, session_scope
from shared.logging import configure_logging, log_event
from shared.models import AiRun, AiRunStatus, AiRunTrigger, SystemState, Ticket, TicketStatus
from shared.tickets import change_ticket_status
from worker.codex_runner import (
    CodexExecutionError,
    CodexPreparedRun,
    build_prompt,
    prepare_codex_run,
    run_codex,
)
from worker.queue import acquire_next_pending_run
from worker.ticket_loader import compute_publication_fingerprint, load_ticket_run_context
from worker.triage import (
    finalize_failure,
    finalize_skipped,
    finalize_success,
    finalize_superseded,
    validate_triage_payload,
)


LOGGER = logging.getLogger("triage-stage1.worker")
HEARTBEAT_KEY = "worker_heartbeat"


@dataclass(frozen=True)
class PreparedExecution:
    run_id: uuid.UUID
    ticket_id: uuid.UUID
    prepared_run: CodexPreparedRun


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _message_dicts(messages) -> list[dict[str, str]]:
    return [
        {
            "author_type": message.author_type,
            "source": message.source,
            "body_markdown": message.body_markdown,
            "body_text": message.body_text,
        }
        for message in messages
    ]


def _log(event: str, **fields: object) -> None:
    log_event(LOGGER, service="worker", event=event, **fields)


def claim_next_run(
    session_factory: sessionmaker[Session],
    *,
    settings: Settings,
    claimed_at: datetime | None = None,
) -> PreparedExecution | None:
    claimed_at = claimed_at or now_utc()
    with session_scope(session_factory) as session:
        run = acquire_next_pending_run(session)
        if run is None:
            return None

        context = load_ticket_run_context(session, ticket_id=run.ticket_id)
        ticket = context.ticket
        fingerprint_before_start = compute_publication_fingerprint(context)

        if (
            run.triggered_by != "manual_rerun"
            and ticket.last_processed_hash
            and fingerprint_before_start == ticket.last_processed_hash
        ):
            result = finalize_skipped(session, ticket=ticket, run=run, completed_at=claimed_at)
            _log(
                "ai_run_skipped",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
            )
            return None

        prompt = build_prompt(
            reference=ticket.reference,
            title=ticket.title,
            status=ticket.status,
            urgent=ticket.urgent,
            public_messages=_message_dicts(context.public_messages),
            internal_messages=_message_dicts(context.internal_messages),
        )
        prepared_run = prepare_codex_run(
            settings,
            ticket_id=ticket.id,
            run_id=run.id,
            prompt=prompt,
            image_paths=[attachment.path for attachment in context.public_attachments],
        )

        run.prompt_path = str(prepared_run.prompt_path)
        run.schema_path = str(prepared_run.schema_path)
        run.final_output_path = str(prepared_run.final_output_path)
        run.stdout_jsonl_path = str(prepared_run.stdout_jsonl_path)
        run.stderr_path = str(prepared_run.stderr_path)
        run.model_name = settings.codex_model
        run.status = AiRunStatus.RUNNING.value
        run.started_at = claimed_at
        run.error_text = None
        change_ticket_status(
            session,
            ticket,
            TicketStatus.AI_TRIAGE,
            changed_by_type="system",
            changed_at=claimed_at,
        )
        session.flush()
        run.input_hash = compute_publication_fingerprint(
            load_ticket_run_context(session, ticket_id=run.ticket_id)
        )
        _log("ai_run_started", run_id=run.id, ticket_reference=ticket.reference)
        return PreparedExecution(run_id=run.id, ticket_id=ticket.id, prepared_run=prepared_run)


def finish_prepared_run(
    session_factory: sessionmaker[Session],
    *,
    settings: Settings,
    execution: PreparedExecution,
    completed_at: datetime | None = None,
) -> str:
    completed_at = completed_at or now_utc()
    error_text: str | None = None
    payload: dict[str, object] | None = None

    try:
        result = run_codex(execution.prepared_run, settings=settings)
        payload = result.payload
    except CodexExecutionError as exc:
        error_text = str(exc)
    except Exception as exc:  # pragma: no cover - defensive worker boundary
        error_text = f"Unexpected worker error: {exc}"

    with session_scope(session_factory) as session:
        run = session.get(AiRun, execution.run_id)
        ticket = session.get(Ticket, execution.ticket_id)
        if run is None or ticket is None:
            raise LookupError("Run or ticket disappeared while finishing worker execution")

        if error_text is not None or payload is None:
            result = finalize_failure(
                session,
                ticket=ticket,
                run=run,
                error_text=error_text or "Unknown AI execution failure",
                completed_at=completed_at,
            )
            _log(
                "ai_run_failed",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
                error_text=run.error_text,
            )
            return result.run_status

        try:
            validated_output = validate_triage_payload(payload, settings=settings, ticket=ticket)
        except Exception as exc:
            result = finalize_failure(
                session,
                ticket=ticket,
                run=run,
                error_text=str(exc),
                completed_at=completed_at,
            )
            _log(
                "ai_run_failed",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
                error_text=run.error_text,
            )
            return result.run_status

        context = load_ticket_run_context(session, ticket_id=ticket.id)
        publication_fingerprint = compute_publication_fingerprint(context)
        if ticket.requeue_requested or publication_fingerprint != run.input_hash:
            if not ticket.requeue_requested:
                ticket.requeue_requested = True
                ticket.requeue_trigger = (
                    ticket.requeue_trigger or AiRunTrigger.REQUESTER_REPLY.value
                )
            result = finalize_superseded(session, ticket=ticket, run=run, completed_at=completed_at)
            _log(
                "ai_run_superseded",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
            )
            return result.run_status

        try:
            result = finalize_success(
                session,
                ticket=ticket,
                run=run,
                output=validated_output,
                internal_body_texts=[message.body_text for message in context.internal_messages],
                publication_fingerprint=publication_fingerprint,
                completed_at=completed_at,
            )
        except Exception as exc:
            result = finalize_failure(
                session,
                ticket=ticket,
                run=run,
                error_text=str(exc),
                completed_at=completed_at,
            )
            _log(
                "ai_run_failed",
                run_id=run.id,
                ticket_reference=ticket.reference,
                queued_requeue_run_id=result.queued_requeue_run_id,
                error_text=run.error_text,
            )
            return result.run_status

        _log(
            "ai_run_succeeded",
            run_id=run.id,
            ticket_reference=ticket.reference,
            action=ticket.last_ai_action,
            queued_requeue_run_id=result.queued_requeue_run_id,
        )
        return result.run_status


def process_next_run(
    session_factory: sessionmaker[Session],
    *,
    settings: Settings,
    claimed_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> str | None:
    execution = claim_next_run(session_factory, settings=settings, claimed_at=claimed_at)
    if execution is None:
        return None
    return finish_prepared_run(
        session_factory,
        settings=settings,
        execution=execution,
        completed_at=completed_at,
    )


def update_worker_heartbeat(
    session_factory: sessionmaker[Session],
    *,
    heartbeat_at: datetime | None = None,
) -> None:
    heartbeat_at = heartbeat_at or now_utc()
    with session_scope(session_factory) as session:
        row = session.get(SystemState, HEARTBEAT_KEY)
        payload = {"timestamp": heartbeat_at.isoformat()}
        if row is None:
            session.add(SystemState(key=HEARTBEAT_KEY, value_json=payload, updated_at=heartbeat_at))
        else:
            row.value_json = payload
            row.updated_at = heartbeat_at


def run_worker_loop(
    *,
    settings: Settings | None = None,
    session_factory: sessionmaker[Session] | None = None,
    once: bool = False,
) -> None:
    resolved_settings = settings or get_settings()
    resolved_session_factory = session_factory or make_session_factory(settings=resolved_settings)
    last_heartbeat_at: datetime | None = None

    while True:
        current = now_utc()
        if last_heartbeat_at is None or (current - last_heartbeat_at).total_seconds() >= 60:
            update_worker_heartbeat(resolved_session_factory, heartbeat_at=current)
            last_heartbeat_at = current

        process_next_run(resolved_session_factory, settings=resolved_settings)
        if once:
            return
        time.sleep(resolved_settings.worker_poll_seconds)


def main() -> None:
    configure_logging(service="worker")
    run_worker_loop()


if __name__ == "__main__":
    main()

```
# End of file: worker/main.py

# File: worker/queue.py
```python
from __future__ import annotations

from datetime import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from shared.models import AiRun, AiRunStatus, AiRunTrigger, Ticket, TicketRequeueTrigger
from shared.tickets import create_pending_ai_run


def acquire_next_pending_run(session: Session) -> AiRun | None:
    query = (
        sa.select(AiRun)
        .where(AiRun.status == AiRunStatus.PENDING.value)
        .order_by(AiRun.created_at.asc(), AiRun.id.asc())
    )
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    return session.scalar(query)


def _normalize_trigger(value: str | None) -> str:
    if value in {
        TicketRequeueTrigger.REQUESTER_REPLY.value,
        TicketRequeueTrigger.MANUAL_RERUN.value,
        TicketRequeueTrigger.REOPEN.value,
    }:
        return value
    return AiRunTrigger.REQUESTER_REPLY.value


def enqueue_deferred_requeue(
    session: Session,
    *,
    ticket: Ticket,
    created_at: datetime,
    requested_by_user_id: uuid.UUID | None = None,
) -> AiRun | None:
    if not ticket.requeue_requested:
        return None

    session.flush()
    active_run = session.scalar(
        sa.select(AiRun).where(
            AiRun.ticket_id == ticket.id,
            AiRun.status.in_([AiRunStatus.PENDING.value, AiRunStatus.RUNNING.value]),
        )
    )
    if active_run is not None:
        return None

    run = create_pending_ai_run(
        session,
        ticket_id=ticket.id,
        triggered_by=_normalize_trigger(ticket.requeue_trigger),
        requested_by_user_id=requested_by_user_id,
        created_at=created_at,
    )
    ticket.requeue_requested = False
    ticket.requeue_trigger = None
    return run


```
# End of file: worker/queue.py

# File: worker/__init__.py
```python
"""Worker package for later phases."""

```
# End of file: worker/__init__.py

# File: worker/triage.py
```python
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

from app.render import markdown_to_plain_text
from shared.config import Settings
from shared.models import (
    AiDraft,
    AiDraftKind,
    AiDraftStatus,
    AiRun,
    MessageAuthorType,
    MessageSource,
    MessageVisibility,
    StatusChangedByType,
    Ticket,
    TicketClass,
    TicketStatus,
)
from shared.tickets import (
    bump_ticket_updated_at,
    change_ticket_status,
    create_ticket_message,
    supersede_pending_drafts,
)
from worker.queue import enqueue_deferred_requeue


class RelevantPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    reason: str


class TriageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_class: Literal["support", "access_config", "data_ops", "bug", "feature", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)
    impact_level: Literal["low", "medium", "high", "unknown"]
    requester_language: str = Field(min_length=2)
    summary_short: str = Field(min_length=1, max_length=120)
    summary_internal: str = Field(min_length=1)
    development_needed: bool
    needs_clarification: bool
    clarifying_questions: list[str] = Field(default_factory=list, max_length=3)
    incorrect_or_conflicting_details: list[str] = Field(default_factory=list)
    evidence_found: bool
    relevant_paths: list[RelevantPath] = Field(default_factory=list)
    recommended_next_action: Literal[
        "ask_clarification",
        "auto_public_reply",
        "auto_confirm_and_route",
        "draft_public_reply",
        "route_dev_ti",
    ]
    auto_public_reply_allowed: bool
    public_reply_markdown: str = ""
    internal_note_markdown: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_action_rules(self) -> "TriageOutput":
        if (
            self.recommended_next_action == "ask_clarification"
            and (not self.needs_clarification or not self.public_reply_markdown.strip())
        ):
            raise ValueError("ask_clarification requires clarification and a public reply")
        if self.recommended_next_action == "auto_public_reply":
            if not self.auto_public_reply_allowed:
                raise ValueError("auto_public_reply requires auto_public_reply_allowed=true")
            if not self.evidence_found:
                raise ValueError("auto_public_reply requires evidence_found=true")
            if not self.public_reply_markdown.strip():
                raise ValueError("auto_public_reply requires a public reply")
            if self.ticket_class == TicketClass.UNKNOWN.value:
                raise ValueError("unknown tickets cannot auto publish")
        if self.recommended_next_action == "auto_confirm_and_route":
            if not self.auto_public_reply_allowed:
                raise ValueError("auto_confirm_and_route requires auto_public_reply_allowed=true")
            if not self.public_reply_markdown.strip():
                raise ValueError("auto_confirm_and_route requires a public reply")
        if self.recommended_next_action == "draft_public_reply":
            if self.auto_public_reply_allowed:
                raise ValueError("draft_public_reply requires auto_public_reply_allowed=false")
            if not self.public_reply_markdown.strip():
                raise ValueError("draft_public_reply requires a public reply")
        if self.recommended_next_action == "route_dev_ti" and self.public_reply_markdown is None:
            raise ValueError("route_dev_ti requires public_reply_markdown to be present")
        return self


class TriageValidationError(ValueError):
    """Raised when the AI payload violates product-level validation rules."""


@dataclass(frozen=True)
class PublicationResult:
    run_status: str
    queued_requeue_run_id: uuid.UUID | None


def guard_auto_public_reply(
    output: TriageOutput,
    *,
    internal_body_texts: list[str],
) -> TriageOutput:
    if output.recommended_next_action not in {
        "ask_clarification",
        "auto_public_reply",
        "auto_confirm_and_route",
    }:
        return output
    if not internal_body_texts:
        return output

    if output.recommended_next_action == "ask_clarification":
        return output.model_copy(
            update={
                "recommended_next_action": "route_dev_ti",
                "auto_public_reply_allowed": False,
                "public_reply_markdown": "",
            }
        )
    return output.model_copy(
        update={
            "recommended_next_action": "draft_public_reply",
            "auto_public_reply_allowed": False,
        }
    )


def validate_triage_payload(
    payload: dict[str, object],
    *,
    settings: Settings,
    ticket: Ticket,
) -> TriageOutput:
    try:
        result = TriageOutput.model_validate(payload)
    except ValidationError as exc:
        raise TriageValidationError(str(exc)) from exc

    if (
        result.recommended_next_action == "auto_public_reply"
        and result.confidence < settings.auto_support_reply_min_confidence
    ):
        raise TriageValidationError("auto_public_reply confidence is below the configured threshold")
    if (
        result.recommended_next_action == "auto_confirm_and_route"
        and result.confidence < settings.auto_confirm_intent_min_confidence
    ):
        raise TriageValidationError(
            "auto_confirm_and_route confidence is below the configured threshold"
        )
    if (
        result.recommended_next_action == "ask_clarification"
        and ticket.clarification_rounds >= 2
    ):
        raise TriageValidationError("clarification limit already reached for this ticket")
    return result


def apply_ticket_classification(ticket: Ticket, output: TriageOutput) -> None:
    ticket.ticket_class = output.ticket_class
    ticket.ai_confidence = Decimal(str(output.confidence)).quantize(
        Decimal("0.001"),
        rounding=ROUND_HALF_UP,
    )
    ticket.impact_level = output.impact_level
    ticket.development_needed = output.development_needed
    ticket.requester_language = output.requester_language


def publish_internal_ai_note(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    output: TriageOutput,
    created_at,
) -> None:
    create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=None,
        author_type=MessageAuthorType.AI,
        visibility=MessageVisibility.INTERNAL,
        source=MessageSource.AI_INTERNAL_NOTE,
        body_markdown=output.internal_note_markdown,
        body_text=markdown_to_plain_text(output.internal_note_markdown),
        ai_run_id=run.id,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)


def publish_failure_note(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    error_text: str,
    created_at,
) -> None:
    body_markdown = (
        "AI triage failed for this run.\n\n"
        f"- Run ID: `{run.id}`\n"
        f"- Error: {error_text}"
    )
    create_ticket_message(
        session,
        ticket_id=ticket.id,
        author_user_id=None,
        author_type=MessageAuthorType.SYSTEM,
        visibility=MessageVisibility.INTERNAL,
        source=MessageSource.SYSTEM,
        body_markdown=body_markdown,
        body_text=markdown_to_plain_text(body_markdown),
        ai_run_id=run.id,
        created_at=created_at,
    )
    bump_ticket_updated_at(ticket, created_at)


def apply_ai_action(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    output: TriageOutput,
    acted_at,
) -> None:
    public_body_text = markdown_to_plain_text(output.public_reply_markdown)

    if output.recommended_next_action == "ask_clarification":
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.AI,
            visibility=MessageVisibility.PUBLIC,
            source=MessageSource.AI_AUTO_PUBLIC,
            body_markdown=output.public_reply_markdown,
            body_text=public_body_text,
            ai_run_id=run.id,
            created_at=acted_at,
        )
        ticket.clarification_rounds += 1
        bump_ticket_updated_at(ticket, acted_at)
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_USER,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    elif output.recommended_next_action == "auto_public_reply":
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.AI,
            visibility=MessageVisibility.PUBLIC,
            source=MessageSource.AI_AUTO_PUBLIC,
            body_markdown=output.public_reply_markdown,
            body_text=public_body_text,
            ai_run_id=run.id,
            created_at=acted_at,
        )
        bump_ticket_updated_at(ticket, acted_at)
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_USER,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    elif output.recommended_next_action == "auto_confirm_and_route":
        create_ticket_message(
            session,
            ticket_id=ticket.id,
            author_user_id=None,
            author_type=MessageAuthorType.AI,
            visibility=MessageVisibility.PUBLIC,
            source=MessageSource.AI_AUTO_PUBLIC,
            body_markdown=output.public_reply_markdown,
            body_text=public_body_text,
            ai_run_id=run.id,
            created_at=acted_at,
        )
        bump_ticket_updated_at(ticket, acted_at)
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_DEV_TI,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    elif output.recommended_next_action == "draft_public_reply":
        draft = AiDraft(
            ticket_id=ticket.id,
            ai_run_id=run.id,
            kind=AiDraftKind.PUBLIC_REPLY.value,
            body_markdown=output.public_reply_markdown,
            body_text=public_body_text,
            status=AiDraftStatus.PENDING_APPROVAL.value,
            created_at=acted_at,
        )
        session.add(draft)
        session.flush()
        supersede_pending_drafts(session, ticket_id=ticket.id, keep_draft_id=draft.id)
        bump_ticket_updated_at(ticket, acted_at)
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_DEV_TI,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    elif output.recommended_next_action == "route_dev_ti":
        change_ticket_status(
            session,
            ticket,
            TicketStatus.WAITING_ON_DEV_TI,
            changed_by_type=StatusChangedByType.AI,
            changed_at=acted_at,
        )
    else:
        raise TriageValidationError(f"Unsupported action: {output.recommended_next_action}")

    ticket.last_ai_action = output.recommended_next_action


def finalize_success(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    output: TriageOutput,
    internal_body_texts: list[str],
    publication_fingerprint: str,
    completed_at,
) -> PublicationResult:
    guarded_output = guard_auto_public_reply(
        output,
        internal_body_texts=internal_body_texts,
    )
    apply_ticket_classification(ticket, guarded_output)
    publish_internal_ai_note(
        session,
        ticket=ticket,
        run=run,
        output=guarded_output,
        created_at=completed_at,
    )
    apply_ai_action(session, ticket=ticket, run=run, output=guarded_output, acted_at=completed_at)
    ticket.last_processed_hash = publication_fingerprint
    run.status = "succeeded"
    run.ended_at = completed_at
    session.flush()
    requeue_run = enqueue_deferred_requeue(session, ticket=ticket, created_at=completed_at)
    return PublicationResult(run_status=run.status, queued_requeue_run_id=getattr(requeue_run, "id", None))


def finalize_failure(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    error_text: str,
    completed_at,
) -> PublicationResult:
    publish_failure_note(session, ticket=ticket, run=run, error_text=error_text, created_at=completed_at)
    change_ticket_status(
        session,
        ticket,
        TicketStatus.WAITING_ON_DEV_TI,
        changed_by_type=StatusChangedByType.SYSTEM,
        changed_at=completed_at,
    )
    run.status = "failed"
    run.ended_at = completed_at
    run.error_text = error_text
    session.flush()
    requeue_run = enqueue_deferred_requeue(session, ticket=ticket, created_at=completed_at)
    return PublicationResult(run_status=run.status, queued_requeue_run_id=getattr(requeue_run, "id", None))


def finalize_superseded(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    completed_at,
) -> PublicationResult:
    run.status = "superseded"
    run.ended_at = completed_at
    session.flush()
    requeue_run = enqueue_deferred_requeue(session, ticket=ticket, created_at=completed_at)
    return PublicationResult(run_status=run.status, queued_requeue_run_id=getattr(requeue_run, "id", None))


def finalize_skipped(
    session: Session,
    *,
    ticket: Ticket,
    run: AiRun,
    completed_at,
) -> PublicationResult:
    run.status = "skipped"
    run.ended_at = completed_at
    session.flush()
    requeue_run = enqueue_deferred_requeue(session, ticket=ticket, created_at=completed_at)
    return PublicationResult(run_status=run.status, queued_requeue_run_id=getattr(requeue_run, "id", None))

```
# End of file: worker/triage.py

# File: worker/ticket_loader.py
```python
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from shared.models import (
    AttachmentVisibility,
    MessageVisibility,
    Ticket,
    TicketAttachment,
    TicketMessage,
)


@dataclass(frozen=True)
class LoadedMessage:
    id: uuid.UUID
    author_type: str
    source: str
    body_markdown: str
    body_text: str


@dataclass(frozen=True)
class LoadedAttachment:
    id: uuid.UUID
    message_id: uuid.UUID
    stored_path: str
    original_filename: str
    mime_type: str
    sha256: str
    created_order: tuple[str, str, str, str]

    @property
    def path(self) -> Path:
        return Path(self.stored_path)


@dataclass(frozen=True)
class TicketRunContext:
    ticket: Ticket
    public_messages: tuple[LoadedMessage, ...]
    internal_messages: tuple[LoadedMessage, ...]
    public_attachments: tuple[LoadedAttachment, ...]


def _load_messages(session: Session, *, ticket_id: uuid.UUID, visibility: str) -> tuple[LoadedMessage, ...]:
    messages = session.scalars(
        sa.select(TicketMessage)
        .where(
            TicketMessage.ticket_id == ticket_id,
            TicketMessage.visibility == visibility,
        )
        .order_by(TicketMessage.created_at.asc(), TicketMessage.id.asc())
    ).all()
    return tuple(
        LoadedMessage(
            id=message.id,
            author_type=message.author_type,
            source=message.source,
            body_markdown=message.body_markdown,
            body_text=message.body_text,
        )
        for message in messages
    )


def _load_public_attachments(session: Session, *, ticket_id: uuid.UUID) -> tuple[LoadedAttachment, ...]:
    rows = session.execute(
        sa.select(
            TicketAttachment,
            TicketMessage.created_at.label("message_created_at"),
        )
        .join(TicketMessage, TicketMessage.id == TicketAttachment.message_id)
        .where(
            TicketAttachment.ticket_id == ticket_id,
            TicketAttachment.visibility == AttachmentVisibility.PUBLIC.value,
            TicketMessage.visibility == MessageVisibility.PUBLIC.value,
        )
        .order_by(
            TicketMessage.created_at.asc(),
            TicketMessage.id.asc(),
            TicketAttachment.created_at.asc(),
            TicketAttachment.id.asc(),
        )
    ).all()
    return tuple(
        LoadedAttachment(
            id=attachment.id,
            message_id=attachment.message_id,
            stored_path=attachment.stored_path,
            original_filename=attachment.original_filename,
            mime_type=attachment.mime_type,
            sha256=attachment.sha256,
            created_order=(
                str(message_created_at.isoformat()),
                str(attachment.message_id),
                str(attachment.created_at.isoformat()),
                str(attachment.id),
            ),
        )
        for attachment, message_created_at in rows
    )


def load_ticket_run_context(session: Session, *, ticket_id: uuid.UUID) -> TicketRunContext:
    ticket = session.get(Ticket, ticket_id)
    if ticket is None:
        raise LookupError(f"Ticket {ticket_id} not found")
    return TicketRunContext(
        ticket=ticket,
        public_messages=_load_messages(
            session,
            ticket_id=ticket_id,
            visibility=MessageVisibility.PUBLIC.value,
        ),
        internal_messages=_load_messages(
            session,
            ticket_id=ticket_id,
            visibility=MessageVisibility.INTERNAL.value,
        ),
        public_attachments=_load_public_attachments(session, ticket_id=ticket_id),
    )


def compute_publication_fingerprint(context: TicketRunContext) -> str:
    payload = {
        "attachment_count": len(context.public_attachments),
        "public_attachments": [attachment.sha256 for attachment in context.public_attachments],
        "public_messages": [
            {
                "author_type": message.author_type,
                "body_text": message.body_text,
                "source": message.source,
            }
            for message in context.public_messages
        ],
        "status": context.ticket.status,
        "title": context.ticket.title,
        "urgent": context.ticket.urgent,
    }
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

```
# End of file: worker/ticket_loader.py

# File: docs/acceptance_matrix.md
```markdown
# Stage 1 Acceptance Matrix

This matrix maps PRD acceptance criteria AC1-AC19 to the primary implementation surfaces and their current verification path.

| AC | Requirement | Primary code paths | Automated verification | Manual verification |
| --- | --- | --- | --- | --- |
| AC1 | Local login with optional remember-me | `app/routes_auth.py`, `app/auth.py`, `shared/security.py` | `tests/test_requester_app.py`, `tests/test_security.py` | [manual_verification.md](/workspace/docloop/triage-stage1/docs/manual_verification.md) steps 1-2 |
| AC2 | PostgreSQL-backed opaque server-side sessions | `app/auth.py`, `shared/models.py`, `shared/security.py` | `tests/test_requester_app.py`, `tests/test_models.py` | steps 1-2 |
| AC3 | Requester can only see own tickets and public content | `app/routes_requester.py`, `shared/permissions.py` | `tests/test_requester_app.py` | steps 3-4 |
| AC4 | New ticket with optional title, urgency, and PNG/JPEG images | `app/routes_requester.py`, `app/uploads.py`, `shared/tickets.py` | `tests/test_requester_app.py`, `tests/test_uploads.py` | step 3 |
| AC5 | Vague ticket produces clarification questions and `waiting_on_user` | `worker/main.py`, `worker/triage.py` | `tests/test_worker_phase4.py` | step 7 |
| AC6 | Clear support/access ticket gets safe auto-reply | `worker/main.py`, `worker/triage.py` | `tests/test_worker_phase4.py` | step 7 |
| AC7 | Safe public confirm-and-route to Dev/TI | `worker/main.py`, `worker/triage.py` | `tests/test_worker_phase4.py` | step 7 |
| AC8 | Bug/feature route publishes one internal AI note and moves to Dev/TI | `worker/main.py`, `worker/triage.py` | `tests/test_worker_phase4.py` | step 7 |
| AC9 | AI drafts can be approved or rejected | `app/routes_ops.py`, `shared/tickets.py`, `worker/triage.py` | `tests/test_ops_app.py`, `tests/test_worker_phase4.py` | step 6 |
| AC10 | Requesters never see internal notes or internal AI analysis | `app/routes_requester.py`, `shared/permissions.py` | `tests/test_requester_app.py`, `tests/test_ops_app.py` | steps 4 and 6 |
| AC11 | Automatic public AI replies never leak internal-only facts | `worker/triage.py`, `worker/main.py` | `tests/test_worker_phase4.py`, `tests/test_ops_app.py` | steps 6-7 |
| AC12 | Repo-aware read-only Codex triage over `app/` and `manuals/` | `worker/codex_runner.py`, `shared/bootstrap.py` | `tests/test_worker_phase4.py`, `tests/test_phase5_operability.py` | steps 5 and 7 |
| AC13 | No repo modification, patching, branching, or SQL Server access | `worker/codex_runner.py`, `shared/workspace_contract.py` | `tests/test_worker_phase4.py`, `tests/test_phase5_operability.py` | steps 5 and 7 |
| AC14 | Resolved ticket reopens on requester reply and requeues AI | `shared/tickets.py`, `app/routes_requester.py` | `tests/test_requester_app.py` | step 4 |
| AC15 | One active AI run per ticket with requeue behavior | `shared/models.py`, `shared/tickets.py`, `worker/queue.py`, `worker/main.py` | `tests/test_models.py`, `tests/test_ticket_helpers.py`, `tests/test_worker_phase4.py` | step 7 |
| AC16 | Stale runs are suppressed and superseded | `worker/main.py`, `worker/queue.py`, `worker/ticket_loader.py` | `tests/test_worker_phase4.py` | step 7 |
| AC17 | Uploads enforce 3-image / 5 MiB limits | `app/routes_requester.py`, `app/uploads.py`, `shared/config.py` | `tests/test_requester_app.py`, `tests/test_uploads.py` | step 3 |
| AC18 | Unread markers only clear on ticket detail or successful same-ticket POST | `app/routes_requester.py`, `app/routes_ops.py`, `shared/tickets.py` | `tests/test_requester_app.py`, `tests/test_ops_app.py` | steps 4 and 6 |
| AC19 | No Kanboard, Slack, SMTP, or external notification dependency | `app/`, `worker/`, `scripts/`, `README.md` | `tests/test_phase5_operability.py` | step 8 |

```
# End of file: docs/acceptance_matrix.md


```
# End of file: docs/triage_stage1_codebase_extract.md

# File: docs/manual_verification.md
```markdown
# Stage 1 Manual Verification

Use this checklist after `alembic upgrade head`, `python scripts/bootstrap_workspace.py`, one admin account, one requester account, the web app, and the worker are all running locally.

1. Verify login and remember-me.
Open `/login`, sign in once without `Remember me`, then sign out and sign back in with `Remember me` enabled. Confirm both flows succeed and the browser keeps the persistent session after a full browser restart only for the remember-me case.

2. Verify requester isolation.
Create tickets as `requester-a` and `requester-b`. Confirm each requester can only see their own `/app/tickets` entries and receives `404` for the other requester's detail and attachment URLs.

3. Verify requester intake and upload limits.
Create a ticket with no title, free-text description, urgency enabled, and one PNG or JPEG image. Confirm the ticket is created, the provisional title is derived from the description, and the image is viewable through the authenticated attachment route. Confirm uploads above 3 images or above 5 MiB are rejected.

4. Verify requester unread tracking and reopen behavior.
As a Dev/TI user, post a public reply to the requester's ticket. Confirm the requester's `/app/tickets` list shows the ticket as updated until the requester opens the detail page. Resolve the ticket, then reply as the requester and confirm the ticket reopens into `ai_triage`.

5. Verify workspace/bootstrap readiness.
Run `GET /readyz` before and after `python scripts/bootstrap_workspace.py`. Confirm readiness stays failing before bootstrap and turns healthy only after the uploads directory, workspace Git repo, mounts, `AGENTS.md`, and `.agents/skills/stage1-triage/SKILL.md` are present.

6. Verify Dev/TI draft review and non-leak behavior.
Open a ticket with an internal note plus a pending AI draft. Approve the draft and confirm the requester only sees the published public text, not the internal note contents. Repeat with draft rejection and confirm no public AI message is created.

7. Verify worker routing invariants.
Submit one vague ticket, one clear support ticket, and one likely bug or feature request. Confirm the worker produces, respectively, a clarification request, a safe public reply, and an internal route to Dev/TI. While a run is active, add a requester reply and confirm the original run is superseded without publishing stale output and exactly one new pending run is queued.

8. Verify Stage 1 isolation.
Confirm the local workflow operates entirely in-app: no Kanboard sync, Slack messages, SMTP mail, patch creation, branch creation, or SQL Server access should be required anywhere in the flow.

```
# End of file: docs/manual_verification.md

