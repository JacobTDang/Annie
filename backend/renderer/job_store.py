"""
Job state persistence (Item #13).

The worker keeps a per-job dict (`{status, url, error, progress, stage, ...}`)
that the route layer polls via /status. Historically this lived in a process-
local dict and evaporated on restart. This module backs the same dict-shaped
interface with SQLite so jobs survive a restart and can later be queried
out-of-band.

Why stdlib sqlite3 instead of SQLAlchemy: zero new dependency, the storage
contract is tiny (one table, two columns), and the existing callsites already
treat the store as a plain dict. SQLAlchemy would buy nothing here.

Default backend is in-memory so existing tests + dev runs are unchanged. Set
``LUMEN_JOBS_DB=/path/to/jobs.db`` (or anything truthy) to opt into SQLite —
the file is created on first write.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Iterator


def _serialize(value: dict) -> str:
    """JSON-encode a job record; treat unsupported types as repr()."""
    return json.dumps(value, default=repr)


def _deserialize(raw: str) -> dict:
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else {}
    except (ValueError, TypeError):
        return {}


class JobStore:
    """Abstract dict-shaped interface — get/set by job_id."""

    def get(self, key: str, default=None) -> Any:
        raise NotImplementedError

    def set(self, key: str, value: dict) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def keys(self) -> Iterator[str]:
        raise NotImplementedError


class InMemoryJobStore(JobStore):
    """Default — dict in process memory. Lost on restart."""

    def __init__(self):
        self._data: dict[str, dict] = {}
        self._lock = threading.Lock()

    def get(self, key: str, default=None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: dict) -> None:
        with self._lock:
            self._data[key] = value

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def keys(self) -> Iterator[str]:
        with self._lock:
            return iter(list(self._data.keys()))


class SqliteJobStore(JobStore):
    """SQLite-backed store. Survives process restarts.

    A single table `jobs(id TEXT PRIMARY KEY, payload TEXT)`; the entire
    job dict is stored as JSON. This trades minor query power for a
    one-pass migration story and zero schema-coupling to the worker.

    Thread safety: every method opens its own connection (sqlite3 forbids
    sharing across threads by default).
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS jobs (
        id      TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        updated INTEGER NOT NULL
    )
    """

    def __init__(self, db_path: str):
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        with self._conn() as cx:
            cx.execute(self.SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        cx = sqlite3.connect(self._db_path, timeout=10)
        cx.row_factory = sqlite3.Row
        return cx

    def get(self, key: str, default=None) -> Any:
        with self._conn() as cx:
            row = cx.execute("SELECT payload FROM jobs WHERE id = ?", (key,)).fetchone()
        if row is None:
            return default
        return _deserialize(row["payload"])

    def set(self, key: str, value: dict) -> None:
        payload = _serialize(value)
        import time
        ts = int(time.time())
        with self._conn() as cx:
            cx.execute(
                "INSERT INTO jobs(id, payload, updated) VALUES (?, ?, ?)"
                " ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,"
                " updated=excluded.updated",
                (key, payload, ts),
            )
            cx.commit()

    def delete(self, key: str) -> None:
        with self._conn() as cx:
            cx.execute("DELETE FROM jobs WHERE id = ?", (key,))
            cx.commit()

    def keys(self) -> Iterator[str]:
        with self._conn() as cx:
            rows = cx.execute("SELECT id FROM jobs").fetchall()
        return iter([r["id"] for r in rows])


class _TrackedDict(dict):
    """A dict that writes back to its JobStore on any mutation.

    Returned from JobDictProxy.__getitem__ / .get() so that existing code
    like ``_jobs[id]["stage"] = "rendering"`` persists to SQLite too. Without
    this wrapper the mutation would happen on a deserialized JSON copy and
    silently vanish.
    """

    def __init__(self, backend: JobStore, key: str, data: dict):
        super().__init__(data)
        self.__backend = backend
        self.__key = key

    def _persist(self) -> None:
        # Snapshot to a plain dict so the backend gets a stable JSON payload.
        self.__backend.set(self.__key, dict(self))

    def __setitem__(self, k, v):
        super().__setitem__(k, v)
        self._persist()

    def __delitem__(self, k):
        super().__delitem__(k)
        self._persist()

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._persist()

    def setdefault(self, k, default=None):
        out = super().setdefault(k, default)
        self._persist()
        return out

    def pop(self, k, *args):
        out = super().pop(k, *args)
        self._persist()
        return out

    def clear(self):
        super().clear()
        self._persist()


class JobDictProxy:
    """Dict-like façade that the existing worker code can keep using.

    Supports the operations the existing code does:
        store[key] = value     (set)
        store[key]             (get; KeyError if missing) — returns a
                                 _TrackedDict so in-place mutations persist
        store.get(key, default)
        store.pop(key, default)
        key in store
    """

    def __init__(self, backend: JobStore):
        self._backend = backend

    def __getitem__(self, key: str) -> dict:
        val = self._backend.get(key)
        if val is None:
            raise KeyError(key)
        return _TrackedDict(self._backend, key, val)

    def __setitem__(self, key: str, value: dict) -> None:
        self._backend.set(key, value)

    def __contains__(self, key: str) -> bool:
        return self._backend.get(key) is not None

    def get(self, key: str, default=None) -> Any:
        val = self._backend.get(key)
        if val is None:
            return default
        return _TrackedDict(self._backend, key, val)

    def pop(self, key: str, default=None) -> Any:
        val = self._backend.get(key, default)
        self._backend.delete(key)
        return val


def build_default_store() -> JobStore:
    """Pick a store based on the LUMEN_JOBS_DB env var."""
    db_path = os.environ.get("LUMEN_JOBS_DB", "").strip()
    if db_path:
        return SqliteJobStore(db_path)
    return InMemoryJobStore()
