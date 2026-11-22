"""Interface de stockage de fichiers. Le code métier ne connaît aucun fournisseur."""
from typing import BinaryIO, Protocol


class StorageError(Exception):
    """Échec d'écriture/lecture dans le stockage."""


class FileNotFoundInStorage(StorageError):
    pass


class Storage(Protocol):
    def save(self, key: str, content: bytes, content_type: str) -> None:
        """Écrit le fichier. Lève StorageError en cas d'échec."""

    def open(self, key: str) -> BinaryIO:
        """Ouvre le fichier en lecture. Lève FileNotFoundInStorage s'il n'existe pas."""

    def delete(self, key: str) -> None:
        """Supprime le fichier ; sans erreur s'il n'existe déjà plus."""

    def signed_url(self, key: str, expires_in: int = 60) -> str | None:
        """URL temporaire d'accès direct (S3), ou None si le fichier doit transiter par l'application."""
