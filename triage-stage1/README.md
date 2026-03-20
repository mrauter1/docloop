# Stage 1 AI Triage MVP

This subproject contains the isolated implementation for the Stage 1 custom Python triage application described in the frozen PRD.

Phase 1 establishes:
- the local dependency manifest
- a documented `.env.example` for the Stage 1 runtime contract
- environment settings loading
- SQLAlchemy models for the full Stage 1 schema
- an Alembic baseline migration
- shared persistence helpers for ticket status, views, drafts, references, and active AI run checks

Later phases will add the FastAPI UI, server-side sessions, worker execution, and bootstrap scripts on top of this foundation.
