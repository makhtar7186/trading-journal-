"""Chiffrement des secrets au repos avec DPAPI Windows (lié au compte Windows de l'utilisateur).

Un autre utilisateur de l'ordinateur, ou le même fichier copié sur une autre machine, ne peut pas relire les secrets.
Aucune dépendance externe (ctypes).
"""
import base64
import ctypes
import sys
from ctypes import wintypes

_ENTROPY = b"TradingJournal/config/v1"
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _Blob:
    buffer = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


def _require_windows() -> None:
    if sys.platform != "win32":
        raise OSError("DPAPI n'est disponible que sous Windows.")


def protect(secret: str) -> str:
    """Texte → chaîne base64 chiffrée (à stocker dans config.json)."""
    _require_windows()
    (blob_in, _keep_a), (blob_entropy, _keep_b) = _blob(secret.encode("utf-8")), _blob(_ENTROPY)
    blob_out = _Blob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, ctypes.byref(blob_entropy), None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out)
    ):
        raise OSError("Chiffrement DPAPI impossible.")
    try:
        return base64.b64encode(ctypes.string_at(blob_out.pbData, blob_out.cbData)).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def unprotect(token: str) -> str:
    """Inverse de protect(). Lève ValueError si le secret ne peut pas être relu (autre compte, fichier altéré)."""
    _require_windows()
    try:
        raw = base64.b64decode(token.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValueError("Secret illisible.") from exc
    (blob_in, _keep_a), (blob_entropy, _keep_b) = _blob(raw), _blob(_ENTROPY)
    blob_out = _Blob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, ctypes.byref(blob_entropy), None, None, _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out)
    ):
        raise ValueError("Secret illisible (autre compte Windows ou fichier altéré).")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
