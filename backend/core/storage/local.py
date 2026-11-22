from pathlib import Path
from typing import BinaryIO

from .base import FileNotFoundInStorage, StorageError


class LocalStorage:
    """Stockage sur disque (développement). Les fichiers ne sont jamais servis statiquement."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        # Défense en profondeur : les clés sont générées côté serveur, mais on refuse toute évasion.
        path = (self.root / key).resolve()
        if self.root != path and self.root not in path.parents:
            raise StorageError("Clé de stockage invalide.")
        return path

    def save(self, key: str, content: bytes, content_type: str) -> None:
        path = self._path(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        except OSError as exc:
            raise StorageError("Écriture impossible.") from exc

    def open(self, key: str) -> BinaryIO:
        path = self._path(key)
        try:
            return path.open("rb")
        except FileNotFoundError as exc:
            raise FileNotFoundInStorage(key) from exc
        except OSError as exc:
            raise StorageError("Lecture impossible.") from exc

    def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError("Suppression impossible.") from exc
        # Retire les dossiers devenus vides (un par trade), sans jamais toucher à la racine.
        parent = path.parent
        while parent != self.root and self.root in parent.parents:
            try:
                parent.rmdir()  # échoue (sans effet) si le dossier n'est pas vide
            except OSError:
                break
            parent = parent.parent

    def signed_url(self, key: str, expires_in: int = 60) -> str | None:
        return None
