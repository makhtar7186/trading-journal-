import io
from typing import BinaryIO

from .base import FileNotFoundInStorage, StorageError


class S3Storage:
    """Stockage S3 compatible (AWS, MinIO, Scaleway, R2…). Bucket privé, accès par URL signée."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        region_name: str | None = None,
        client=None,
    ):
        if client is None:
            import boto3  # import tardif : inutile en développement local

            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url or None,
                aws_access_key_id=access_key_id or None,
                aws_secret_access_key=secret_access_key or None,
                region_name=region_name or None,
            )
        self.bucket = bucket
        self.client = client

    def save(self, key: str, content: bytes, content_type: str) -> None:
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=key, Body=content, ContentType=content_type
            )
        except Exception as exc:  # botocore lève de nombreux types d'erreurs
            raise StorageError("Écriture impossible.") from exc

    def open(self, key: str) -> BinaryIO:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return io.BytesIO(response["Body"].read())
        except self.client.exceptions.NoSuchKey as exc:
            raise FileNotFoundInStorage(key) from exc
        except Exception as exc:
            raise StorageError("Lecture impossible.") from exc

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)  # idempotent côté S3
        except Exception as exc:
            raise StorageError("Suppression impossible.") from exc

    def signed_url(self, key: str, expires_in: int = 60) -> str | None:
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except Exception as exc:
            raise StorageError("Génération d'URL impossible.") from exc
