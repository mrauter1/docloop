# Implement ↔ Code Reviewer Feedback

## 2026-03-18 Producer Cycle 1 Attempt 1

- Implemented the approved portability/scale slice across policy, execution, batch, adapter, and export surfaces.
- Added fallback model policies, runtime cost controls, approval/audit hooks, simulator mode, timeout handling, Azure OpenAI support, and batch budget reporting.
- Added optional domain-pack scaffolding plus pack validation enforcing compatibility metadata, eval suites, and tests.
- Verified the implementation with `python3 -m pytest -q` (`86 passed, 1 skipped`).

## 2026-03-18 Verifier Cycle 1 Attempt 1

- `IMP-001` `blocking`: [`fuzzy/core.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py) `_invoke_executor` now runs every synchronous executor through `asyncio.to_thread(...)` even when no timeout is configured (`_invoke_executor` at [fuzzy/core.py](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py):1517). That is a behavior break for existing `dispatch(..., auto_execute=True)` callers whose executors rely on thread-local state, request-scoped DB sessions, non-thread-safe handles, or in-thread transaction semantics. Concrete failure scenario: an executor that previously used a request-bound SQLAlchemy session or thread-local auth context will start failing or mutating outside the expected context after this change, even with no timeout configured. Minimal fix: preserve inline execution for synchronous executors when `timeout_seconds is None`, and centralize timeout-specific off-thread execution in the timeout path only.
- `IMP-002` `blocking`: [`fuzzy/batch.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/batch.py) now always invokes primitives with `return_trace=True` and returns successful `BatchResult.trace` values even when the caller passed `return_traces=False` ([fuzzy/batch.py](/home/marcelo/code/docloop/Fuzzy/fuzzy/batch.py):258-266 and [fuzzy/batch.py](/home/marcelo/code/docloop/Fuzzy/fuzzy/batch.py):228-235). This silently changes the public batch contract and can expose full evidence traces, including caller context/messages, to downstream logging/serialization paths that explicitly opted out of traces. Concrete failure scenario: an application that logs or forwards `BatchReport.results` expecting trace-free payloads now emits raw user evidence and provider metadata, creating a privacy and payload-size regression. Minimal fix: keep internal trace collection private for accounting/budget logic, but strip `BatchResult.trace` back to `None` unless `return_traces=True`; centralize the internal accounting handoff in a private wrapper or local variable rather than overloading the public result shape.

## 2026-03-18 Producer Cycle 2 Attempt 1

- Resolved `IMP-001` by restoring inline synchronous executor execution when no timeout is configured and limiting off-thread execution to the timeout path.
- Resolved `IMP-002` by separating batch’s internal trace accounting from the public `BatchResult.trace` field so successful traces stay hidden unless `return_traces=True`.
- Added regression tests covering both fixes and reran the full suite successfully with `python3 -m pytest -q` (`88 passed, 1 skipped`).

## 2026-03-18 Verifier Cycle 2 Attempt 1

- `IMP-003` `blocking`: [`fuzzy/core.py`](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py) `_invoke_executor` still implements timeout for synchronous executors by running them in `asyncio.to_thread(...)` and timing out the await, but that does not stop the underlying thread or side effects ([fuzzy/core.py](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py):1560-1570). Concrete failure scenario: a sync executor that writes to an external system after 50ms with `timeout_seconds=0.01` will cause `dispatch(..., auto_execute=True)` to raise `FrameworkError("command_execution", "...timed out...")`, yet the write can still happen moments later in the background thread. That creates a hidden reliability/data-integrity regression because callers may retry or escalate under the assumption that execution never happened. Minimal fix: either reject timeout configuration for synchronous executors, or centralize timeout handling behind a mechanism that provides cooperative cancellation/isolated execution semantics instead of `to_thread` best-effort waiting.

## 2026-03-18 Producer Cycle 3 Attempt 1

- Resolved `IMP-003` by rejecting timeout configuration for synchronous executors before execution and keeping actual timeout enforcement only for async executors.
- Added regression coverage for both async timeout behavior and sync timeout rejection.
- Reran the full suite successfully with `python3 -m pytest -q` (`89 passed, 1 skipped`).

## 2026-03-18 Verifier Cycle 3 Attempt 1

- `IMP-004` `non-blocking`: Re-review found no remaining blocking implementation issues. The current code preserves the batch trace contract, preserves inline sync executor behavior when no timeout is requested, rejects unsafe sync-executor timeout configuration before execution, and keeps async timeout coverage in tests. Criteria updated to complete.
