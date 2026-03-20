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
