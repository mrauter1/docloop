from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.main import create_app
from shared.config import Settings
from shared.models import (
    AiRun,
    AiRunStatus,
    AiRunTrigger,
    Base,
    MessageSource,
    MessageVisibility,
    Ticket,
    TicketMessage,
    User,
    UserRole,
)
from shared.security import hash_password
from shared.tickets import ActiveAIRunExistsError, create_pending_ai_run, create_requester_ticket
from worker.main import claim_next_run, finish_prepared_run
from worker.queue import enqueue_deferred_requeue
from worker.triage import finalize_failure


def make_app_settings(database_url: str, uploads_dir: Path) -> Settings:
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
    temp_dir = Path(tempfile.mkdtemp(prefix="triage-stage1-phase2-app-test-"))
    db_path = temp_dir / "test.db"
    uploads_dir = temp_dir / "uploads"
    engine = sa.create_engine(
        f"sqlite+pysqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    settings = make_app_settings(f"sqlite+pysqlite:///{db_path}", uploads_dir)
    app = create_app(settings=settings, session_factory=session_factory)
    client = TestClient(app)
    return client, session_factory


def make_worker_settings(database_url: str, workspace_dir: Path, uploads_dir: Path) -> Settings:
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
    temp_dir = Path(tempfile.mkdtemp(prefix="triage-stage1-phase2-worker-test-"))
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
    settings = make_worker_settings(f"sqlite+pysqlite:///{db_path}", workspace_dir, uploads_dir)
    return session_factory, settings


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


def extract_hidden_csrf(html: str) -> str:
    return html.split('name="csrf_token" value="', 1)[1].split('"', 1)[0]


@pytest.mark.parametrize(
    ("role", "expected_location"),
    [
        (UserRole.REQUESTER.value, "/app"),
        (UserRole.DEV_TI.value, "/ops"),
    ],
)
def test_login_browser_submit_uses_hidden_token_and_preserves_role_redirects(
    role: str,
    expected_location: str,
) -> None:
    client, session_factory = build_client()
    user = seed_user(session_factory, email=f"{role}@example.com", role=role)

    response = client.get("/login")
    hidden_csrf = extract_hidden_csrf(response.text)

    assert hidden_csrf

    login_response = client.post(
        "/login",
        data={
            "email": user.email,
            "password": "password123",
            "csrf_token": hidden_csrf,
        },
        follow_redirects=False,
    )

    assert login_response.status_code == 303
    assert login_response.headers["location"] == expected_location


def test_login_browser_submit_rejects_tampered_hidden_token_with_403() -> None:
    client, session_factory = build_client()
    user = seed_user(session_factory, email="tampered@example.com", role=UserRole.REQUESTER.value)

    response = client.get("/login")
    original_token = extract_hidden_csrf(response.text)

    assert original_token

    failure_response = client.post(
        "/login",
        data={
            "email": user.email,
            "password": "password123",
            "csrf_token": f"{original_token}-tampered",
        },
        follow_redirects=False,
    )

    assert failure_response.status_code == 403
    assert "Invalid login form session." in failure_response.text
    assert extract_hidden_csrf(failure_response.text)


def test_enqueue_deferred_requeue_clears_flags_when_active_run_is_already_visible(monkeypatch) -> None:
    session_factory, _settings = build_session_factory()
    requester = seed_user(
        session_factory,
        email="active-visible@example.com",
        role=UserRole.REQUESTER.value,
    )
    ticket, original_run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Need requeue",
        body="Body",
        created_at=datetime(2026, 3, 20, 12, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        run_db = session.get(AiRun, original_run.id)
        assert ticket_db is not None
        assert run_db is not None
        run_db.status = AiRunStatus.SUPERSEDED.value
        run_db.ended_at = datetime(2026, 3, 20, 12, 1, tzinfo=timezone.utc)
        ticket_db.requeue_requested = True
        ticket_db.requeue_trigger = AiRunTrigger.REQUESTER_REPLY.value
        session.flush()
        create_pending_ai_run(
            session,
            ticket_id=ticket.id,
            triggered_by=AiRunTrigger.REQUESTER_REPLY,
            created_at=datetime(2026, 3, 20, 12, 2, tzinfo=timezone.utc),
        )
        session.commit()

    def raise_active_run_exists(*args, **kwargs):
        raise ActiveAIRunExistsError("already queued")

    monkeypatch.setattr("worker.queue.create_pending_ai_run", raise_active_run_exists)

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        assert ticket_db is not None

        queued_run = enqueue_deferred_requeue(
            session,
            ticket=ticket_db,
            created_at=datetime(2026, 3, 20, 12, 3, tzinfo=timezone.utc),
        )
        session.commit()

        assert queued_run is None
        assert ticket_db.requeue_requested is False
        assert ticket_db.requeue_trigger is None

    with session_factory() as session:
        active_runs = session.scalars(
            sa.select(AiRun).where(
                AiRun.ticket_id == ticket.id,
                AiRun.status.in_([AiRunStatus.PENDING.value, AiRunStatus.RUNNING.value]),
            )
        ).all()
        assert len(active_runs) == 1


def test_enqueue_deferred_requeue_handles_active_run_integrity_race(monkeypatch) -> None:
    session_factory, _settings = build_session_factory()
    requester = seed_user(
        session_factory,
        email="integrity-race@example.com",
        role=UserRole.REQUESTER.value,
    )
    ticket, original_run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Need requeue",
        body="Body",
        created_at=datetime(2026, 3, 20, 13, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        run_db = session.get(AiRun, original_run.id)
        assert ticket_db is not None
        assert run_db is not None
        run_db.status = AiRunStatus.SUPERSEDED.value
        run_db.ended_at = datetime(2026, 3, 20, 13, 1, tzinfo=timezone.utc)
        ticket_db.requeue_requested = True
        ticket_db.requeue_trigger = AiRunTrigger.REQUESTER_REPLY.value
        session.flush()
        create_pending_ai_run(
            session,
            ticket_id=ticket.id,
            triggered_by=AiRunTrigger.REQUESTER_REPLY,
            created_at=datetime(2026, 3, 20, 13, 2, tzinfo=timezone.utc),
        )
        session.commit()

    def raise_integrity_error(*args, **kwargs):
        raise IntegrityError("insert into ai_runs", {}, Exception("uq_ai_runs_ticket_active"))

    monkeypatch.setattr("worker.queue.create_pending_ai_run", raise_integrity_error)

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        assert ticket_db is not None

        queued_run = enqueue_deferred_requeue(
            session,
            ticket=ticket_db,
            created_at=datetime(2026, 3, 20, 13, 3, tzinfo=timezone.utc),
        )
        session.commit()

        assert queued_run is None
        assert ticket_db.requeue_requested is False
        assert ticket_db.requeue_trigger is None

    with session_factory() as session:
        active_runs = session.scalars(
            sa.select(AiRun).where(
                AiRun.ticket_id == ticket.id,
                AiRun.status.in_([AiRunStatus.PENDING.value, AiRunStatus.RUNNING.value]),
            )
        ).all()
        assert len(active_runs) == 1


def test_finish_prepared_run_is_noop_after_reaper_already_failed_the_run(monkeypatch) -> None:
    session_factory, settings = build_session_factory()
    requester = seed_user(session_factory, email="crossed@example.com", role=UserRole.REQUESTER.value)
    ticket, original_run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Crossed completion",
        body="Body",
        created_at=datetime(2026, 3, 20, 14, tzinfo=timezone.utc),
    )

    execution = claim_next_run(
        session_factory,
        settings=settings,
        claimed_at=datetime(2026, 3, 20, 14, 1, tzinfo=timezone.utc),
    )
    assert execution is not None

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        run_db = session.get(AiRun, original_run.id)
        assert ticket_db is not None
        assert run_db is not None
        ticket_db.requeue_requested = True
        ticket_db.requeue_trigger = AiRunTrigger.REQUESTER_REPLY.value
        result = finalize_failure(
            session,
            ticket=ticket_db,
            run=run_db,
            error_text="Run stuck in running state for over 120 seconds (started at 2026-03-20T14:01:00+00:00). Reaped by worker.",
            completed_at=datetime(2026, 3, 20, 14, 2, tzinfo=timezone.utc),
        )
        session.commit()
        assert result.run_status == AiRunStatus.FAILED.value

    def fail_if_called(*args, **kwargs):
        raise AssertionError("run_codex should not be called for an already-terminal run")

    monkeypatch.setattr("worker.main.run_codex", fail_if_called)

    status = finish_prepared_run(
        session_factory,
        settings=settings,
        execution=execution,
        completed_at=datetime(2026, 3, 20, 14, 3, tzinfo=timezone.utc),
    )

    assert status == AiRunStatus.FAILED.value

    with session_factory() as session:
        runs = session.scalars(
            sa.select(AiRun)
            .where(AiRun.ticket_id == ticket.id)
            .order_by(AiRun.created_at.asc(), AiRun.id.asc())
        ).all()
        system_notes = session.scalars(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.source == MessageSource.SYSTEM.value,
                TicketMessage.visibility == MessageVisibility.INTERNAL.value,
            )
        ).all()
        ai_notes = session.scalars(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.source == MessageSource.AI_INTERNAL_NOTE.value,
            )
        ).all()
        ticket_db = session.get(Ticket, ticket.id)

        assert ticket_db is not None
        assert len(runs) == 2
        assert runs[0].status == AiRunStatus.FAILED.value
        assert runs[1].status == AiRunStatus.PENDING.value
        assert ticket_db.requeue_requested is False
        assert ticket_db.requeue_trigger is None
        assert len(system_notes) == 1
        assert ai_notes == []
