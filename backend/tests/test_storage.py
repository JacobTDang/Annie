"""Tests for the pluggable storage backend (Item #15)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from renderer.storage import (
    LocalStorageBackend,
    S3StorageBackend,
    build_default_storage,
)


# ─────────────────────────────────────────────────────────────────────────────
# Local backend
# ─────────────────────────────────────────────────────────────────────────────


def test_local_put_copies_file_and_returns_url(tmp_path):
    base = tmp_path / "lessons"
    src = tmp_path / "input.mp4"
    src.write_bytes(b"\x00\x00\x00mp4")

    be = LocalStorageBackend(str(base), url_prefix="/media/lessons")
    url = be.put(str(src), "abc.mp4")

    assert (base / "abc.mp4").exists()
    assert url == "/media/lessons/abc.mp4"


def test_local_url_uses_posix_slashes(tmp_path):
    """Even on Windows the URL must use forward slashes."""
    be = LocalStorageBackend(str(tmp_path), url_prefix="/media")
    assert be.url_for("sub/dir/x.mp4") == "/media/sub/dir/x.mp4"


def test_local_exists_returns_true_after_put(tmp_path):
    src = tmp_path / "src.mp4"
    src.write_bytes(b"x")
    be = LocalStorageBackend(str(tmp_path / "out"))
    be.put(str(src), "video.mp4")
    assert be.exists("video.mp4") is True
    assert be.exists("missing.mp4") is False


def test_local_put_no_op_when_source_equals_destination(tmp_path):
    """If the source file already lives in the backend dir, don't try to
    copy onto itself (would raise SameFileError)."""
    base = tmp_path / "lessons"
    base.mkdir()
    src = base / "already.mp4"
    src.write_bytes(b"x")
    be = LocalStorageBackend(str(base))
    url = be.put(str(src), "already.mp4")
    assert src.exists()
    assert url.endswith("already.mp4")


# ─────────────────────────────────────────────────────────────────────────────
# S3 backend — boto3 is mocked so no real network calls
# ─────────────────────────────────────────────────────────────────────────────


def test_s3_backend_uploads_via_boto3(mocker):
    fake_client = mocker.MagicMock()
    fake_boto3 = mocker.MagicMock()
    fake_boto3.client.return_value = fake_client
    mocker.patch.dict("sys.modules", {"boto3": fake_boto3})

    be = S3StorageBackend(bucket="my-bucket", region="us-east-1", prefix="lessons")
    url = be.put("/tmp/x.mp4", "abc.mp4")

    fake_client.upload_file.assert_called_once()
    call = fake_client.upload_file.call_args
    assert call.kwargs["Bucket"] == "my-bucket"
    assert call.kwargs["Key"] == "lessons/abc.mp4"
    assert call.kwargs["ExtraArgs"]["ContentType"] == "video/mp4"
    # URL falls back to the standard S3 virtual-hosted style
    assert url == "https://my-bucket.s3.amazonaws.com/lessons/abc.mp4"


def test_s3_backend_uses_public_base_url_when_provided(mocker):
    fake_client = mocker.MagicMock()
    fake_boto3 = mocker.MagicMock()
    fake_boto3.client.return_value = fake_client
    mocker.patch.dict("sys.modules", {"boto3": fake_boto3})

    be = S3StorageBackend(
        bucket="b", prefix="p",
        public_base_url="https://cdn.example.com",
    )
    assert be.url_for("x.mp4") == "https://cdn.example.com/p/x.mp4"


def test_s3_backend_passes_endpoint_url_for_r2(mocker):
    """Cloudflare R2 + MinIO compatibility: endpoint_url is wired into boto3."""
    fake_client = mocker.MagicMock()
    fake_boto3 = mocker.MagicMock()
    fake_boto3.client.return_value = fake_client
    mocker.patch.dict("sys.modules", {"boto3": fake_boto3})

    S3StorageBackend(
        bucket="b",
        endpoint_url="https://abc.r2.cloudflarestorage.com",
    )
    call = fake_boto3.client.call_args
    assert call.kwargs["endpoint_url"].endswith(".cloudflarestorage.com")


def test_s3_backend_raises_clear_error_when_boto3_missing(mocker):
    """If LUMEN_STORAGE_BACKEND=s3 is set but boto3 isn't installed, the
    error message must tell the user what to do."""
    import builtins
    real_import = builtins.__import__

    def block_boto3(name, *args, **kwargs):
        if name == "boto3":
            raise ImportError("No module named 'boto3'")
        return real_import(name, *args, **kwargs)

    mocker.patch("builtins.__import__", side_effect=block_boto3)
    with pytest.raises(ImportError, match="boto3"):
        S3StorageBackend(bucket="b")


# ─────────────────────────────────────────────────────────────────────────────
# build_default_storage routing
# ─────────────────────────────────────────────────────────────────────────────


def test_build_default_storage_returns_local_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("LUMEN_STORAGE_BACKEND", raising=False)
    s = build_default_storage(local_base_dir=str(tmp_path))
    assert isinstance(s, LocalStorageBackend)


def test_build_default_storage_requires_bucket_for_s3(monkeypatch):
    monkeypatch.setenv("LUMEN_STORAGE_BACKEND", "s3")
    monkeypatch.delenv("LUMEN_S3_BUCKET", raising=False)
    with pytest.raises(RuntimeError, match="LUMEN_S3_BUCKET"):
        build_default_storage()


def test_build_default_storage_builds_s3_backend(monkeypatch, mocker):
    """End-to-end env wiring."""
    fake_client = mocker.MagicMock()
    fake_boto3 = mocker.MagicMock()
    fake_boto3.client.return_value = fake_client
    mocker.patch.dict("sys.modules", {"boto3": fake_boto3})

    monkeypatch.setenv("LUMEN_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("LUMEN_S3_BUCKET", "lumen-prod")
    monkeypatch.setenv("LUMEN_S3_REGION", "us-west-2")

    s = build_default_storage()
    assert isinstance(s, S3StorageBackend)
