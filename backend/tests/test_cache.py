"""Unit tests for the lesson render cache + media cleanup helpers.

These tests intentionally avoid touching the on-disk media/ tree of the
running app — they redirect the cache constants to tmp_path via monkeypatch.
"""
import json
import os
import time
from types import SimpleNamespace

import pytest

from renderer import worker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_media(tmp_path, monkeypatch):
    """Point the worker module's media/lesson constants at a tmp dir.

    Item #15: storage is initialized at module-load against `_LESSONS_DIR`.
    Rebuild it pointed at the tmp dir too so cache lookups (which call
    `_storage.exists()`) see the test fixtures.
    """
    from renderer.storage import LocalStorageBackend
    media_dir   = tmp_path / "media"
    lessons_dir = media_dir / "lessons"
    jobs_dir    = media_dir / "jobs"
    lessons_dir.mkdir(parents=True)
    jobs_dir.mkdir(parents=True)

    monkeypatch.setattr(worker, "_MEDIA_DIR",   str(media_dir))
    monkeypatch.setattr(worker, "_LESSONS_DIR", str(lessons_dir))
    monkeypatch.setattr(worker, "_CACHE_INDEX", str(lessons_dir / "cache_index.json"))
    monkeypatch.setattr(worker, "_storage", LocalStorageBackend(str(lessons_dir)))
    return SimpleNamespace(
        media_dir=media_dir, lessons_dir=lessons_dir, jobs_dir=jobs_dir,
    )


def _step(tool: str, params: dict, caption: str = ""):
    """Lightweight stand-in for StepPlan — only needs .tool/.params/.caption."""
    return SimpleNamespace(tool=tool, params=params, caption=caption)


# ---------------------------------------------------------------------------
# _lesson_cache_key
# ---------------------------------------------------------------------------

def test_cache_key_is_deterministic():
    steps = [_step("function_plot", {"expression": "x**2", "domain": [-3, 3]})]
    assert worker._lesson_cache_key(steps) == worker._lesson_cache_key(steps)


def test_cache_key_ignores_caption():
    a = [_step("function_plot", {"expression": "x**2"}, caption="hello")]
    b = [_step("function_plot", {"expression": "x**2"}, caption="goodbye")]
    assert worker._lesson_cache_key(a) == worker._lesson_cache_key(b)


def test_cache_key_changes_with_params():
    a = [_step("function_plot", {"expression": "x**2"})]
    b = [_step("function_plot", {"expression": "x**3"})]
    assert worker._lesson_cache_key(a) != worker._lesson_cache_key(b)


def test_cache_key_changes_with_tool():
    a = [_step("function_plot", {"expression": "x"})]
    b = [_step("limit",         {"expression": "x"})]
    assert worker._lesson_cache_key(a) != worker._lesson_cache_key(b)


def test_cache_key_invariant_to_param_order():
    """sort_keys=True means dict insertion order shouldn't change the hash."""
    a = [_step("function_plot", {"expression": "x**2", "domain": [-3, 3]})]
    b = [_step("function_plot", {"domain": [-3, 3], "expression": "x**2"})]
    assert worker._lesson_cache_key(a) == worker._lesson_cache_key(b)


def test_cache_key_step_order_matters():
    """Different step ordering = different lesson, must hash differently."""
    s1 = _step("function_plot", {"expression": "x"})
    s2 = _step("limit",         {"expression": "x", "limit_point": 0})
    assert worker._lesson_cache_key([s1, s2]) != worker._lesson_cache_key([s2, s1])


# ---------------------------------------------------------------------------
# _cache_lookup / _cache_store round-trip
# ---------------------------------------------------------------------------

def test_cache_store_then_lookup_hits(isolated_media):
    """The cache index now stores lesson_id; lookup reconstructs the URL
    via the active storage backend (Item #15 refactor)."""
    video_path = isolated_media.lessons_dir / "abc.mp4"
    video_path.write_bytes(b"fake mp4")

    worker._cache_store("key1", "abc")
    assert worker._cache_lookup("key1") == "/media/lessons/abc.mp4"


def test_cache_lookup_miss_returns_none(isolated_media):
    assert worker._cache_lookup("nope") is None


def test_cache_lookup_drops_stale_entry(isolated_media):
    """If the cached video file no longer exists, lookup must return None
    AND remove the dead entry from the index."""
    worker._cache_store("ghost", "missing")
    assert worker._cache_lookup("ghost") is None

    with open(isolated_media.lessons_dir / "cache_index.json") as fh:
        index = json.load(fh)
    assert "ghost" not in index


def test_cache_lookup_migrates_legacy_url_entries(isolated_media):
    """Legacy cache entries stored full URLs. The reader must transparently
    accept them so an upgrade doesn't invalidate the existing cache."""
    video_path = isolated_media.lessons_dir / "legacy.mp4"
    video_path.write_bytes(b"x")

    # Manually inject a legacy URL-shaped entry
    legacy_index = {"legacy_key": "/media/lessons/legacy.mp4"}
    (isolated_media.lessons_dir / "cache_index.json").write_text(
        json.dumps(legacy_index)
    )

    # Lookup should still resolve it to a valid URL
    assert worker._cache_lookup("legacy_key") == "/media/lessons/legacy.mp4"


def test_cache_index_persists_to_disk(isolated_media):
    video_path = isolated_media.lessons_dir / "v.mp4"
    video_path.write_bytes(b"x")
    worker._cache_store("k", "v")

    raw = json.loads((isolated_media.lessons_dir / "cache_index.json").read_text())
    assert raw == {"k": "v"}


def test_load_cache_index_handles_corrupt_json(isolated_media):
    (isolated_media.lessons_dir / "cache_index.json").write_text("{not json")
    assert worker._load_cache_index() == {}


# ---------------------------------------------------------------------------
# cleanup_old_jobs
# ---------------------------------------------------------------------------

def test_cleanup_removes_old_dirs(isolated_media):
    old = isolated_media.jobs_dir / "old"
    new = isolated_media.jobs_dir / "new"
    old.mkdir()
    new.mkdir()
    # Backdate "old" by 2 hours
    old_ts = time.time() - 7200
    os.utime(old, (old_ts, old_ts))

    removed = worker.cleanup_old_jobs(max_age_seconds=3600)
    assert removed == 1
    assert not old.exists()
    assert new.exists()


def test_cleanup_skips_lessons_and_steps(isolated_media):
    """media/lessons and media/steps must never be touched."""
    lesson_file = isolated_media.lessons_dir / "keep.mp4"
    lesson_file.write_bytes(b"important")
    steps_dir = isolated_media.media_dir / "steps"
    steps_dir.mkdir()
    keep_step = steps_dir / "keep.mp4"
    keep_step.write_bytes(b"step")
    # Backdate both
    old_ts = time.time() - 7200
    os.utime(lesson_file, (old_ts, old_ts))
    os.utime(steps_dir,   (old_ts, old_ts))

    worker.cleanup_old_jobs(max_age_seconds=3600)
    assert lesson_file.exists()
    assert keep_step.exists()


def test_cleanup_handles_missing_jobs_dir(tmp_path, monkeypatch):
    """No jobs/ directory yet → cleanup should no-op, not raise."""
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    monkeypatch.setattr(worker, "_MEDIA_DIR", str(media_dir))
    assert worker.cleanup_old_jobs() == 0
