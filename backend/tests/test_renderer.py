import os
import threading
from unittest.mock import MagicMock, patch

from renderer.worker import get_job, submit_render


def test_submit_render_returns_string_id():
    with patch("renderer.worker._run_render"):
        with patch("threading.Thread") as mock_thread:
            mock_thread.return_value = MagicMock()
            job_id = submit_render("bubble_sort", {"array": [3, 1, 2]})
    assert isinstance(job_id, str)
    assert len(job_id) > 0


def test_initial_status_is_pending():
    with patch("threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        job_id = submit_render("bubble_sort", {"array": [3, 1, 2]})
    job = get_job(job_id)
    assert job is not None
    assert job["status"] == "pending"


def test_unknown_job_returns_none():
    assert get_job("does-not-exist") is None


def test_unknown_scene_type_sets_error(tmp_path, monkeypatch):
    monkeypatch.setattr("renderer.worker._TEMP_DIR", str(tmp_path))
    monkeypatch.setattr("renderer.worker._MEDIA_DIR", str(tmp_path))

    # Run _run_render directly (synchronously) with an unknown scene type
    from renderer.worker import _run_render, _jobs
    job_id = "test-unknown-scene"
    _jobs[job_id] = {"status": "pending", "url": None, "error": None}
    _run_render(job_id, "not_a_real_scene", {})

    assert _jobs[job_id]["status"] == "error"
    assert "unknown scene type" in _jobs[job_id]["error"]


# ─────────────────────────────────────────────────────────────────────────────
# Phase A — stage tracking
# ─────────────────────────────────────────────────────────────────────────────

def test_submit_render_initializes_with_queued_stage():
    with patch("threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        job_id = submit_render("bubble_sort", {"array": [3, 1, 2]})
    job = get_job(job_id)
    assert job is not None
    assert job.get("stage") == "queued"


def test_submit_lesson_initializes_with_queued_stage():
    from renderer.worker import submit_lesson
    with patch("threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        lesson_id = submit_lesson([])  # empty steps OK for init check
    job = get_job(lesson_id)
    assert job is not None
    assert job.get("stage") == "queued"


def test_get_job_includes_stage_field():
    with patch("threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        job_id = submit_render("bubble_sort", {"array": [1]})
    job = get_job(job_id)
    assert "stage" in job


def test_unknown_scene_sets_stage_error(tmp_path, monkeypatch):
    monkeypatch.setattr("renderer.worker._TEMP_DIR", str(tmp_path))
    monkeypatch.setattr("renderer.worker._MEDIA_DIR", str(tmp_path))
    from renderer.worker import _run_render, _jobs
    job_id = "test-unknown-stage"
    _jobs[job_id] = {"status": "pending", "url": None, "error": None,
                     "progress": 0.0, "stage": "queued"}
    _run_render(job_id, "not_a_real_scene", {})
    assert _jobs[job_id]["stage"] == "error"


def test_run_lesson_sets_done_stage_on_cache_hit(tmp_path, monkeypatch):
    """When the cache returns a URL, the lesson immediately finalizes with stage=done."""
    monkeypatch.setattr("renderer.worker._MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr("renderer.worker._LESSONS_DIR", str(tmp_path))

    from renderer.worker import _run_lesson, _jobs
    monkeypatch.setattr("renderer.worker._cache_lookup", lambda key: "/media/lessons/cached.mp4")

    lesson_id = "test-cache-hit"
    _jobs[lesson_id] = {"status": "pending", "url": None, "error": None,
                        "progress": 0.0, "stage": "queued"}
    _run_lesson(lesson_id, [])
    assert _jobs[lesson_id]["stage"] == "done"
    assert _jobs[lesson_id]["status"] == "done"


def test_aggregate_progress_sets_rendering_x_of_n(tmp_path, monkeypatch):
    """The progress aggregator sets stage='rendering_X_of_N' based on completed steps."""
    from renderer.worker import _aggregate_progress, _jobs

    lesson_id = "test-agg-progress"
    step_ids = ["s1", "s2", "s3"]
    _jobs[lesson_id] = {"status": "pending", "url": None, "error": None,
                        "progress": 0.0, "stage": "queued"}
    # Two steps done, third in-progress
    _jobs["s1"] = {"status": "done", "progress": 1.0}
    _jobs["s2"] = {"status": "done", "progress": 1.0}
    _jobs["s3"] = {"status": "pending", "progress": 0.3}

    stop = threading.Event()
    t = threading.Thread(target=_aggregate_progress, args=(lesson_id, step_ids, stop), daemon=True)
    t.start()
    # Give the ticker (250ms loop) a moment to update
    import time
    time.sleep(0.4)
    stop.set()
    t.join(timeout=1.0)

    assert _jobs[lesson_id]["stage"] == "rendering_3_of_3"


# ─────────────────────────────────────────────────────────────────────────────
# Phase D — video pinning
# ─────────────────────────────────────────────────────────────────────────────

def test_pin_video_writes_to_index(tmp_path, monkeypatch):
    """Item #15 refactor: the pin index now stores lesson_id (backend-
    agnostic) rather than the full URL."""
    monkeypatch.setattr("renderer.worker._PINNED_INDEX", str(tmp_path / "pinned_index.json"))
    monkeypatch.setattr("renderer.worker._LESSONS_DIR", str(tmp_path))
    from renderer.worker import pin_video, _load_pinned_index, _jobs

    job_id = "test-pin-write"
    _jobs[job_id] = {"status": "done", "url": "/media/lessons/test.mp4",
                     "error": None, "progress": 1.0, "stage": "done"}
    pin_video(job_id)
    index = _load_pinned_index()
    # New shape: lesson_id extracted from the URL basename
    assert index.get(job_id) == "test"


def test_unpin_video_removes_from_index(tmp_path, monkeypatch):
    monkeypatch.setattr("renderer.worker._PINNED_INDEX", str(tmp_path / "pinned_index.json"))
    monkeypatch.setattr("renderer.worker._LESSONS_DIR", str(tmp_path))
    from renderer.worker import pin_video, unpin_video, _load_pinned_index, _jobs

    job_id = "test-pin-unpin"
    _jobs[job_id] = {"status": "done", "url": "/media/lessons/abc.mp4",
                     "error": None, "progress": 1.0, "stage": "done"}
    pin_video(job_id)
    assert job_id in _load_pinned_index()
    assert unpin_video(job_id) is True
    assert job_id not in _load_pinned_index()


def test_unpin_video_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr("renderer.worker._PINNED_INDEX", str(tmp_path / "pinned_index.json"))
    from renderer.worker import unpin_video
    # Never pinned — should return False, not raise
    assert unpin_video("never-pinned") is False
    assert unpin_video("never-pinned") is False  # second call also safe


def test_pin_video_unknown_job_raises():
    from renderer.worker import pin_video
    import pytest as _pt
    with _pt.raises(ValueError, match="unknown job_id"):
        pin_video("does-not-exist")


def test_pin_video_pending_job_raises():
    from renderer.worker import pin_video, _jobs
    import pytest as _pt
    _jobs["test-pending-pin"] = {"status": "pending", "url": None,
                                  "error": None, "progress": 0.0, "stage": "queued"}
    with _pt.raises(ValueError, match="status="):
        pin_video("test-pending-pin")


def test_cleanup_respects_pinned_index(tmp_path, monkeypatch):
    """Files referenced in pinned_index survive cleanup even when over the count cap."""
    lessons_dir = tmp_path / "lessons"
    lessons_dir.mkdir()
    monkeypatch.setattr("renderer.worker._LESSONS_DIR", str(lessons_dir))
    monkeypatch.setattr("renderer.worker._MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr("renderer.worker._PINNED_INDEX", str(tmp_path / "pinned_index.json"))
    monkeypatch.setattr("renderer.worker._CACHE_INDEX", str(tmp_path / "cache_index.json"))

    # Create 5 lesson files, all old enough to be eligible for cleanup
    import time
    old = time.time() - 1000
    for i in range(5):
        f = lessons_dir / f"file_{i}.mp4"
        f.write_bytes(b"x" * 100)
        os.utime(f, (old, old))

    # Pin file_2 explicitly
    from renderer.worker import _save_pinned_index, cleanup_old_lessons
    _save_pinned_index({"my-job": "/media/lessons/file_2.mp4"})

    # Cap at 1 — should evict 4, but file_2 must survive
    removed = cleanup_old_lessons(max_count=1, min_age_seconds=0)
    remaining = sorted(p.name for p in lessons_dir.glob("*.mp4"))
    assert "file_2.mp4" in remaining
    assert removed >= 3   # 4 should have been removed, but 1 stays for the cap
