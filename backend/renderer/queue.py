"""
Pluggable background job queue (Item #14).

Default: ``InProcessQueue`` — runs jobs on a thread pool inside the Flask
process. This matches today's worker behavior and needs zero ops setup.

Opt-in: ``RedisQueue`` — uses RQ (Redis Queue) so jobs survive crashes and
can be processed by separate worker containers (see ``docker-compose.yml``
which provisions a redis service).

Switch via:
    REDIS_URL=redis://localhost:6379/0   → use RQ if `rq` is importable
                                            AND the redis server pings.
    LUMEN_QUEUE_BACKEND=inprocess        → force the in-process backend.

The two backends share a single interface so the worker layer can stay
agnostic.
"""
from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable


class JobQueue:
    """Abstract job-queue interface."""

    def enqueue(self, func: Callable, *args, **kwargs) -> str:
        """Submit a job. Returns an opaque job_id."""
        raise NotImplementedError

    def status(self, job_id: str) -> str:
        """Return one of: queued | started | finished | failed | unknown."""
        raise NotImplementedError

    def result(self, job_id: str, timeout: float | None = None) -> Any:
        """Block (up to timeout) for the job result. Raises on failure."""
        raise NotImplementedError


class InProcessQueue(JobQueue):
    """Thread-pool backed queue. The default — zero ops setup."""

    def __init__(self, max_workers: int = 4):
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()

    def enqueue(self, func: Callable, *args, **kwargs) -> str:
        job_id = str(uuid.uuid4())
        fut = self._pool.submit(func, *args, **kwargs)
        with self._lock:
            self._futures[job_id] = fut
        return job_id

    def status(self, job_id: str) -> str:
        with self._lock:
            fut = self._futures.get(job_id)
        if fut is None:
            return "unknown"
        if fut.done():
            return "failed" if fut.exception() else "finished"
        if fut.running():
            return "started"
        return "queued"

    def result(self, job_id: str, timeout: float | None = None) -> Any:
        with self._lock:
            fut = self._futures.get(job_id)
        if fut is None:
            raise KeyError(job_id)
        return fut.result(timeout=timeout)

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)


class RedisQueue(JobQueue):
    """RQ + Redis-backed queue. Jobs survive process restarts.

    Imports rq lazily — only required when this backend is built. A clear
    error fires if rq isn't installed, so the operator knows what to fix.
    """

    def __init__(self, redis_url: str, queue_name: str = "lumen"):
        try:
            import rq          # type: ignore
            import redis       # type: ignore
        except ImportError as exc:
            raise ImportError(
                "RedisQueue requires `rq` and `redis` — `pip install rq redis`."
            ) from exc

        self._redis = redis.Redis.from_url(redis_url)
        # Smoke-ping so build_default_queue can fall back if Redis is down.
        self._redis.ping()
        self._q = rq.Queue(queue_name, connection=self._redis)
        self._name = queue_name

    def enqueue(self, func: Callable, *args, **kwargs) -> str:
        job = self._q.enqueue(func, *args, **kwargs)
        return job.id

    def status(self, job_id: str) -> str:
        try:
            import rq  # type: ignore
        except ImportError:
            return "unknown"
        try:
            job = rq.job.Job.fetch(job_id, connection=self._redis)
        except Exception:
            return "unknown"
        return job.get_status() or "unknown"

    def result(self, job_id: str, timeout: float | None = None) -> Any:
        import time
        import rq  # type: ignore
        deadline = time.monotonic() + timeout if timeout else None
        while True:
            try:
                job = rq.job.Job.fetch(job_id, connection=self._redis)
            except Exception as exc:
                raise KeyError(job_id) from exc
            status = job.get_status()
            if status == "finished":
                return job.result
            if status == "failed":
                raise RuntimeError(job.exc_info or "job failed")
            if deadline and time.monotonic() > deadline:
                raise TimeoutError(f"job {job_id} not done after {timeout}s")
            time.sleep(0.25)


def build_default_queue() -> JobQueue:
    """Pick a queue based on env vars + Redis reachability.

    Resolution order:
      1. LUMEN_QUEUE_BACKEND=inprocess → always in-process.
      2. REDIS_URL set AND rq + redis importable AND Redis pings → RedisQueue.
      3. Otherwise → InProcessQueue (graceful fallback).
    """
    forced = os.environ.get("LUMEN_QUEUE_BACKEND", "").strip().lower()
    if forced == "inprocess":
        return InProcessQueue()

    redis_url = os.environ.get("REDIS_URL", "").strip()
    if redis_url:
        try:
            return RedisQueue(redis_url)
        except Exception as exc:
            print(f"[queue] RedisQueue unavailable ({exc}); "
                   "falling back to InProcessQueue")
    return InProcessQueue()
