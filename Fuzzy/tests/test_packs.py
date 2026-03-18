from __future__ import annotations

import json

import pytest

from fuzzy import validate_pack_directory


def test_validate_pack_directory_accepts_sample_support_pack():
    result = validate_pack_directory("domain_packs/support")

    assert result.pack_name == "fuzzy-support"
    assert result.compatibility_path.name == "compatibility.json"
    assert result.pyproject_path.name == "pyproject.toml"
    assert result.eval_suite_paths[0].name == "support_triage_suite.json"
    assert result.export_paths[0].name == "recipes.py"


def test_validate_pack_directory_rejects_missing_eval_suite(tmp_path):
    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()
    (pack_dir / "tests").mkdir()
    (pack_dir / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "broken-pack"',
                'version = "0.1.0"',
                'requires-python = ">=3.10"',
            ]
        ),
        encoding="utf-8",
    )
    (pack_dir / "compatibility.json").write_text(
        json.dumps(
            {
                "name": "broken-pack",
                "core_version": ">=0.1.0",
                "exports": ["broken.recipes"],
                "eval_suites": ["evals/missing.json"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        validate_pack_directory(pack_dir)

    assert "does not exist" in str(exc_info.value)


def test_validate_pack_directory_rejects_missing_pyproject(tmp_path):
    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()
    (pack_dir / "tests").mkdir()
    (pack_dir / "compatibility.json").write_text(
        json.dumps(
            {
                "name": "broken-pack",
                "core_version": ">=0.1.0",
                "exports": ["broken.recipes"],
                "eval_suites": ["evals/suite.json"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        validate_pack_directory(pack_dir)

    assert "pyproject.toml" in str(exc_info.value)


def test_validate_pack_directory_rejects_missing_export_module(tmp_path):
    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()
    (pack_dir / "tests").mkdir()
    (pack_dir / "evals").mkdir()
    (pack_dir / "evals" / "suite.json").write_text(
        json.dumps({"name": "suite", "cases": []}),
        encoding="utf-8",
    )
    (pack_dir / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "broken-pack"',
                'version = "0.1.0"',
                'requires-python = ">=3.10"',
            ]
        ),
        encoding="utf-8",
    )
    (pack_dir / "compatibility.json").write_text(
        json.dumps(
            {
                "name": "broken-pack",
                "core_version": ">=0.1.0",
                "exports": ["broken.recipes"],
                "eval_suites": ["evals/suite.json"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        validate_pack_directory(pack_dir)

    assert "Pack export does not exist" in str(exc_info.value)


def test_validate_pack_directory_accepts_single_quoted_pyproject_values(tmp_path):
    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()
    (pack_dir / "tests").mkdir()
    (pack_dir / "evals").mkdir()
    (pack_dir / "src").mkdir()
    (pack_dir / "src" / "quoted_pack.py").write_text("VALUE = True\n", encoding="utf-8")
    (pack_dir / "evals" / "suite.json").write_text(
        json.dumps({"name": "suite", "cases": []}),
        encoding="utf-8",
    )
    (pack_dir / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                "name = 'quoted-pack'  # comment",
                "version = '0.1.0'",
                "requires-python = '>=3.10'",
            ]
        ),
        encoding="utf-8",
    )
    (pack_dir / "compatibility.json").write_text(
        json.dumps(
            {
                "name": "quoted-pack",
                "core_version": ">=0.1.0",
                "exports": ["quoted_pack"],
                "eval_suites": ["evals/suite.json"],
            }
        ),
        encoding="utf-8",
    )

    result = validate_pack_directory(pack_dir)

    assert result.pack_name == "quoted-pack"


def test_validate_pack_directory_rejects_name_mismatch_between_pyproject_and_compatibility(tmp_path):
    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()
    (pack_dir / "tests").mkdir()
    (pack_dir / "evals").mkdir()
    (pack_dir / "src").mkdir()
    (pack_dir / "src" / "quoted_pack.py").write_text("VALUE = True\n", encoding="utf-8")
    (pack_dir / "evals" / "suite.json").write_text(
        json.dumps({"name": "suite", "cases": []}),
        encoding="utf-8",
    )
    (pack_dir / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "different-name"',
                'version = "0.1.0"',
                'requires-python = ">=3.10"',
            ]
        ),
        encoding="utf-8",
    )
    (pack_dir / "compatibility.json").write_text(
        json.dumps(
            {
                "name": "quoted-pack",
                "core_version": ">=0.1.0",
                "exports": ["quoted_pack"],
                "eval_suites": ["evals/suite.json"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        validate_pack_directory(pack_dir)

    assert "project.name" in str(exc_info.value)
