# implementation_notes.md

## Files Changed

- `fuzzy/recipes/__init__.py`
- `fuzzy/recipes/common.py`
- `fuzzy/recipes/support.py`
- `fuzzy/recipes/sales.py`
- `fuzzy/recipes/approval.py`
- `fuzzy/recipes/fixtures.py`
- `examples/fastapi_support.py`
- `examples/django_lead_service.py`
- `tests/test_recipes.py`

## Checklist Mapping

- Milestone B1 trace substrate: already present in repository baseline for this run; validated indirectly by the existing passing trace/eval suite.
- Milestone B2 trace storage and viewing: already present in repository baseline for this run; no corrective changes required in this pass.
- Milestone B3 eval foundation: reused existing `fuzzy.evals` APIs to ship recipe-level eval fixtures.
- Milestone B4 regression and CI helpers: reused existing report/assertion helpers; added recipe fixture coverage through tests.
- Milestone C1 `fuzzy.recipes` package: implemented with three coherent flagship slices:
  - support triage
  - lead qualification
  - approval routing
- Milestone C2 reference integrations: added lightweight FastAPI-style and Django-style example service functions under `examples/`.
- Phase 4 portability/scale items: intentionally deferred.
- Phase 5 ecosystem/pack items: intentionally deferred.

## Assumptions

- Release A and the Release B foundations already existed in the worktree and were stable enough to build on without reworking core contracts.
- The most coherent next milestone was Release C recipes layered on existing primitives, traces, and evals rather than widening into Phase 4 policy/scaling controls.
- Recipe examples should stay dependency-free and demonstrate integration style without pulling framework packages into the test/runtime surface.

## Expected Side Effects

- Repository users can now import `fuzzy.recipes` and use three thin, typed workflow helpers without expanding the top-level package surface.
- Recipe calls can accept either structured context assembled from typed inputs or ordered `messages`, and can optionally return per-step trace bundles.
- Follow-up recipe steps now preserve original ordered `messages` and append step summaries as extra structured evidence instead of dropping caller evidence after extraction.
- The new examples compile and the new tests add baseline regression coverage for recipe behavior and bundled eval fixtures.

## Deduplication / Centralization Decisions

- Added `fuzzy/recipes/common.py` to centralize recipe trace collection, multi-step return wrapping, and context-versus-messages routing so the three recipes do not duplicate orchestration glue.
- Extended `fuzzy/recipes/common.py` with shared follow-up evidence propagation so step-two dispatch calls reuse original caller evidence in both context and message modes.
- Kept recipe schemas local to each recipe module because they are part of the recipe contract and are reused directly by the bundled eval fixtures.

## Reviewer Feedback Resolution

- Resolved `IMP-001` by preserving original `messages` into recipe dispatch steps and appending extraction summaries as additional JSON evidence.
- Added a regression assertion in `tests/test_recipes.py` that inspects the second request for `qualify_lead(...)` and verifies the original ordered messages are still present.

## Deferred Items

- No new first-party adapters were added.
- No batch runner, fallback policy, approval hook, audit hook, or runtime cost controls were added.
- No optional domain-pack scaffolding or contribution-template work was added.
