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

For reproducible installs that match the validated Stage 1 test environment, use:

```bash
pip install -r requirements.lock
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

**Stuck-run reaper**

The worker automatically reaps AI runs stuck in `running` state for longer than twice the configured `CODEX_TIMEOUT_SECONDS`. This handles cases where the worker process was killed mid-execution. To run the reaper manually:

```bash
python scripts/reap_stuck_runs.py
python scripts/reap_stuck_runs.py --max-age-seconds 300
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
