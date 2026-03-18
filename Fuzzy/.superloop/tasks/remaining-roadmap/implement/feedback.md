# Implement ↔ Code Reviewer Feedback

## Findings

### IMP-001 `blocking`

File/symbols: `fuzzy/recipes/support.py:86`, `fuzzy/recipes/sales.py:80`, `fuzzy/recipes/approval.py:77`

When a recipe is called with `messages=...`, the first `extract(...)` step sees the original caller evidence, but the second `dispatch(...)` step does not. Each recipe rebuilds step-two input from only the extracted summary plus `None` placeholders for the original structured fields, so the original ordered messages are discarded before action selection.

Concrete failure scenario:
- A support conversation contains abuse indicators and refund language.
- The extraction step compresses that into `{"category": "billing", "urgency": "high", "refund_candidate": true}`.
- The dispatch step can no longer inspect the original conversation and may route `open_refund_review_case` instead of `escalate_to_abuse_queue`, because the nuance needed for the second decision was dropped.

This violates the explicit evidence-boundary intent for advanced `messages` input and makes the recipe path materially less reliable than the underlying primitives.

Minimal fix direction:
- Centralize a helper in `fuzzy/recipes/common.py` that preserves original caller evidence across recipe steps.
- For message-mode calls, pass the original `messages` into the dispatch step and append the extracted summary as additional structured evidence instead of replacing the evidence surface.
- Add a regression test that proves `messages` survive into step two for at least one recipe.

Resolution review, cycle 2:
- Verified resolved. `extend_recipe_evidence(...)` now preserves original `messages` and appends the extracted summary as additional JSON evidence for the second step.
- Verified with the new regression assertion in `tests/test_recipes.py` plus a passing targeted recipe test run.

No additional findings in the follow-up diff.
