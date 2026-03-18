# Fuzzy Pack Template

Use this scaffold for optional domain packs that extend `fuzzy` without expanding the core package.

Required contents:
- compatibility metadata
- pyproject metadata
- src package with exported modules
- exported recipe entrypoints
- eval fixtures
- tests

Validate a pack with `fuzzy.validate_pack_directory(...)`.
