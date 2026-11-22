"""Validation et normalisation des images envoyées. Ne fait jamais confiance au client."""
import io
import os
import re
from dataclasses import dataclass

from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError

# Formats acceptés, identifiés par le CONTENU réel (pas l'extension ni le Content-Type déclaré).
# SVG est refusé volontairement : il peut embarquer du JavaScript (XSS).
ALLOWED_FORMATS = {
    "PNG": ("png", "image/png"),
    "JPEG": ("jpg", "image/jpeg"),
    "WEBP": ("webp", "image/webp"),
}
CONTENT_TYPE_BY_EXT = {ext: ctype for ext, ctype in ALLOWED_FORMATS.values()}


class InvalidImage(Exception):
    """Fichier refusé ; le message est destiné à l'utilisateur."""


@dataclass(frozen=True)
class ProcessedImage:
    content: bytes
    ext: str
    content_type: str
    width: int
    height: int


def sanitize_filename(name: str | None) -> str:
    """Nom d'origine conservé comme simple métadonnée d'affichage (jamais utilisé comme chemin)."""
    base = os.path.basename((name or "").replace("\\", "/"))
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip()
    return base[:255] or "capture"


def _megabytes(n: int) -> str:
    return f"{n / (1024 * 1024):g} Mo"


def process_image(upload) -> ProcessedImage:
    """Valide (taille, vrai format, dimensions, décodage complet) puis ré-encode l'image.

    Le ré-encodage supprime les métadonnées EXIF (GPS, appareil…) et tout contenu
    parasite ajouté après les données image. Seule la première image des fichiers animés est conservée.
    """
    max_bytes: int = settings.SCREENSHOT_MAX_BYTES
    max_pixels: int = settings.SCREENSHOT_MAX_PIXELS

    declared = getattr(upload, "size", None)
    if declared is not None and declared > max_bytes:
        raise InvalidImage(f"Fichier trop volumineux (maximum {_megabytes(max_bytes)}).")
    # On relit au plus max_bytes + 1 octets : la taille déclarée n'est pas une garantie.
    raw = upload.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise InvalidImage(f"Fichier trop volumineux (maximum {_megabytes(max_bytes)}).")
    if not raw:
        raise InvalidImage("Fichier vide.")

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            fmt = probe.format
            if fmt not in ALLOWED_FORMATS:
                raise InvalidImage("Format non pris en charge (PNG, JPEG ou WebP uniquement).")
            width, height = probe.size
            if width * height > max_pixels:
                raise InvalidImage("Image trop grande (dimensions excessives).")
            probe.load()  # décodage complet : détecte les fichiers tronqués ou corrompus
            image = ImageOps.exif_transpose(probe)  # applique l'orientation EXIF avant de la supprimer
            image.load()
            if fmt == "JPEG" and image.mode not in ("RGB", "L"):
                image = image.convert("RGB")  # ex. CMYK
            out = io.BytesIO()
            if fmt == "PNG":
                image.save(out, format="PNG")
            elif fmt == "JPEG":
                image.save(out, format="JPEG", quality=92)
            else:
                image.save(out, format="WEBP", quality=92)
            width, height = image.size
    except InvalidImage:
        raise
    except Image.DecompressionBombError as exc:
        raise InvalidImage("Image trop grande (dimensions excessives).") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError) as exc:
        raise InvalidImage("Fichier illisible ou corrompu : ce n'est pas une image valide.") from exc

    ext, content_type = ALLOWED_FORMATS[fmt]
    return ProcessedImage(out.getvalue(), ext, content_type, width, height)
