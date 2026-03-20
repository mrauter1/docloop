from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Mapping


class ConfigError(ValueError):
    """Raised when required environment configuration is missing or invalid."""


DEFAULT_UPLOADS_DIR = Path("/opt/triage/data/uploads")
DEFAULT_TRIAGE_WORKSPACE_DIR = Path("/opt/triage/triage_workspace")
DEFAULT_REPO_DIRNAME = "app"
DEFAULT_MANUALS_DIRNAME = "manuals"

REQUIRED_ENV_VARS = (
    "APP_BASE_URL",
    "APP_SECRET_KEY",
    "DATABASE_URL",
    "CODEX_API_KEY",
)


def _coerce_int(name: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _coerce_float(name: str, value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc


@dataclass(frozen=True)
class Settings:
    app_base_url: str
    app_secret_key: str
    database_url: str
    codex_api_key: str
    uploads_dir: Path = DEFAULT_UPLOADS_DIR
    triage_workspace_dir: Path = DEFAULT_TRIAGE_WORKSPACE_DIR
    repo_mount_dir: Path = DEFAULT_TRIAGE_WORKSPACE_DIR / DEFAULT_REPO_DIRNAME
    manuals_mount_dir: Path = DEFAULT_TRIAGE_WORKSPACE_DIR / DEFAULT_MANUALS_DIRNAME
    codex_bin: str = "codex"
    codex_model: str | None = None
    codex_timeout_seconds: int = 75
    worker_poll_seconds: int = 10
    auto_support_reply_min_confidence: float = 0.85
    auto_confirm_intent_min_confidence: float = 0.90
    max_images_per_message: int = 3
    max_image_bytes: int = 5 * 1024 * 1024
    session_default_hours: int = 12
    session_remember_days: int = 30

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        values = dict(os.environ if env is None else env)
        missing = [key for key in REQUIRED_ENV_VARS if not values.get(key)]
        if missing:
            joined = ", ".join(sorted(missing))
            raise ConfigError(f"Missing required environment variables: {joined}")

        codex_model = values.get("CODEX_MODEL") or None
        triage_workspace_dir = Path(
            values.get("TRIAGE_WORKSPACE_DIR", str(DEFAULT_TRIAGE_WORKSPACE_DIR))
        )
        repo_mount_dir = Path(
            values.get("REPO_MOUNT_DIR", str(triage_workspace_dir / DEFAULT_REPO_DIRNAME))
        )
        manuals_mount_dir = Path(
            values.get("MANUALS_MOUNT_DIR", str(triage_workspace_dir / DEFAULT_MANUALS_DIRNAME))
        )

        settings = cls(
            app_base_url=values["APP_BASE_URL"],
            app_secret_key=values["APP_SECRET_KEY"],
            database_url=values["DATABASE_URL"],
            codex_api_key=values["CODEX_API_KEY"],
            uploads_dir=Path(values.get("UPLOADS_DIR", str(DEFAULT_UPLOADS_DIR))),
            triage_workspace_dir=triage_workspace_dir,
            repo_mount_dir=repo_mount_dir,
            manuals_mount_dir=manuals_mount_dir,
            codex_bin=values.get("CODEX_BIN", "codex"),
            codex_model=codex_model,
            codex_timeout_seconds=_coerce_int(
                "CODEX_TIMEOUT_SECONDS", values.get("CODEX_TIMEOUT_SECONDS", "75")
            ),
            worker_poll_seconds=_coerce_int(
                "WORKER_POLL_SECONDS", values.get("WORKER_POLL_SECONDS", "10")
            ),
            auto_support_reply_min_confidence=_coerce_float(
                "AUTO_SUPPORT_REPLY_MIN_CONFIDENCE",
                values.get("AUTO_SUPPORT_REPLY_MIN_CONFIDENCE", "0.85"),
            ),
            auto_confirm_intent_min_confidence=_coerce_float(
                "AUTO_CONFIRM_INTENT_MIN_CONFIDENCE",
                values.get("AUTO_CONFIRM_INTENT_MIN_CONFIDENCE", "0.90"),
            ),
            max_images_per_message=_coerce_int(
                "MAX_IMAGES_PER_MESSAGE", values.get("MAX_IMAGES_PER_MESSAGE", "3")
            ),
            max_image_bytes=_coerce_int(
                "MAX_IMAGE_BYTES", values.get("MAX_IMAGE_BYTES", str(5 * 1024 * 1024))
            ),
            session_default_hours=_coerce_int(
                "SESSION_DEFAULT_HOURS", values.get("SESSION_DEFAULT_HOURS", "12")
            ),
            session_remember_days=_coerce_int(
                "SESSION_REMEMBER_DAYS", values.get("SESSION_REMEMBER_DAYS", "30")
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.max_images_per_message <= 0:
            raise ConfigError("MAX_IMAGES_PER_MESSAGE must be greater than zero")
        if self.max_image_bytes <= 0:
            raise ConfigError("MAX_IMAGE_BYTES must be greater than zero")
        if self.session_default_hours <= 0:
            raise ConfigError("SESSION_DEFAULT_HOURS must be greater than zero")
        if self.session_remember_days <= 0:
            raise ConfigError("SESSION_REMEMBER_DAYS must be greater than zero")
        if self.worker_poll_seconds <= 0:
            raise ConfigError("WORKER_POLL_SECONDS must be greater than zero")
        if self.codex_timeout_seconds <= 0:
            raise ConfigError("CODEX_TIMEOUT_SECONDS must be greater than zero")
        if not self.app_base_url.strip():
            raise ConfigError("APP_BASE_URL must not be blank")
        if not self.app_secret_key.strip():
            raise ConfigError("APP_SECRET_KEY must not be blank")
        if not self.database_url.strip():
            raise ConfigError("DATABASE_URL must not be blank")
        if not self.codex_api_key.strip():
            raise ConfigError("CODEX_API_KEY must not be blank")
        for name, value in (
            ("AUTO_SUPPORT_REPLY_MIN_CONFIDENCE", self.auto_support_reply_min_confidence),
            (
                "AUTO_CONFIRM_INTENT_MIN_CONFIDENCE",
                self.auto_confirm_intent_min_confidence,
            ),
        ):
            if not 0.0 <= value <= 1.0:
                raise ConfigError(f"{name} must be between 0.0 and 1.0")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
