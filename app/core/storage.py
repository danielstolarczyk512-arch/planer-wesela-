"""Magazyn plików za interfejsem: lokalny katalog (wolumen Dockera) albo S3-compatible.

Klucze generuje serwer (`weddings/{wedding_id}/{uuid}`), nigdy z nazwy pliku klienta.
"""

import re
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from app.core.config import get_settings
from app.core.ids import uuid7

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9/_-]{0,200}(\.part)?$")  # .part = przerwany zapis


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def delete_prefix(self, prefix: str) -> int: ...
    def list_keys(self, prefix: str) -> Iterator[tuple[str, datetime]]:
        """(klucz, czas modyfikacji UTC) — do sprzątania plików bez rekordu w bazie."""
        ...


def new_key(wedding_id: UUID) -> str:
    return f"weddings/{wedding_id}/{uuid7()}"


def wedding_prefix(wedding_id: UUID) -> str:
    return f"weddings/{wedding_id}"


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        if not _KEY_RE.match(key) or ".." in key:
            raise ValueError("Nieprawidłowy klucz pliku")
        path = (self.root / key).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError("Klucz poza katalogiem magazynu")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(path)  # zapis atomowy: brak połówek plików po awarii

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def delete_prefix(self, prefix: str) -> int:
        path = self._path(prefix)
        if not path.exists():
            return 0
        count = sum(1 for p in path.rglob("*") if p.is_file())
        shutil.rmtree(path)
        return count

    def list_keys(self, prefix: str) -> Iterator[tuple[str, datetime]]:
        path = self._path(prefix)
        if not path.exists():
            return
        for p in path.rglob("*"):
            if p.is_file():
                mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
                yield p.relative_to(self.root).as_posix(), mtime


class S3Storage:
    """Magazyn S3-compatible (np. dostawca w UE). Te same klucze co lokalnie.

    Szyfrowanie po stronie serwera (SSE) i blokada publicznego dostępu ustawiane są na
    kubełku (docs/wdrozenie.md). Kubełek nie może mieć publicznego odczytu: pliki zawsze
    przechodzą przez API z kontrolą uprawnień.
    """

    def __init__(self, bucket: str, client: "S3Client") -> None:
        self.bucket = bucket
        self.client = client

    @staticmethod
    def _check(key: str) -> str:
        if not _KEY_RE.match(key) or ".." in key:
            raise ValueError("Nieprawidłowy klucz pliku")
        return key

    def put(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=self._check(key), Body=data)

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=self._check(key))["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._check(key))

    def _objects(self, prefix: str) -> Iterator[tuple[str, datetime]]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self._check(prefix) + "/"):
            for o in page.get("Contents", []):
                yield o["Key"], o["LastModified"]

    def delete_prefix(self, prefix: str) -> int:
        keys = [key for key, _ in self._objects(prefix)]
        for i in range(0, len(keys), 1000):  # limit DeleteObjects: 1000 kluczy
            self.client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": k} for k in keys[i : i + 1000]], "Quiet": True},
            )
        return len(keys)

    def list_keys(self, prefix: str) -> Iterator[tuple[str, datetime]]:
        yield from self._objects(prefix)


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        import boto3

        secret = settings.s3_secret_access_key
        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=secret.get_secret_value() if secret else None,
        )
        return S3Storage(settings.s3_bucket or "", client)
    return LocalStorage(settings.storage_dir)
