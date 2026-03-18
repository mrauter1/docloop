from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evals import load_eval_suite


@dataclass(frozen=True)
class PackValidationResult:
    pack_name: str
    compatibility_path: Path
    pyproject_path: Path
    eval_suite_paths: tuple[Path, ...]
    export_paths: tuple[Path, ...]


def validate_pack_directory(path: str | Path) -> PackValidationResult:
    root = Path(path)
    if not root.exists():
        raise ValueError(f"Pack path does not exist: {root}")
    compatibility_path = root / "compatibility.json"
    if not compatibility_path.exists():
        raise ValueError(f"Pack is missing compatibility metadata: {compatibility_path}")
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        raise ValueError(f"Pack is missing package metadata: {pyproject_path}")
    payload = json.loads(compatibility_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("compatibility.json must be a JSON object")
    _require_string(payload, "name")
    _require_string(payload, "core_version")
    pyproject = _load_pyproject_metadata(pyproject_path)
    project_name = pyproject["name"]
    if project_name != str(payload["name"]):
        raise ValueError("compatibility.json name must match pyproject.toml project.name")
    exports = payload.get("exports")
    if not isinstance(exports, list) or not exports or not all(isinstance(item, str) and item.strip() for item in exports):
        raise ValueError("compatibility.json exports must be a non-empty list of strings")
    eval_suites = payload.get("eval_suites")
    if not isinstance(eval_suites, list) or not eval_suites or not all(isinstance(item, str) and item.strip() for item in eval_suites):
        raise ValueError("compatibility.json eval_suites must be a non-empty list of strings")
    tests_dir = root / "tests"
    if not tests_dir.exists():
        raise ValueError(f"Pack is missing tests directory: {tests_dir}")

    export_paths: list[Path] = []
    for export in exports:
        export_path = _resolve_export_path(root, export)
        if not export_path.exists():
            raise ValueError(f"Pack export does not exist: {export_path}")
        export_paths.append(export_path)

    eval_suite_paths: list[Path] = []
    for eval_suite in eval_suites:
        suite_path = root / eval_suite
        if not suite_path.exists():
            raise ValueError(f"Pack eval suite does not exist: {suite_path}")
        load_eval_suite(suite_path)
        eval_suite_paths.append(suite_path)

    return PackValidationResult(
        pack_name=str(payload["name"]),
        compatibility_path=compatibility_path,
        pyproject_path=pyproject_path,
        eval_suite_paths=tuple(eval_suite_paths),
        export_paths=tuple(export_paths),
    )


def _require_string(payload: dict[str, Any], key: str) -> None:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"compatibility.json {key!r} must be a non-empty string")


def _load_pyproject_metadata(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    project_section = _extract_toml_section(text, "project")
    name = _extract_toml_string(project_section, "name")
    version = _extract_toml_string(project_section, "version")
    requires_python = _extract_toml_string(project_section, "requires-python")
    return {
        "name": name,
        "version": version,
        "requires-python": requires_python,
    }


def _extract_toml_section(text: str, section: str) -> str:
    pattern = re.compile(rf"^\[{re.escape(section)}\]\s*$", re.MULTILINE)
    match = pattern.search(text)
    if match is None:
        raise ValueError(f"pyproject.toml is missing [{section}] section")
    start = match.end()
    next_section = re.search(r"^\[[^\]]+\]\s*$", text[start:], re.MULTILINE)
    end = start + next_section.start() if next_section is not None else len(text)
    return text[start:end]


def _extract_toml_string(section_text: str, key: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(['\"])(.*?)\1\s*(?:#.*)?$", re.MULTILINE)
    match = pattern.search(section_text)
    if match is None or not match.group(2).strip():
        raise ValueError(f"pyproject.toml project.{key} must be a non-empty string")
    return match.group(2).strip()


def _resolve_export_path(root: Path, export: str) -> Path:
    normalized_export = export.strip()
    if not normalized_export or normalized_export.startswith(".") or normalized_export.endswith(".") or ".." in normalized_export:
        raise ValueError(f"compatibility.json export is not a valid module path: {export!r}")
    relative_path = Path(*normalized_export.split("."))
    candidates = (
        root / "src" / relative_path.with_suffix(".py"),
        root / "src" / relative_path / "__init__.py",
        root / relative_path.with_suffix(".py"),
        root / relative_path / "__init__.py",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]
