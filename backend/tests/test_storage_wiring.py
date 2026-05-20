"""Tests for the storage-wiring refactor (#15 completion).

The worker module must dispatch all final-lesson MP4 writes through
``_storage`` (the pluggable backend) rather than direct shutil.copyfile.
The cache + pin index must be backend-agnostic (store lesson_id, not URL)
and must still accept legacy URL-shaped entries.
"""
import json
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import renderer.worker as worker
from renderer.storage import LocalStorageBackend, StorageBackend


# ─────────────────────────────────────────────────────────────────────────────
# Worker module surface
# ─────────────────────────────────────────────────────────────────────────────


def test_worker_initializes_storage_backend():
    assert hasattr(worker, "_storage")
    assert isinstance(worker._storage, StorageBackend)


def test_worker_storage_helpers_exist():
    assert callable(worker._lesson_key)
    assert callable(worker._lesson_url)
    assert callable(worker._lesson_exists)
    assert callable(worker._url_to_lesson_id)


def test_lesson_key_format():
    assert worker._lesson_key("abc") == "abc.mp4"
    assert worker._lesson_key("uuid-with-dashes") == "uuid-with-dashes.mp4"


def test_url_to_lesson_id_extracts_from_local_url():
    assert worker._url_to_lesson_id("/media/lessons/foo.mp4") == "foo"


def test_url_to_lesson_id_extracts_from_s3_url():
    assert worker._url_to_lesson_id(
        "https://bucket.s3.amazonaws.com/lessons/abc.mp4"
    ) == "abc"


def test_url_to_lesson_id_strips_query_string():
    """Pre-signed S3 URLs carry ?X-Amz-Signature=... — must not corrupt the id."""
    assert worker._url_to_lesson_id(
        "https://x/lessons/abc.mp4?X-Amz-Signature=zzz"
    ) == "abc"


def test_url_to_lesson_id_returns_none_for_non_lesson_url():
    assert worker._url_to_lesson_id("/api/status/123") is None
    assert worker._url_to_lesson_id("") is None


# ─────────────────────────────────────────────────────────────────────────────
# cleanup_old_lessons + remote backend
# ─────────────────────────────────────────────────────────────────────────────


def test_cleanup_old_lessons_noops_for_remote_backend(monkeypatch):
    """The cleanup task only makes sense for LocalStorageBackend — S3 has
    lifecycle rules for that. Must return 0 without scanning the local dir."""
    class _RemoteBackend(StorageBackend):
        def put(self, src, key): return ""
        def exists(self, key): return False
        def url_for(self, key): return ""

    monkeypatch.setattr(worker, "_storage", _RemoteBackend())
    # Even if there are files in _LESSONS_DIR, no cleanup should happen
    removed = worker.cleanup_old_lessons(max_count=0)
    assert removed == 0


# ─────────────────────────────────────────────────────────────────────────────
# _run_lesson upload path — single step + multi-step both go through storage
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    """Point worker at a fresh tmp storage backend so test artifacts don't
    leak into the real media/ tree."""
    media_dir   = tmp_path / "media"
    lessons_dir = media_dir / "lessons"
    jobs_dir    = media_dir / "jobs"
    temp_dir    = media_dir / "temp"
    lessons_dir.mkdir(parents=True)
    jobs_dir.mkdir(parents=True)
    temp_dir.mkdir(parents=True)

    monkeypatch.setattr(worker, "_MEDIA_DIR",   str(media_dir))
    monkeypatch.setattr(worker, "_LESSONS_DIR", str(lessons_dir))
    monkeypatch.setattr(worker, "_TEMP_DIR",    str(temp_dir))
    monkeypatch.setattr(worker, "_CACHE_INDEX", str(lessons_dir / "cache_index.json"))
    monkeypatch.setattr(worker, "_PINNED_INDEX", str(lessons_dir / "pinned_index.json"))
    monkeypatch.setattr(worker, "_storage", LocalStorageBackend(str(lessons_dir)))
    return SimpleNamespace(
        media_dir=media_dir, lessons_dir=lessons_dir,
        jobs_dir=jobs_dir, temp_dir=temp_dir,
    )


def test_worker_source_no_longer_uses_shutil_copyfile_for_lessons():
    """Item #15 contract regression: the only remaining shutil.copyfile
    calls (if any) must NOT target _LESSONS_DIR. All final lesson writes
    must go through _storage.put()."""
    import inspect
    src = inspect.getsource(worker)
    # Storage.put must be invoked from the run-lesson path
    assert "_storage.put(" in src, (
        "_run_lesson must dispatch lesson uploads through _storage.put()"
    )
    # No raw shutil.copyfile destinations should be _LESSONS_DIR-derived
    # (we keep shutil.copyfile importable for other uses, but inspect that
    # it isn't called with a _LESSONS_DIR target).
    import re
    bad = re.findall(r"shutil\.copyfile\([^)]*_LESSONS_DIR", src)
    assert not bad, f"shutil.copyfile to _LESSONS_DIR still present: {bad}"


def test_run_lesson_writes_to_temp_dir_before_uploading():
    """Stitching must happen in _TEMP_DIR so S3 backend works (ffmpeg needs
    a local target before storage.put uploads). Previously stitched directly
    into _LESSONS_DIR which is broken under S3."""
    import inspect
    src = inspect.getsource(worker._run_lesson)
    # The stitched output path must be built relative to _TEMP_DIR, not _LESSONS_DIR
    assert "_TEMP_DIR" in src
    # Spec: cache_store now takes lesson_id (not URL)
    assert "_cache_store(cache_key, lesson_id)" in src