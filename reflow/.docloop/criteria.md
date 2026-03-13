# Document Verification Criteria
Check these boxes (`- [x]`) only when the target document itself satisfies the rule.

## Completeness
- [x] **Implementation-Ready Scope**: The document defines the system purpose, major components, responsibilities, and boundaries clearly enough that an autonomous coding agent would not need to invent the overall design.
- [x] **Behavior Completeness**: The document now deterministically defines `run` and `resume` workspace-lock behavior, including stale-lock repair, refusal on any non-stale live lock, and the exact no-mutation refusal path for pre-ownership command-state errors.
- [x] **Interface & Data Contracts**: The `active.json`, `run.json`, `history.jsonl`, and iteration-record contracts specify the required fields and refusal semantics needed to implement locking, resume, failure handling, and artifact persistence consistently.
- [x] **Operational Constraints**: Relevant runtime constraints are stated clearly, including performance, security, observability, configuration, deployment assumptions, and other non-functional requirements that affect implementation.

## Clarity
- [x] **Ambiguity Control**: The document resolves the previously open lock/resume edge cases with explicit stale-lock, live-lock, refusal, and exit-code rules, leaving no material guess in the control flow.
- [x] **Internal Consistency**: The lock contract, resume semantics, CLI command rules, and exit-code mapping now align on one active run per workspace and one consistent refusal path for conflicting live controllers.

## Economy
- [x] **Single Source of Truth**: Canonical rules now mostly live in the contract sections, with later algorithm/testing sections serving as concise summaries or informative guidance rather than redundant normative restatements.
- [x] **Appropriate Abstraction Level**: The document stays focused on externally observable behavior, persisted state, and implementation-critical contracts, while internal module layout and delivery order are clearly marked as informative only.
