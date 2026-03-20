from __future__ import annotations

import asyncio
from io import BytesIO

from PIL import Image
import pytest
from starlette.datastructures import FormData, Headers, UploadFile

from app.uploads import UploadValidationError, validate_public_image_uploads
from shared.config import Settings


def make_settings(*, max_images_per_message: int = 3, max_image_bytes: int = 5 * 1024 * 1024) -> Settings:
    return Settings.from_env(
        {
            "APP_BASE_URL": "http://testserver",
            "APP_SECRET_KEY": "secret",
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "CODEX_API_KEY": "codex-secret",
            "MAX_IMAGES_PER_MESSAGE": str(max_images_per_message),
            "MAX_IMAGE_BYTES": str(max_image_bytes),
        }
    )


def make_png_bytes(color: str = "red") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def make_upload(filename: str, data: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_validate_public_image_uploads_rejects_more_than_max_files() -> None:
    settings = make_settings(max_images_per_message=3)
    form = FormData(
        [
            ("attachments", make_upload("1.png", make_png_bytes("red"), "image/png")),
            ("attachments", make_upload("2.png", make_png_bytes("green"), "image/png")),
            ("attachments", make_upload("3.png", make_png_bytes("blue"), "image/png")),
            ("attachments", make_upload("4.png", make_png_bytes("yellow"), "image/png")),
        ]
    )

    with pytest.raises(UploadValidationError, match="at most 3 images"):
        asyncio.run(validate_public_image_uploads(form, settings))


def test_validate_public_image_uploads_rejects_files_over_size_limit() -> None:
    settings = make_settings(max_image_bytes=10)
    form = FormData(
        [
            ("attachments", make_upload("large.png", b"x" * 11, "image/png")),
        ]
    )

    with pytest.raises(UploadValidationError, match="10 bytes or smaller"):
        asyncio.run(validate_public_image_uploads(form, settings))
