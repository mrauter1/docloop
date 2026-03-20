from __future__ import annotations

from pathlib import Path

import pytest

from shared.config import ConfigError, Settings


def test_settings_from_env_applies_required_defaults() -> None:
    settings = Settings.from_env(
        {
            "APP_BASE_URL": "http://localhost:8000",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": "postgresql+psycopg://triage:triage@localhost/triage",
            "CODEX_API_KEY": "codex-secret",
        }
    )

    assert settings.uploads_dir.as_posix() == "/opt/triage/data/uploads"
    assert settings.triage_workspace_dir.as_posix() == "/opt/triage/triage_workspace"
    assert settings.repo_mount_dir.as_posix() == "/opt/triage/triage_workspace/app"
    assert settings.manuals_mount_dir.as_posix() == "/opt/triage/triage_workspace/manuals"
    assert settings.max_images_per_message == 3
    assert settings.max_image_bytes == 5 * 1024 * 1024
    assert settings.session_remember_days == 30


def test_settings_require_core_secrets_database_url_and_codex_key() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env({"APP_BASE_URL": "http://localhost:8000"})


def test_settings_derive_repo_and_manual_paths_from_workspace_override() -> None:
    settings = Settings.from_env(
        {
            "APP_BASE_URL": "http://localhost:8000",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": "postgresql+psycopg://triage:triage@localhost/triage",
            "CODEX_API_KEY": "codex-secret",
            "TRIAGE_WORKSPACE_DIR": "/srv/triage/workspace",
        }
    )

    assert settings.repo_mount_dir == Path("/srv/triage/workspace/app")
    assert settings.manuals_mount_dir == Path("/srv/triage/workspace/manuals")


def test_settings_validate_confidence_bounds() -> None:
    with pytest.raises(ConfigError):
        Settings.from_env(
            {
                "APP_BASE_URL": "http://localhost:8000",
                "APP_SECRET_KEY": "secret",
                "DATABASE_URL": "postgresql+psycopg://triage:triage@localhost/triage",
                "CODEX_API_KEY": "codex-secret",
                "AUTO_SUPPORT_REPLY_MIN_CONFIDENCE": "1.1",
            }
        )


def test_env_example_documents_all_required_inputs() -> None:
    env_example = (
        Path(__file__).resolve().parent.parent / ".env.example"
    ).read_text()

    for variable in (
        "APP_BASE_URL",
        "APP_SECRET_KEY",
        "DATABASE_URL",
        "CODEX_API_KEY",
        "TRIAGE_WORKSPACE_DIR",
        "REPO_MOUNT_DIR",
        "MANUALS_MOUNT_DIR",
    ):
        assert f"{variable}=" in env_example
