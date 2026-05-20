"""Tests for the SQLite job store + dict proxy (Item #13)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from renderer.job_store import (
    InMemoryJobStore,
    JobDictProxy,
    SqliteJobStore,
    build_default_store,
)


# ─────────────────────────────────────────────────────────────────────────────
# InMemory backend
# ─────────────────────────────────────────────────────────────────────────────


def test_inmemory_set_and_get():
    s = InMemoryJobStore()
    s.set("a", {"status": "pending"})
    assert s.get("a") == {"status": "pending"}


def test_inmemory_get_missing_returns_default():
    s = InMemoryJobStore()
    assert s.get("missing") is None
    assert s.get("missing", "fallback") == "fallback"


# ─────────────────────────────────────────────────────────────────────────────
# SQLite backend — the core persistence regression for Item #13
# ─────────────────────────────────────────────────────────────────────────────


def test_sqlite_persists_across_reopen(tmp_path):
    """The core promise: write, drop the store, reopen with same path,
    read back the same value."""
    db = str(tmp_path / "jobs.db")

    s1 = SqliteJobStore(db)
    s1.set("j1", {"status": "done", "url": "/media/x.mp4"})

    # Drop the reference + open a fresh store — simulates a process restart.
    del s1
    s2 = SqliteJobStore(db)
    got = s2.get("j1")
    assert got == {"status": "done", "url": "/media/x.mp4"}


def test_sqlite_set_overwrites(tmp_path):
    db = str(tmp_path / "jobs.db")
    s = SqliteJobStore(db)
    s.set("j", {"status": "pending"})
    s.set("j", {"status": "done", "url": "/x"})
    assert s.get("j")["status"] == "done"


def test_sqlite_delete_removes(tmp_path):
    db = str(tmp_path / "jobs.db")
    s = SqliteJobStore(db)
    s.set("j", {"x": 1})
    s.delete("j")
    assert s.get("j") is None


def test_sqlite_keys_lists_all(tmp_path):
    db = str(tmp_path / "jobs.db")
    s = SqliteJobStore(db)
    s.set("a", {})
    s.set("b", {})
    s.set("c", {})
    assert set(s.keys()) == {"a", "b", "c"}


def test_sqlite_handles_unicode_and_nested(tmp_path):
    db = str(tmp_path / "jobs.db")
    s = SqliteJobStore(db)
    s.set("j", {"title": "Riemann — ∫ x²", "steps": [{"tool": "show_array"}]})
    got = s.get("j")
    assert got["title"] == "Riemann — ∫ x²"
    assert got["steps"][0]["tool"] == "show_array"


# ─────────────────────────────────────────────────────────────────────────────
# JobDictProxy — dict-shaped façade behavior
# ─────────────────────────────────────────────────────────────────────────────


def test_proxy_basic_dict_ops():
    s = InMemoryJobStore()
    proxy = JobDictProxy(s)
    proxy["a"] = {"status": "pending"}
    assert "a" in proxy
    assert proxy["a"]["status"] == "pending"
    assert proxy.get("missing") is None
    assert proxy.get("missing", "x") == "x"


def test_proxy_missing_key_raises_keyerror():
    s = InMemoryJobStore()
    proxy = JobDictProxy(s)
    with pytest.raises(KeyError):
        _ = proxy["nope"]


def test_proxy_inplace_mutation_persists_to_sqlite(tmp_path):
    """The critical regression: `_jobs[id]["stage"] = "rendering"`
    must persist to the SQLite backend, not vanish on a deserialized copy."""
    db = str(tmp_path / "jobs.db")
    s = SqliteJobStore(db)
    proxy = JobDictProxy(s)
    proxy["j"] = {"status": "pending", "stage": "queued"}
    # In-place mutation — used pervasively by the worker
    proxy["j"]["stage"] = "rendering"
    proxy["j"]["progress"] = 0.42

    # Reopen the store: changes must have been flushed
    s2 = SqliteJobStore(db)
    got = s2.get("j")
    assert got["stage"] == "rendering"
    assert got["progress"] == 0.42


def test_proxy_pop_removes_from_backend(tmp_path):
    db = str(tmp_path / "jobs.db")
    s = SqliteJobStore(db)
    proxy = JobDictProxy(s)
    proxy["j"] = {"x": 1}
    proxy.pop("j", None)
    assert s.get("j") is None


# ─────────────────────────────────────────────────────────────────────────────
# build_default_store env-var routing
# ─────────────────────────────────────────────────────────────────────────────


def test_build_default_store_defaults_to_in_memory(monkeypatch):
    monkeypatch.delenv("LUMEN_JOBS_DB", raising=False)
    s = build_default_store()
    assert isinstance(s, InMemoryJobStore)


def test_build_default_store_uses_sqlite_when_env_set(monkeypatch, tmp_path):
    db = str(tmp_path / "jobs.db")
    monkeypatch.setenv("LUMEN_JOBS_DB", db)
    s = build_default_store()
    assert isinstance(s, SqliteJobStore)
    # Smoke check: it actually works
    s.set("j", {"x": 1})
    assert s.get("j") == {"x": 1}
