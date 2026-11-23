from pathlib import Path

from django.db.models import Sum
from PIL import Image
from rest_framework.exceptions import ValidationError

from .models import Document, Product

DOCUMENT_MAX_BYTES = 50 * 1024 * 1024
ASSET_PHOTO_MAX_BYTES = 10 * 1024 * 1024
COMPANY_STORAGE_LIMIT_BYTES = 5 * 1024 * 1024 * 1024

EXTENSIONS = {
    "pdf": {"application/pdf"},
    "doc": {"application/msword"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "xls": {"application/vnd.ms-excel"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    "csv": {"text/csv", "application/csv", "text/plain"},
    "txt": {"text/plain"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "png": {"image/png"},
    "webp": {"image/webp"},
    "ppt": {"application/vnd.ms-powerpoint"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    "zip": {"application/zip", "application/x-zip-compressed"},
}

PHOTO_EXTENSIONS = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                    "webp": "image/webp"}
PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}


def sanitize_filename(name):
    cleaned = Path(str(name or "archivo")).name
    cleaned = "".join(char for char in cleaned if char.isprintable())
    return cleaned[:255] or "archivo"


def _head(upload, size=12):
    upload.seek(0)
    head = upload.read(size)
    upload.seek(0)
    return head


def _matches_signature(extension, head):
    if extension == "pdf":
        return head.startswith(b"%PDF-")
    if extension in {"docx", "xlsx", "pptx", "zip"}:
        return head.startswith(b"PK\x03\x04")
    if extension in {"doc", "xls", "ppt"}:
        return head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if extension in {"jpg", "jpeg"}:
        return head.startswith(b"\xff\xd8\xff")
    if extension == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == "webp":
        return head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    return True


def validate_document(upload):
    if upload is None or upload.size <= 0:
        raise ValidationError({"file": "El archivo está vacío."})
    if upload.size > DOCUMENT_MAX_BYTES:
        raise ValidationError({"file": "El archivo no puede superar 50 MB."})
    original = sanitize_filename(upload.name)
    extension = Path(original).suffix.lower().lstrip(".")
    if extension not in EXTENSIONS:
        raise ValidationError({"file": "Formato no permitido."})
    declared = (getattr(upload, "content_type", "") or "").lower()
    if declared and declared not in EXTENSIONS[extension]:
        raise ValidationError({"file": "El tipo declarado no coincide con el formato."})
    if not _matches_signature(extension, _head(upload)):
        raise ValidationError({"file": "El contenido no coincide con el formato."})
    return original


def validate_asset_photo(upload):
    if upload is None or upload.size <= 0:
        raise ValidationError({"photo": "La foto está vacía."})
    if upload.size > ASSET_PHOTO_MAX_BYTES:
        raise ValidationError({"photo": "La foto no puede superar 10 MB."})
    original = sanitize_filename(upload.name)
    extension = Path(original).suffix.lower().lstrip(".")
    if extension not in PHOTO_EXTENSIONS:
        raise ValidationError({"photo": "La foto debe ser PNG, JPEG o WebP."})
    try:
        image = Image.open(upload)
        image_format = image.format
        image.verify()
    except Exception:
        raise ValidationError({"photo": "La foto debe ser una imagen válida."})
    finally:
        upload.seek(0)
    if image_format not in PHOTO_FORMATS:
        raise ValidationError({"photo": "La foto debe ser PNG, JPEG o WebP."})
    return original


def storage_usage(company):
    documents_bytes = Document.objects.filter(company=company).aggregate(
        total=Sum("size"),
    )["total"] or 0
    photos_bytes = Product.objects.filter(company=company).aggregate(
        total=Sum("photo_size"),
    )["total"] or 0
    return {
        "used_bytes": int(documents_bytes) + int(photos_bytes),
        "limit_bytes": COMPANY_STORAGE_LIMIT_BYTES,
        "documents_bytes": int(documents_bytes),
        "photos_bytes": int(photos_bytes),
        "document_count": Document.objects.filter(company=company).count(),
        "asset_photo_count": Product.objects.filter(
            company=company, kind=Product.Kind.ASSET, photo__gt="",
        ).count(),
    }
