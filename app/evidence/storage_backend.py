from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredObject:
    backend: str
    storage_path: str
    size_bytes: int


class EvidenceStorageBackend(ABC):
    name: str

    @abstractmethod
    def put_bytes(self, *, storage_path: str, content: bytes, content_type: str) -> StoredObject:
        pass

    @abstractmethod
    def get_bytes(self, *, storage_path: str) -> bytes:
        pass


class LocalFileStorageBackend(EvidenceStorageBackend):
    name = "local"

    def __init__(self, root_path: str) -> None:
        self.root_path = Path(root_path)

    def put_bytes(self, *, storage_path: str, content: bytes, content_type: str) -> StoredObject:
        destination = self._resolve(storage_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(f"Evidence object already exists: {storage_path}")

        destination.write_bytes(content)
        return StoredObject(
            backend=self.name,
            storage_path=storage_path,
            size_bytes=len(content),
        )

    def get_bytes(self, *, storage_path: str) -> bytes:
        return self._resolve(storage_path).read_bytes()

    def _resolve(self, storage_path: str) -> Path:
        relative_path = Path(storage_path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("Evidence storage path must be relative")
        return self.root_path / relative_path


class S3StorageBackend(EvidenceStorageBackend):
    name = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str = "",
        endpoint_url: str | None = None,
        region_name: str | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("S3 evidence storage requires a bucket")

        import boto3

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.client = boto3.client(
            "s3", endpoint_url=endpoint_url or None, region_name=region_name or None
        )

    def put_bytes(self, *, storage_path: str, content: bytes, content_type: str) -> StoredObject:
        key = self._key(storage_path)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except self.client.exceptions.ClientError as exc:
            status_code = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status_code != 404:
                raise
        else:
            raise FileExistsError(f"Evidence object already exists: {storage_path}")

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            Metadata={"immutable": "true"},
        )
        return StoredObject(
            backend=self.name,
            storage_path=f"s3://{self.bucket}/{key}",
            size_bytes=len(content),
        )

    def get_bytes(self, *, storage_path: str) -> bytes:
        key = storage_path
        prefix = f"s3://{self.bucket}/"
        if storage_path.startswith(prefix):
            key = storage_path[len(prefix) :]

        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def _key(self, storage_path: str) -> str:
        clean_path = storage_path.strip("/")
        if self.prefix:
            return f"{self.prefix}/{clean_path}"
        return clean_path
