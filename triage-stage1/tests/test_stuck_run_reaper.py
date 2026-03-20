from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from scripts import reap_stuck_runs as reap_stuck_runs_script
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
    TicketStatus,
    User,
    UserRole,
)
from shared.security import hash_password
from shared.tickets import create_requester_ticket
from worker.main import reap_stuck_runs


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
    temp_dir = Path(tempfile.mkdtemp(prefix="triage-stage1-reaper-test-"))
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


def mark_run_running(
    session_factory: sessionmaker[Session],
    *,
    ticket_id,
    run_id,
    started_at: datetime,
) -> None:
    with session_factory() as session:
        ticket = session.get(Ticket, ticket_id)
        run = session.get(AiRun, run_id)
        assert ticket is not None
        assert run is not None
        ticket.status = TicketStatus.AI_TRIAGE.value
        run.status = AiRunStatus.RUNNING.value
        run.started_at = started_at
        run.ended_at = None
        run.error_text = None
        session.commit()


def test_reaper_marks_stuck_running_run_as_failed_and_routes_ticket() -> None:
    session_factory, settings = build_session_factory()
    requester = seed_user(session_factory, email="stuck@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Stuck run",
        body="Body",
        created_at=datetime(2026, 3, 20, 9, tzinfo=timezone.utc),
    )
    mark_run_running(
        session_factory,
        ticket_id=ticket.id,
        run_id=run.id,
        started_at=datetime(2026, 3, 20, 9, 56, 40, tzinfo=timezone.utc),
    )

    reaped = reap_stuck_runs(
        session_factory,
        settings=settings,
        max_age_seconds=150,
        reaped_at=datetime(2026, 3, 20, 10, tzinfo=timezone.utc),
    )

    assert reaped == 1

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        run_db = session.get(AiRun, run.id)
        note = session.scalar(
            sa.select(TicketMessage).where(
                TicketMessage.ticket_id == ticket.id,
                TicketMessage.source == MessageSource.SYSTEM.value,
                TicketMessage.visibility == MessageVisibility.INTERNAL.value,
            )
        )
        assert ticket_db is not None
        assert run_db is not None
        assert note is not None
        assert run_db.status == AiRunStatus.FAILED.value
        assert "stuck" in (run_db.error_text or "").lower()
        assert ticket_db.status == TicketStatus.WAITING_ON_DEV_TI.value


def test_reaper_ignores_running_run_within_age_threshold() -> None:
    session_factory, settings = build_session_factory()
    requester = seed_user(session_factory, email="fresh@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Fresh run",
        body="Body",
        created_at=datetime(2026, 3, 20, 10, tzinfo=timezone.utc),
    )
    mark_run_running(
        session_factory,
        ticket_id=ticket.id,
        run_id=run.id,
        started_at=datetime(2026, 3, 20, 10, 4, tzinfo=timezone.utc),
    )

    reaped = reap_stuck_runs(
        session_factory,
        settings=settings,
        max_age_seconds=150,
        reaped_at=datetime(2026, 3, 20, 10, 5, tzinfo=timezone.utc),
    )

    assert reaped == 0

    with session_factory() as session:
        run_db = session.get(AiRun, run.id)
        assert run_db is not None
        assert run_db.status == AiRunStatus.RUNNING.value


