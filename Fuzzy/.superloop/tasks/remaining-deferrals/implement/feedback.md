# Implement ↔ Code Reviewer Feedback

## 2026-03-18 reviewer cycle 1 attempt 1

- `IMP-001` blocking: [fuzzy/__init__.py](/home/marcelo/code/docloop/Fuzzy/fuzzy/__init__.py) removed the existing public `drop` export when expanding the module exports. `drop` still exists in [fuzzy/core.py](/home/marcelo/code/docloop/Fuzzy/fuzzy/core.py), and the accepted plan explicitly said not to change primitive/public interfaces. Any downstream caller using `from fuzzy import drop` will now fail with `ImportError`, which is a compatibility regression unrelated to the remaining-deferrals scope. Minimal fix: re-export `drop` from `fuzzy.__init__` and restore it in `__all__`.
- `IMP-002` non-blocking: [fuzzy/packs.py](/home/marcelo/code/docloop/Fuzzy/fuzzy/packs.py) validates `pyproject.toml` with a narrow regex parser that only accepts a small subset of valid TOML string forms. That is acceptable for the in-repo fixtures, but it is brittle for third-party publishable packs and may reject otherwise valid metadata formatting. Minimal follow-up: broaden the parser to handle the standard string forms this validator intends to support, or clearly document the intentionally limited subset.

## 2026-03-18 reviewer cycle 2 attempt 1

- No additional findings. `IMP-001` is resolved by restoring `drop` to [fuzzy/__init__.py](/home/marcelo/code/docloop/Fuzzy/fuzzy/__init__.py), and the `IMP-002` follow-up was addressed by broadening accepted quoted string syntax in [fuzzy/packs.py](/home/marcelo/code/docloop/Fuzzy/fuzzy/packs.py) with regression coverage in [tests/test_packs.py](/home/marcelo/code/docloop/Fuzzy/tests/test_packs.py).
