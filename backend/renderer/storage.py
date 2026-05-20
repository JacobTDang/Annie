"""
Pluggable video storage backend (Item #15).

The default `LocalStorageBackend` keeps the existing behavior: rendered MP4s
live in `backend/media/lessons/` and are served by Flask. The opt-in
`S3StorageBackend` uploads to S3 / R2 / any S3-compatible bucket and returns
a public URL instead.

Switch backends via env vars:
    LUMEN_STORAGE_BACKEND=local        (default — no behavior change)
    LUMEN_STORAGE_BACKEND=s3
      LUMEN_S3_BUCKET=lumen-videos
      LUMEN_S3_REGION=us-east-1
      LUMEN_S3_PREFIX=lessons/         (optional key prefix)
      LUMEN_S3_PUBLIC_BASE_URL=https://cdn.example.com  (optional — if set,
                                                          returned URLs use
                                                          this base instead
                                                          of the s3 URL)
      AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY  (standard boto3 env vars)
      AWS_ENDPOINT_URL_S3=https://...r2.cloudflarestorage.com  (for R2)

boto3 is loaded lazily — local deployments don't need it installed.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


class StorageBackend:
    """Common interface — uploads a rendered video, returns a URL."""

    def put(self, local_path: str, key: str) -> str:
        """Upload ``local_path`` under ``key``; return a URL the frontend can play."""
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def url_for(self, key: str) -> str:
        """Return the public URL for a key already in storage."""
        raise NotImplementedError


class LocalStorageBackend(StorageBackend):
    """File-system backend — matches the existing media/ layout.

    Files are copied/moved into ``base_dir`` and exposed via a relative URL
    like ``/media/lessons/<key>``. The Flask app already serves this prefix.
    """

    def __init__(self, base_dir: str, url_prefix: str = "/media/lessons"):
        self._base = base_dir
        self._prefix = url_prefix.rstrip("/")
        os.makedirs(self._base, exist_ok=True)

    def _abs(self, key: str) -> str:
        return os.path.join(self._base, key)

    def put(self, local_path: str, key: str) -> str:
        dst = self._abs(key)
        os.makedirs(os.path.dirname(dst) or self._base, exist_ok=True)
        # Use copy not move: caller may want the original for cleanup logic.
        if os.path.abspath(local_path) != os.path.abspath(dst):
            shutil.copyfile(local_path, dst)
        return self.url_for(key)

    def exists(self, key: str) -> bool:
        return os.path.exists(self._abs(key))

    def url_for(self, key: str) -> str:
        # POSIX-style slash in URLs even on Windows
        return f"{self._prefix}/{Path(key).as_posix()}"


class S3StorageBackend(StorageBackend):
    """S3-compatible backend. Works with AWS S3, Cloudflare R2, MinIO, etc.

    boto3 is imported lazily — only deployments opting into S3 need it.
    A clear ImportError is raised if the env asked for S3 but boto3 isn't
    installed.
    """

    def __init__(self, bucket: str, region: str | None = None,
                  prefix: str = "", public_base_url: str | None = None,
                  endpoint_url: str | None = None):
        try:
            import boto3  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "S3StorageBackend requires `boto3` — `pip install boto3`. "
                "Alternatively unset LUMEN_STORAGE_BACKEND to use the local "
                "file-system backend."
            ) from exc

        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._public_base = (public_base_url or "").rstrip("/")
        client_kwargs: dict = {}
        if region:
            client_kwargs["region_name"] = region
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url
        self._client = boto3.client("s3", **client_kwargs)

    def _key(self, key: str) -> str:
        return f"{self._prefix}/{key}" if self._prefix else key

    def put(self, local_path: str, key: str) -> str:
        full_key = self._key(key)
        self._client.upload_file(
            Filename=local_path,
            Bucket=self._bucket,
            Key=full_key,
            ExtraArgs={"ContentType": "video/mp4"},
        )
        return self.url_for(key)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=self._key(key))
            return True
        except Exception:
            return False

    def url_for(self, key: str) -> str:
        full_key = self._key(key)
        if self._public_base:
            return f"{self._public_base}/{full_key}"
        # Fall back to the standard virtual-hosted–style S3 URL
        return f"https://{self._bucket}.s3.amazonaws.com/{full_key}"


def build_default_storage(local_base_dir: str | None = None) -> StorageBackend:
    """Pick a backend based on LUMEN_STORAGE_BACKEND."""
    backend = os.environ.get("LUMEN_STORAGE_BACKEND", "local").strip().lower()
    if backend == "s3":
        bucket = os.environ.get("LUMEN_S3_BUCKET", "").strip()
        if not bucket:
            raise RuntimeError(
                "LUMEN_STORAGE_BACKEND=s3 requires LUMEN_S3_BUCKET to be set"
            )
        return S3StorageBackend(
            bucket=bucket,
            region=os.environ.get("LUMEN_S3_REGION") or None,
            prefix=os.environ.get("LUMEN_S3_PREFIX", "").strip(),
            public_base_url=os.environ.get("LUMEN_S3_PUBLIC_BASE_URL"),
            endpoint_url=os.environ.get("AWS_ENDPOINT_URL_S3"),
        )

    # Default: local file-system backend.
    base = local_base_dir or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "media", "lessons",
    )
    return LocalStorageBackend(base_dir=base)
