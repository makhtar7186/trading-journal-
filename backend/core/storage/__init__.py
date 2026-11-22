from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .base import FileNotFoundInStorage, Storage, StorageError

__all__ = ["FileNotFoundInStorage", "Storage", "StorageError", "get_storage"]


def get_storage() -> Storage:
    """Choisit l'implémentation selon STORAGE_BACKEND (local | s3). Lu à chaque appel (testable)."""
    backend = settings.STORAGE_BACKEND
    if backend == "local":
        from .local import LocalStorage

        return LocalStorage(settings.STORAGE_LOCAL_ROOT)
    if backend == "s3":
        from .s3 import S3Storage

        if not settings.S3_BUCKET:
            raise ImproperlyConfigured("S3_BUCKET est requis quand STORAGE_BACKEND=s3.")
        return S3Storage(
            bucket=settings.S3_BUCKET,
            endpoint_url=settings.S3_ENDPOINT_URL,
            access_key_id=settings.S3_ACCESS_KEY_ID,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
        )
    raise ImproperlyConfigured(f"STORAGE_BACKEND inconnu : {backend!r} (attendu : local ou s3).")
