from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import hashlib
import uuid

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from starlette.datastructures import FormData, UploadFile as StarletteUploadFile

from shared.config import Settings
from shared.models import AttachmentVisibility, TicketAttachment


ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
}


class UploadValidationError(ValueError):
    """Raised when an uploaded file violates Stage 1 rules."""


@dataclass(frozen=True)
class ValidatedImageUpload:
    attachment_id: uuid.UUID
    original_filename: str
    mime_type: str
    data: bytes
    sha256: str
    size_bytes: int
    width: int
    height: int
    suffix: str


def extract_upload_files(form: FormData, *, field_name: str = "attachments") -> list[UploadFile]:
    files: list[UploadFile] = []
    for value in form.getlist(field_name):
        if isinstance(value, (UploadFile, StarletteUploadFile)) and value.filename:
            files.append(value)
    return files


async def validate_public_image_uploads(
    form: FormData,
    settings: Settings,
    *,
    field_name: str = "attachments",
) -> list[ValidatedImageUpload]:
    files = extract_upload_files(form, field_name=field_name)
    if len(files) > settings.max_images_per_message:
        raise UploadValidationError(
            f"You can upload at most {settings.max_images_per_message} images per message."
        )

    validated: list[ValidatedImageUpload] = []
    for upload in files:
        mime_type = (upload.content_type or "").lower()
        suffix = ALLOWED_IMAGE_TYPES.get(mime_type)
        if suffix is None:
            raise UploadValidationError("Only PNG and JPEG images are allowed.")

        data = await upload.read()
        await upload.close()
        size_bytes = len(data)
        if size_bytes > settings.max_image_bytes:
            raise UploadValidationError(
                f"Each image must be {settings.max_image_bytes} bytes or smaller."
            )
        if size_bytes == 0:
            raise UploadValidationError("Uploaded images must not be empty.")

        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
            with Image.open(BytesIO(data)) as image:
                width, height = image.size
        except (UnidentifiedImageError, OSError) as exc:
            raise UploadValidationError("Uploaded files must be valid images.") from exc

        validated.append(
            ValidatedImageUpload(
                attachment_id=uuid.uuid4(),
                original_filename=upload.filename or "image",
                mime_type=mime_type,
                data=data,
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=size_bytes,
                width=width,
                height=height,
                suffix=suffix,
            )
        )
    return validated


def persist_validated_uploads(
    uploads: list[ValidatedImageUpload],
    *,
    uploads_dir: Path,
    ticket_id: uuid.UUID,
    message_id: uuid.UUID,
) -> tuple[list[TicketAttachment], list[Path]]:
    attachments: list[TicketAttachment] = []
    written_paths: list[Path] = []

    target_dir = uploads_dir / str(ticket_id) / str(message_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    for upload in uploads:
        stored_path = target_dir / f"{upload.attachment_id}{upload.suffix}"
        with stored_path.open("wb") as handle:
            handle.write(upload.data)
        written_paths.append(stored_path)
        attachments.append(
            TicketAttachment(
                id=upload.attachment_id,
                ticket_id=ticket_id,
                message_id=message_id,
                visibility=AttachmentVisibility.PUBLIC.value,
                original_filename=upload.original_filename,
                stored_path=str(stored_path),
                mime_type=upload.mime_type,
                sha256=upload.sha256,
                size_bytes=upload.size_bytes,
                width=upload.width,
                height=upload.height,
            )
        )
    return attachments, written_paths


def cleanup_written_uploads(paths: list[Path]) -> None:
    for path in reversed(paths):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue
        parent = path.parent
        while parent.name and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
