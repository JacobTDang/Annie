"""Tests for the worker shutdown + progress-thread join (daemon-thread-leak fix).

The trailing 'RuntimeError: cannot schedule new futures after interpreter
shutdown' trace in earlier pytest runs came from daemon threads outliving
test teardown. These tests pin that contract.
"""
import os
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from renderer import worker


# ─────────────────────────────────────────────────────────────────────────────
# progress_thread.join(): aggregator must die when its lesson finishes
# ─────────────────────────────────────────────────────────────────────────────


def _step(tool: str = "function_plot", params: dict | None = None, caption: str = ""):
    return SimpleNamespace(tool=tool, params=params or {}, caption=caption)


def _wait_until(predicate, timeout: float = 3.0, tick: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(tick)
    return predicate()


def test_progress_thread_joins_on_normal_completion(monkeypatch, mocker):
    """When all steps complete successfully, the aggregator thread must
    exit within 2s of _run_lesson returning."""
    # Stub the actual render so the worker doesn't try to spawn manim
    captured_threads: list[threading.Thread] = []
    original_thread_class = threading.Thread

    def _record(target, *args, **kwargs):
        t = original_thread_class(target=target, *args, **kwargs)
        if target is worker._aggregate_progress:
            captured_threads.append(t)
        return t

    monkeypatch.setattr(worker.threading, "Thread", _record)

    # Make _run_render an instant-complete no-op that flips the inner job to
    # "done" so the for-loop check doesn't return early.
    def _stub_render(job_id, scene_type, params):
        worker._jobs[job_id] = {
            "status": "done",
            "url": f"/media/jobs/{job_id}/file.mp4",
            "error": None, "progress": 1.0, "stage": "done",
        }
        # Touch a fake src file so storage.put has something to copy
        src = os.path.join(worker._MEDIA_DIR, "jobs", job_id)
        os.makedirs(src, exist_ok=True)
        with open(os.path.join(src, "file.mp4"), "wb") as fh:
            fh.write(b"\x00")
    monkeypatch.setattr(worker, "_run_render", _stub_render)
    monkeypatch.setattr(worker, "_cache_lookup", lambda k: None)
    monkeypatch.setattr(worker, "_cache_store", lambda k, v: None)

    # Seed the outer lesson job record (normally done by submit_lesson)
    worker._jobs["lesson-join-ok"] = {
        "status": "pending", "url": None, "error": None,
        "progress": 0.0, "stage": "queued",
    }
    worker._run_lesson("lesson-join-ok", [_step(), _step()])

    # The aggregator thread we captured must NOT outlive _run_lesson
    assert captured_threads, "aggregator thread was never started"
    agg = captured_threads[-1]
    assert _wait_until(lambda: not agg.is_alive(), timeout=3.0), (
        "progress thread is still alive after _run_lesson returned — leak"
    )


def test_progress_thread_joins_on_step_error(monkeypatch):
    """If any step errors, _run_lesson early-returns. The aggregator must
    still be joined (the `finally` clause covers both paths)."""
    captured_threads: list[threading.Thread] = []
    original_thread_class = threading.Thread

    def _record(target, *args, **kwargs):
        t = original_thread_class(target=target, *args, **kwargs)
        if target is worker._aggregate_progress:
            captured_threads.append(t)
        return t

    monkeypatch.setattr(worker.threading, "Thread", _record)

    def _stub_render(job_id, scene_type, params):
        worker._jobs[job_id] = {
            "status": "error", "url": None, "error": "boom",
            "progress": 0.0, "stage": "error",
        }
    monkeypatch.setattr(worker, "_run_render", _stub_render)
    monkeypatch.setattr(worker, "_cache_lookup", lambda k: None)

    # Seed the outer lesson job record (normally done by submit_lesson)
    worker._jobs["lesson-join-err"] = {
        "status": "pending", "url": None, "error": None,
        "progress": 0.0, "stage": "queued",
    }
    worker._run_lesson("lesson-join-err", [_step(), _step()])

    assert captured_threads
    agg = captured_threads[-1]
    assert _wait_until(lambda: not agg.is_alive(), timeout=3.0), (
        "aggregator survived early-return path — leak"
    )


# ─────────────────────────────────────────────────────────────────────────────
# worker.shutdown(): draining the InProcessQueue
# ─────────────────────────────────────────────────────────────────────────────


def test_worker_shutdown_drains_inprocess_queue(monkeypatch):
    """Submit work, immediately call shutdown(), assert the pool drained."""
    from renderer.queue import InProcessQueue
    q = InProcessQueue(max_workers=2)
    completed = []

    def slow_job(i: int):
        time.sleep(0.1)
        completed.append(i)

    for i in range(4):
        q.enqueue(slow_job, i)

    # Replace the module's queue so shutdown() targets our instance
    monkeypatch.setattr(worker, "_default_queue", q)
    worker.shutdown(wait=True, timeout=5.0)

    # All 4 jobs should have run before shutdown returned
    assert sorted(completed) == [0, 1, 2, 3]


def test_worker_shutdown_is_idempotent_and_safe_on_missing_queue(monkeypatch):
    """shutdown() must never raise even when called twice or when the queue
    backend doesn't expose .shutdown."""
    class _NoOpQueue:
        # No .shutdown attr — exercises the hasattr guard
        pass
    monkeypatch.setattr(worker, "_default_queue", _NoOpQueue())
    # Doesn't raise
    worker.shutdown()
    worker.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end sentinel: the trailing 'cannot schedule new futures' trace
# must not appear in a clean pytest run.
# ─────────────────────────────────────────────────────────────────────────────


def test_pytest_does_not_emit_scheduler_shutdown_trace(tmp_path):
    """Run a tiny pytest invocation that submits + drops a lesson, then assert
    stderr doesn't contain the leaked-thread RuntimeError.

    Skipped on platforms that can't easily launch a subprocess invocation of
    the same interpreter (rare; not a concern on win32/linux/darwin).
    """
    test_file = tmp_path / "test_lesson_submit.py"
    test_file.write_text(
        "import os, sys, time\n"
        f"sys.path.insert(0, r{os.path.dirname(os.path.dirname(__file__))!r})\n"
        "from renderer import worker\n"
        "from types import SimpleNamespace\n"
        "def test_submit_then_drop():\n"
        "    # Stub the inner render so it completes instantly\n"
        "    worker._run_render = lambda *a, **kw: None\n"
        "    job_id = worker.submit_lesson([SimpleNamespace(tool='x', params={}, caption='')])\n"
        "    # Don't poll — let teardown drain (worker.shutdown via conftest)\n"
        "    time.sleep(0.05)\n",
        encoding="utf-8",
    )

    res = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file), "-q",
         "--rootdir", os.path.dirname(os.path.dirname(__file__))],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, "PYTHONPATH": os.path.dirname(os.path.dirname(__file__))},
    )
    combined = (res.stdout or "") + "\n" + (res.stderr or "")
    assert "cannot schedule new futures after interpreter shutdown" not in combined, (
        "daemon-thread leak regressed:\n" + combined[-2000:]
    )
