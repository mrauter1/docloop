# Implement ↔ Code Reviewer Feedback

- IMP-001 `blocking`: [loop_control.py](/workspace/CodexTest/docloop/loop_control.py#L53) `parse_loop_control()` / `_parse_canonical_control()` do not enforce the new requirement that canonical `<loop-control>` output be the last non-empty logical block. Today a payload like `...<loop-control>{"schema":"docloop.loop_control/v1","kind":"promise","promise":"COMPLETE"}</loop-control>\nextra prose` is accepted as canonical, so `docloop.py` and `superloop.py` will treat that verifier pass as `COMPLETE` even though the protocol says trailing output after the control block is invalid and should fail fast. That weakens the contract the prompts and README now rely on, and it can hide agent drift or conflicting post-block text instead of surfacing a hard protocol error. Minimal fix: reject any non-whitespace trailing content outside the single canonical block before decoding it, and add a regression fixture/test for canonical block plus trailing prose.


## System Warning (cycle 1)
No promise tag found, defaulted to <promise>INCOMPLETE</promise>.

## Review Update (cycle 2)

No remaining blocking or non-blocking findings in the current implementation diff review. `IMP-001` is resolved by rejecting canonical `<loop-control>` output with trailing non-whitespace content in `loop_control.py`, and the regression is covered by `tests/test_loop_control.py` plus the `canonical_trailing_prose.txt` fixture.


## System Warning (cycle 2)
No promise tag found, defaulted to <promise>INCOMPLETE</promise>.

## Review Update (cycle 3)

No remaining blocking or non-blocking findings in the current implementation diff review. The shared `loop_control.py` parser, the `docloop.py` and `superloop.py` integrations, and the new fixture-backed tests are consistent with the documented canonical loop-control contract, including rejection of trailing prose after a canonical block.


## System Warning (cycle 3)
No promise tag found, defaulted to <promise>INCOMPLETE</promise>.