def test_reaper_ignores_pending_and_completed_runs() -> None:
    session_factory, settings = build_session_factory()
    requester = seed_user(session_factory, email="mixed@example.com", role=UserRole.REQUESTER.value)
    pending_ticket, pending_run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Pending run",
        body="Body",
        created_at=datetime(2026, 3, 20, 11, tzinfo=timezone.utc),
    )
    completed_ticket, completed_run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Completed run",
        body="Body",
        created_at=datetime(2026, 3, 20, 11, 5, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        completed_run_db = session.get(AiRun, completed_run.id)
        completed_ticket_db = session.get(Ticket, completed_ticket.id)
        assert completed_run_db is not None
        assert completed_ticket_db is not None
        completed_ticket_db.status = TicketStatus.WAITING_ON_USER.value
        completed_run_db.status = AiRunStatus.SUCCEEDED.value
        completed_run_db.started_at = datetime(2026, 3, 20, 11, 0, tzinfo=timezone.utc)
        completed_run_db.ended_at = datetime(2026, 3, 20, 11, 1, tzinfo=timezone.utc)
        session.commit()

    reaped = reap_stuck_runs(
        session_factory,
        settings=settings,
        max_age_seconds=150,
        reaped_at=datetime(2026, 3, 20, 11, 10, tzinfo=timezone.utc),
    )

    assert reaped == 0

    with session_factory() as session:
        pending_run_db = session.get(AiRun, pending_run.id)
        completed_run_db = session.get(AiRun, completed_run.id)
        assert pending_run_db is not None
        assert completed_run_db is not None
        assert pending_run_db.status == AiRunStatus.PENDING.value
        assert completed_run_db.status == AiRunStatus.SUCCEEDED.value


def test_reaper_enqueues_deferred_requeue_when_requested() -> None:
    session_factory, settings = build_session_factory()
    requester = seed_user(session_factory, email="requeue@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Requeue run",
        body="Body",
        created_at=datetime(2026, 3, 20, 12, tzinfo=timezone.utc),
    )
    mark_run_running(
        session_factory,
        ticket_id=ticket.id,
        run_id=run.id,
        started_at=datetime(2026, 3, 20, 12, 56, 40, tzinfo=timezone.utc),
    )

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        assert ticket_db is not None
        ticket_db.requeue_requested = True
        ticket_db.requeue_trigger = AiRunTrigger.REQUESTER_REPLY.value
        session.commit()

    reaped = reap_stuck_runs(
        session_factory,
        settings=settings,
        max_age_seconds=150,
        reaped_at=datetime(2026, 3, 20, 13, tzinfo=timezone.utc),
    )

    assert reaped == 1

    with session_factory() as session:
        ticket_db = session.get(Ticket, ticket.id)
        runs = session.scalars(
            sa.select(AiRun)
            .where(AiRun.ticket_id == ticket.id)
            .order_by(AiRun.created_at.asc(), AiRun.id.asc())
        ).all()
        assert ticket_db is not None
        assert runs[0].status == AiRunStatus.FAILED.value
        assert runs[1].status == AiRunStatus.PENDING.value
        assert runs[1].triggered_by == AiRunTrigger.REQUESTER_REPLY.value
        assert ticket_db.requeue_requested is False


def test_reaper_uses_double_codex_timeout_as_default_threshold() -> None:
    session_factory, settings = build_session_factory()
    settings = Settings.from_env(
        {
            "APP_BASE_URL": settings.app_base_url,
            "APP_SECRET_KEY": settings.app_secret_key,
            "DATABASE_URL": settings.database_url,
            "CODEX_API_KEY": settings.codex_api_key,
            "TRIAGE_WORKSPACE_DIR": str(settings.triage_workspace_dir),
            "REPO_MOUNT_DIR": str(settings.repo_mount_dir),
            "MANUALS_MOUNT_DIR": str(settings.manuals_mount_dir),
            "UPLOADS_DIR": str(settings.uploads_dir),
            "CODEX_BIN": settings.codex_bin,
            "CODEX_TIMEOUT_SECONDS": "30",
        }
    )
    requester = seed_user(session_factory, email="default-threshold@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Default threshold",
        body="Body",
        created_at=datetime(2026, 3, 20, 13, tzinfo=timezone.utc),
    )
    mark_run_running(
        session_factory,
        ticket_id=ticket.id,
        run_id=run.id,
        started_at=datetime(2026, 3, 20, 13, 58, 55, tzinfo=timezone.utc),
    )

    reaped = reap_stuck_runs(
        session_factory,
        settings=settings,
        max_age_seconds=None,
        reaped_at=datetime(2026, 3, 20, 14, tzinfo=timezone.utc),
    )

    assert reaped == 1

    with session_factory() as session:
        run_db = session.get(AiRun, run.id)
        assert run_db is not None
        assert run_db.status == AiRunStatus.FAILED.value


def test_reap_stuck_runs_script_outputs_json(capsys) -> None:
    session_factory, settings = build_session_factory()
    requester = seed_user(session_factory, email="script@example.com", role=UserRole.REQUESTER.value)
    ticket, run = create_ticket_fixture(
        session_factory,
        creator=requester,
        title="Script threshold",
        body="Body",
        created_at=datetime(2026, 3, 20, 14, tzinfo=timezone.utc),
    )
    mark_run_running(
        session_factory,
        ticket_id=ticket.id,
        run_id=run.id,
        started_at=datetime(2026, 3, 20, 14, 56, 40, tzinfo=timezone.utc),
    )

    exit_code = reap_stuck_runs_script.main(
        [],
        settings=settings,
        session_factory=session_factory,
    )
    output = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(output.out) == {"status": "ok", "reaped_count": 1}
