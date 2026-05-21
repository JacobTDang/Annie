"""Tests for the semantic-step chapter recorder (Phase 4 DP-prep)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scenes.dsa_primitives import ChapterRecorder


class _Recorder(ChapterRecorder):
    """Bare-bones scene-like host: only has the bits ChapterRecorder needs."""
    def __init__(self, time: float = 0.0):
        self.renderer = type("R", (), {"time": time})()


def test_mark_chapter_appends_with_time():
    r = _Recorder(time=1.5)
    r.mark_chapter("first")
    r.renderer.time = 2.25
    r.mark_chapter("second")
    assert r._chapters == [
        {"t": 1.5, "label": "first"},
        {"t": 2.25, "label": "second"},
    ]


def test_mark_chapter_handles_missing_renderer():
    """Calling mark_chapter before the scene's renderer is fully attached
    must still record (with t=0.0) instead of raising."""
    r = ChapterRecorder()                           # no renderer at all
    r.mark_chapter("early")
    assert r._chapters == [{"t": 0.0, "label": "early"}]


def test_flush_chapters_writes_to_env_path(tmp_path, monkeypatch):
    out_path = tmp_path / "chapters.json"
    monkeypatch.setenv("LUMEN_CHAPTERS_OUT", str(out_path))
    r = _Recorder(time=0.0)
    r.mark_chapter("a")
    r.renderer.time = 5.0
    r.mark_chapter("b")
    r.flush_chapters()
    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data == [{"t": 0.0, "label": "a"}, {"t": 5.0, "label": "b"}]


def test_flush_chapters_silent_without_env(monkeypatch, tmp_path):
    """When LUMEN_CHAPTERS_OUT is unset, flush_chapters must be a no-op
    (no temp file created, no exception)."""
    monkeypatch.delenv("LUMEN_CHAPTERS_OUT", raising=False)
    r = _Recorder()
    r.mark_chapter("only-in-memory")
    r.flush_chapters()
    # In-memory list is still populated; nothing happens on disk
    assert r._chapters == [{"t": 0.0, "label": "only-in-memory"}]


def test_flush_chapters_silent_when_empty(monkeypatch, tmp_path):
    """Even with the env var set, an empty chapter list must NOT
    overwrite an existing file with `[]` — common for non-DP scenes
    that don't call mark_chapter at all."""
    out_path = tmp_path / "chapters.json"
    monkeypatch.setenv("LUMEN_CHAPTERS_OUT", str(out_path))
    r = _Recorder()
    r.flush_chapters()  # no marks recorded
    assert not out_path.exists()


def test_flush_chapters_swallows_write_errors(monkeypatch, tmp_path):
    """Disk-full / permission denied / etc must not break the render."""
    # Point to a directory path (which can't be opened as a file)
    monkeypatch.setenv("LUMEN_CHAPTERS_OUT", str(tmp_path))
    r = _Recorder()
    r.mark_chapter("x")
    # Should not raise
    r.flush_chapters()


def test_dp_scenes_mix_in_chapter_recorder():
    """Every shipped DP scene must subclass ChapterRecorder so the env-var
    wiring actually fires. Catches a refactor that forgets the mixin."""
    from scenes import dsa_pattern_scene as pat
    for cls_name in ["Knapsack01Scene", "LCSScene", "EditDistanceScene",
                     "CoinChange2DScene", "LISScene", "DPProgressionScene"]:
        cls = getattr(pat, cls_name)
        assert issubclass(cls, ChapterRecorder), (
            f"{cls_name} must mix in ChapterRecorder for step controls"
        )


def test_construct_wraps_in_try_finally():
    """Each DP scene's construct() must delegate to _construct_impl()
    inside try/finally so flush_chapters fires even on render failure."""
    import inspect
    from scenes import dsa_pattern_scene as pat
    for cls_name in ["Knapsack01Scene", "LCSScene", "EditDistanceScene",
                     "CoinChange2DScene", "LISScene", "DPProgressionScene"]:
        cls = getattr(pat, cls_name)
        src = inspect.getsource(cls.construct)
        assert "flush_chapters" in src, (
            f"{cls_name}.construct() must call self.flush_chapters() in a "
            f"finally block — otherwise failed renders lose their chapters"
        )
        assert "finally" in src, f"{cls_name}.construct() missing try/finally"
