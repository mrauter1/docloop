# Plan ↔ Plan Verifier Feedback

## 2026-03-18 producer cycle 1 attempt 1

- Replaced the placeholder `plan.md` with an implementation-ready plan scoped only to the remaining deferred items from the current baseline.
- Captured the baseline gaps actually present in the repo: missing Anthropic/Gemini/local-compatible adapter entrypoints, caller-only pricing without a first-party catalog, and thin pack scaffolding/validation.
- Defined three concrete milestones with proposed public interfaces, sequencing, definition-of-done criteria, and a risk register so the implement phase can execute without re-planning.

## 2026-03-18 verifier cycle 1 attempt 1

- `PLAN-001` non-blocking: The pricing-helper examples in `plan.md` mention `pricing=[get_model_pricing(...)]`, but the current runtime pricing normalization only accepts concrete `ModelPricing` entries. Tighten the implement-phase contract so helper usage either guarantees non-`None` returns or documents that callers must filter/validate lookup misses before passing the list into `run_batch(...)`.
