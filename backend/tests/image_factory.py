"""Fabrique d'images (et de faux fichiers) pour les tests d'upload."""
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def png_bytes(size=(12, 8), color=(200, 30, 30), mode="RGB") -> bytes:
    out = io.BytesIO()
    Image.new(mode, size, color if mode == "RGB" else None).save(out, format="PNG")
    return out.getvalue()


def jpeg_bytes(size=(12, 8), color=(30, 200, 30), exif=None, mode="RGB") -> bytes:
    out = io.BytesIO()
    kwargs = {"exif": exif} if exif is not None else {}
    Image.new(mode, size, color if mode == "RGB" else (0, 0, 0, 0)).save(out, format="JPEG", **kwargs)
    return out.getvalue()


def webp_bytes(size=(12, 8), color=(30, 30, 200)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, format="WEBP")
    return out.getvalue()


def gif_bytes() -> bytes:
    out = io.BytesIO()
    Image.new("P", (10, 10)).save(out, format="GIF")
    return out.getvalue()


def upload(name="capture.png", content=None, content_type="image/png"):
    return SimpleUploadedFile(name, content if content is not None else png_bytes(), content_type=content_type)


def exif_with_gps_and_orientation(orientation=1) -> bytes:
    exif = Image.Exif()
    exif[0x010F] = "AppareilSecret"  # Make
    exif[0x0112] = orientation
    exif.get_ifd(0x8825)[1] = "N"  # GPSLatitudeRef : présence d'un bloc GPS
    return exif.tobytes()
