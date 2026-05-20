"""Tests for the pluggable background-job queue (Item #14)."""
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from renderer.queue import (
    InProcessQueue,
    RedisQueue,
    build_default_queue,
)


# ─────────────────────────────────────────────────────────────────────────────
# InProcessQueue — actual execution
# ─────────────────────────────────────────────────────────────────────────────


def test_inprocess_runs_function_and_returns_result():
    q = InProcessQueue(max_workers=2)
    try:
        job_id = q.enqueue(lambda a, b: a + b, 2, 3)
        assert q.result(job_id, timeout=5) == 5
        assert q.status(job_id) == "finished"
    finally:
        q.shutdown()


def test_inprocess_status_reflects_failure():
    q = InProcessQueue()
    try:
        def boom():
            raise ValueError("nope")
        job_id = q.enqueue(boom)
        # Wait for the worker
        for _ in range(50):
            if q.status(job_id) == "failed":
                break
            time.sleep(0.05)
        assert q.status(job_id) == "failed"
    finally:
        q.shutdown()


def test_inprocess_unknown_job_id():
    q = InProcessQueue()
    try:
        assert q.status("does-not-exist") == "unknown"
        with pytest.raises(KeyError):
            q.result("does-not-exist")
    finally:
        q.shutdown()


def test_inprocess_concurrent_jobs():
    """Multiple jobs run in parallel — total time < serial time."""
    q = InProcessQueue(max_workers=4)
    try:
        start = time.monotonic()
        ids = [q.enqueue(time.sleep, 0.2) for _ in range(4)]
        for jid in ids:
            q.result(jid, timeout=5)
        elapsed = time.monotonic() - start
        # Serial would be ~0.8s; 4 workers should finish in ~0.2-0.3s
        assert elapsed < 0.6, f"parallel jobs took {elapsed:.2f}s (expected < 0.6s)"
    finally:
        q.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# RedisQueue — boto3-style mocked rq + redis modules
# ─────────────────────────────────────────────────────────────────────────────


def test_redis_queue_enqueue_uses_rq(mocker):
    fake_job = mocker.MagicMock()
    fake_job.id = "rq-job-1"
    fake_q = mocker.MagicMock()
    fake_q.enqueue.return_value = fake_job

    fake_rq_mod = mocker.MagicMock()
    fake_rq_mod.Queue.return_value = fake_q

    fake_redis_client = mocker.MagicMock()
    fake_redis_mod = mocker.MagicMock()
    fake_redis_mod.Redis.from_url.return_value = fake_redis_client

    mocker.patch.dict("sys.modules", {"rq": fake_rq_mod, "redis": fake_redis_mod})

    q = RedisQueue("redis://localhost:6379/0", queue_name="lumen")
    fake_redis_client.ping.assert_called_once()  # smoke-pings on init
    job_id = q.enqueue(print, "hello")
    assert job_id == "rq-job-1"
    fake_q.enqueue.assert_called_once()


def test_redis_queue_raises_when_rq_not_installed(mocker):
    """Operator-friendly error if they asked for RQ without installing it."""
    import builtins
    real_import = builtins.__import__

    def block(name, *args, **kwargs):
        if name in ("rq", "redis"):
            raise ImportError(f"No module named '{name}'")
        return real_import(name, *args, **kwargs)

    mocker.patch("builtins.__import__", side_effect=block)
    with pytest.raises(ImportError, match="rq"):
        RedisQueue("redis://localhost:6379/0")


# ─────────────────────────────────────────────────────────────────────────────
# build_default_queue routing
# ─────────────────────────────────────────────────────────────────────────────


def test_build_default_queue_no_redis_url_returns_inprocess(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("LUMEN_QUEUE_BACKEND", raising=False)
    q = build_default_queue()
    assert isinstance(q, InProcessQueue)
    q.shutdown()


def test_build_default_queue_forced_inprocess_overrides_redis(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("LUMEN_QUEUE_BACKEND", "inprocess")
    q = build_default_queue()
    assert isinstance(q, InProcessQueue)
    q.shutdown()


def test_build_default_queue_falls_back_when_redis_unreachable(monkeypatch, mocker):
    """If REDIS_URL is set but the server is down, gracefully use InProcess."""
    monkeypatch.setenv("REDIS_URL", "redis://nonexistent:6379/0")
    monkeypatch.delenv("LUMEN_QUEUE_BACKEND", raising=False)

    # Make RedisQueue init explode with a connection error so the fallback fires
    def boom(*args, **kwargs):
        raise ConnectionError("could not reach redis")
    mocker.patch("renderer.queue.RedisQueue", side_effect=boom)

    q = build_default_queue()
    assert isinstance(q, InProcessQueue)
    q.shutdown()


def test_build_default_queue_uses_rq_when_reachable(monkeypatch, mocker):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("LUMEN_QUEUE_BACKEND", raising=False)

    sentinel = object()
    mocker.patch("renderer.queue.RedisQueue", return_value=sentinel)
    assert build_default_queue() is sentinel
