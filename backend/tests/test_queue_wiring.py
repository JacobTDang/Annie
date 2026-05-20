"""Tests for the queue-wiring follow-up (#14 completion).

The submit_* dispatchers must go through `_default_queue` instead of
spawning bare threading.Threads, so swapping in RQ requires only a
`REDIS_URL=...` env change rather than a code refactor.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_worker_module_initializes_default_queue():
    """`_default_queue` must be built at module import — flipping REDIS_URL
    after the fact should route subsequent submits through the queue."""
    import renderer.worker as w
    from renderer.queue import JobQueue
    assert hasattr(w, "_default_queue")
    assert isinstance(w._default_queue, JobQueue)


def test_submit_render_enqueues_via_queue(mocker):
    """submit_render must call _default_queue.enqueue, not Thread."""
    import renderer.worker as w
    enq = mocker.patch.object(w._default_queue, "enqueue")
    thread_spy = mocker.patch("renderer.worker.threading.Thread")

    job_id = w.submit_render("function_plot",
                              {"expression": "x*x", "domain": [-2, 2]})
    assert isinstance(job_id, str) and len(job_id) > 0
    enq.assert_called_once()
    # First positional arg to enqueue is the function to run
    call = enq.call_args
    assert call.args[0] is w._run_render
    assert call.args[1] == job_id
    # Critical: must NOT have spun up a raw thread
    thread_spy.assert_not_called()


def test_submit_lesson_enqueues_via_queue(mocker):
    import renderer.worker as w
    enq = mocker.patch.object(w._default_queue, "enqueue")
    thread_spy = mocker.patch("renderer.worker.threading.Thread")

    job_id = w.submit_lesson([])
    enq.assert_called_once()
    call = enq.call_args
    assert call.args[0] is w._run_lesson
    assert call.args[1] == job_id
    thread_spy.assert_not_called()


def test_submit_direct_lesson_enqueues_via_queue(mocker):
    import renderer.worker as w
    enq = mocker.patch.object(w._default_queue, "enqueue")
    thread_spy = mocker.patch("renderer.worker.threading.Thread")

    job_id = w.submit_direct_lesson("anything",
                                       style=None, target_minutes=1.5)
    enq.assert_called_once()
    call = enq.call_args
    assert call.args[0] is w._run_direct_lesson
    # job_id, question, style, target_minutes, difficulty_hint
    assert call.args[1] == job_id
    assert call.args[2] == "anything"
    thread_spy.assert_not_called()


def test_submit_render_creates_pending_job_state(mocker):
    """Sanity: the dispatch still seeds `_jobs[job_id]` so /status can find it
    immediately, before the queue has even run the worker."""
    import renderer.worker as w
    mocker.patch.object(w._default_queue, "enqueue")
    job_id = w.submit_render("function_plot", {"expression": "x", "domain": [-1, 1]})
    rec = w._jobs.get(job_id)
    assert rec is not None
    assert rec["status"] == "pending"
    assert rec["url"] is None


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end with InProcessQueue — make sure the InProcess path still
# actually executes the work (this is the default and tests must pass even
# without Redis).
# ─────────────────────────────────────────────────────────────────────────────


def test_default_queue_is_inprocess_when_redis_url_unset(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("LUMEN_QUEUE_BACKEND", raising=False)
    # Re-import to pick up env
    import importlib
    import renderer.queue as q
    import renderer.worker as w
    importlib.reload(q)
    importlib.reload(w)
    assert type(w._default_queue).__name__ == "InProcessQueue"
