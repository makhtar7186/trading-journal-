import contextlib
import logging
import uuid

from django.db import transaction

from apps.trades.models import Trade
from core.storage import StorageError, get_storage

from .images import InvalidImage, process_image, sanitize_filename
from .models import TradeScreenshot

logger = logging.getLogger(__name__)


class UploadRejected(Exception):
    """Un ou plusieurs fichiers sont refusés. `errors` : liste de (nom de fichier, message)."""

    def __init__(self, errors: list[tuple[str, str]]):
        self.errors = errors
        super().__init__("; ".join(f"{name} : {msg}" for name, msg in errors))


def new_storage_key(trade: Trade, ext: str) -> str:
    """Clé aléatoire et sûre : le nom du client n'y entre jamais."""
    return f"trades/{trade.pk}/{uuid.uuid4().hex}.{ext}"


def create_screenshots(
    *, trade: Trade, files: list, category: str, description: str = ""
) -> list[TradeScreenshot]:
    """Tout ou rien : si un fichier est refusé ou si une écriture échoue, rien n'est conservé."""
    processed = []
    errors: list[tuple[str, str]] = []
    for upload in files:
        name = sanitize_filename(getattr(upload, "name", None))
        try:
            processed.append((name, process_image(upload)))
        except InvalidImage as exc:
            errors.append((name, str(exc)))
    if errors:
        raise UploadRejected(errors)

    storage = get_storage()
    saved_keys: list[str] = []
    try:
        with transaction.atomic():
            created = []
            for name, image in processed:
                key = new_storage_key(trade, image.ext)
                storage.save(key, image.content, image.content_type)
                saved_keys.append(key)
                created.append(
                    TradeScreenshot.objects.create(
                        trade=trade,
                        storage_key=key,
                        original_filename=name,
                        category=category,
                        description=description,
                    )
                )
        return created
    except Exception:
        # Nettoyage des fichiers déjà écrits (la transaction DB est annulée par atomic).
        for key in saved_keys:
            with contextlib.suppress(StorageError):
                storage.delete(key)
        raise


def delete_stored_file(key: str) -> None:
    """Suppression du fichier ; une panne laisse au pire un fichier orphelin (journalisé)."""
    try:
        get_storage().delete(key)
    except Exception:
        logger.warning("Fichier de capture non supprimé du stockage : %s", key, exc_info=True)
