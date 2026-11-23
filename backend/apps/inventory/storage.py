import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage

private_storage = FileSystemStorage(
    location=settings.PRIVATE_MEDIA_ROOT,
    base_url=None,
)


def _suffix(filename):
    return Path(filename).suffix.lower()


def document_upload_path(instance, filename):
    return f"documents/{instance.company_id}/{uuid.uuid4().hex}{_suffix(filename)}"


def asset_photo_upload_path(instance, filename):
    return f"assets/{instance.company_id}/{uuid.uuid4().hex}{_suffix(filename)}"
