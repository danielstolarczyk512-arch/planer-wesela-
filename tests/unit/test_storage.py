"""Magazyn plików: lokalny i S3 (moto, bez sieci) muszą zachowywać się tak samo."""

from datetime import UTC, datetime, timedelta

import boto3
import pytest
from moto import mock_aws

from app.core.storage import LocalStorage, S3Storage


@pytest.fixture(params=["local", "s3"])
def storage(request, tmp_path):
    if request.param == "local":
        yield LocalStorage(tmp_path)
        return
    with mock_aws():
        client = boto3.client("s3", region_name="eu-central-1")
        client.create_bucket(
            Bucket="wesela", CreateBucketConfiguration={"LocationConstraint": "eu-central-1"}
        )
        yield S3Storage("wesela", client)


def test_put_get_list_delete(storage):
    storage.put("weddings/a/1", b"jeden")
    storage.put("weddings/a/2", b"dwa")
    storage.put("weddings/b/1", b"inne wesele")
    assert storage.get("weddings/a/1") == b"jeden"
    keys = dict(storage.list_keys("weddings/a"))
    assert set(keys) == {"weddings/a/1", "weddings/a/2"}
    now = datetime.now(UTC)
    assert all(now - timedelta(minutes=5) < t <= now + timedelta(minutes=5) for t in keys.values())

    storage.delete("weddings/a/1")
    assert set(dict(storage.list_keys("weddings/a"))) == {"weddings/a/2"}
    assert storage.delete_prefix("weddings/a") == 1
    assert list(storage.list_keys("weddings/a")) == []
    assert storage.get("weddings/b/1") == b"inne wesele"  # inny prefiks nietknięty
    assert storage.delete_prefix("weddings/brak") == 0


@pytest.mark.parametrize("key", ["../etc/passwd", "weddings/../x", "/abs", "Duze/Litery", ""])
def test_rejects_unsafe_keys(storage, key):
    with pytest.raises(ValueError, match="klucz"):
        storage.put(key, b"x")


def test_s3_prefix_does_not_match_longer_names():
    with mock_aws():
        client = boto3.client("s3", region_name="eu-central-1")
        client.create_bucket(
            Bucket="wesela", CreateBucketConfiguration={"LocationConstraint": "eu-central-1"}
        )
        s3 = S3Storage("wesela", client)
        s3.put("weddings/a1/x", b"1")
        s3.put("weddings/a/x", b"2")
        assert s3.delete_prefix("weddings/a") == 1  # nie usuwa weddings/a1/…
        assert s3.get("weddings/a1/x") == b"1"
