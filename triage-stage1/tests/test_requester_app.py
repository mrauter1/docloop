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
