from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath

from .models import PolicyResult, PolicySpec, WorkspaceSnapshot


def snapshot_workspace(workspace: Path, ignored_paths: set[str] | None = None) -> WorkspaceSnapshot:
    root = workspace.resolve()
    entries: dict[str, tuple[str, str]] = {}
    escape_paths: set[str] = set()
    ignored = {path.strip("/") for path in (ignored_paths or set()) if path}

    for current_root, dirnames, filenames in os.walk(workspace, topdown=True, followlinks=False):
        current_path = Path(current_root)
        rel_root = current_path.relative_to(workspace)
        rel_root_str = "" if rel_root == Path(".") else rel_root.as_posix()
        if _is_ignored(rel_root_str, ignored):
            dirnames[:] = []
            continue
        dirnames[:] = [
            name
            for name in dirnames
            if not _is_ignored(name if rel_root == Path(".") else (rel_root / name).as_posix(), ignored)
        ]

        for name in sorted(dirnames + filenames):
            path = current_path / name
            rel_path = name if rel_root == Path(".") else (rel_root / name).as_posix()
            if not rel_path or _is_ignored(rel_path, ignored):
                continue
            try:
                resolved = path.resolve(strict=False)
                resolved.relative_to(root)
            except ValueError:
                escape_paths.add(rel_path)
            entries[rel_path] = _stat_signature(path)
    return WorkspaceSnapshot(entries=entries, escape_paths=escape_paths)


def evaluate_policy(
    before: WorkspaceSnapshot,
    after: WorkspaceSnapshot,
    policy: PolicySpec | None,
    workspace: Path | None = None,
) -> PolicyResult:
    changed_paths = sorted(
        {
            path
            for path in set(before.entries) | set(after.entries)
            if before.entries.get(path) != after.entries.get(path)
        }
    )
    violations: list[str] = []
    for escape_path in sorted(before.escape_paths | after.escape_paths):
        if escape_path in changed_paths:
            violations.append(f"{escape_path}: resolves outside workspace")

    if policy:
        for path in changed_paths:
            if policy.forbid_write and _matches_any(path, policy.forbid_write):
                violations.append(f"{path}: matches forbid_write")
                continue
            if policy.allow_write and not _matches_any(path, policy.allow_write):
                violations.append(f"{path}: not allowed by allow_write")

    required_files_missing: list[str] = []
    if policy and workspace and policy.required_files:
        for required in policy.required_files:
            if not (workspace / required).exists():
                required_files_missing.append(required)

    return PolicyResult(
        changed_paths=changed_paths,
        violations=violations,
        required_files_missing=required_files_missing,
    )


def _stat_signature(path: Path) -> tuple[str, str]:
    if path.is_symlink():
        return ("symlink", os.readlink(path))
    if path.is_dir():
        return ("dir", "")
    digest = hashlib.sha1(path.read_bytes()).hexdigest()
    return ("file", digest)


def _matches_any(path: str, patterns: list[str]) -> bool:
    pure = PurePosixPath(path)
    return any(pure.match(pattern) or path == pattern for pattern in patterns)


def _is_ignored(path: str, ignored_paths: set[str]) -> bool:
    normalized = path.strip("/")
    if not normalized:
        return False
    return any(normalized == ignored or normalized.startswith(f"{ignored}/") for ignored in ignored_paths)
