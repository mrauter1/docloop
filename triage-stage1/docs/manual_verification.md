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
