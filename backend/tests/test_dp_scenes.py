"""Structural + smoke tests for the 2D DP scene family (Phase 2-3 of the
DP interview-prep batch).

Each scene gets a unit-level test that:
  - imports the class without crashing (catches syntax errors fast)
  - asserts it's registered in SCENE_REGISTRY with the right key
  - asserts its Pydantic schema accepts canonical input + rejects garbage

Integration tests (slow render via subprocess) run only with -m integration
and live alongside the existing test_calculus_scenes.py harness — too
expensive to gate unit-suite turnaround on.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


BACKEND = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))


# ─────────────────────────────────────────────────────────────────────────────
# Scene registration + class importability
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("scene_key,class_name", [
    ("knapsack_01",     "Knapsack01Scene"),
    ("lcs",             "LCSScene"),
    ("edit_distance",   "EditDistanceScene"),
    ("coin_change_2d",  "CoinChange2DScene"),
    ("lis",             "LISScene"),
    ("dp_progression",  "DPProgressionScene"),
])
def test_dp_scene_registered(scene_key, class_name):
    """Every new DP scene must be in SCENE_REGISTRY pointing at the right class."""
    from renderer.worker import SCENE_REGISTRY
    assert scene_key in SCENE_REGISTRY, f"{scene_key} not registered"
    file_path, cls = SCENE_REGISTRY[scene_key]
    assert cls == class_name
    assert file_path == "scenes/dsa_pattern_scene.py"


@pytest.mark.parametrize("class_name", [
    "Knapsack01Scene",
    "LCSScene",
    "EditDistanceScene",
    "CoinChange2DScene",
    "LISScene",
    "DPProgressionScene",
])
def test_dp_scene_class_importable(class_name):
    """If the class fails to import, render time will surface a confusing
    error — surface it here first."""
    import importlib
    mod = importlib.import_module("scenes.dsa_pattern_scene")
    assert hasattr(mod, class_name), f"{class_name} missing from dsa_pattern_scene"
    cls = getattr(mod, class_name)
    assert callable(cls)
    # Manim scene classes always have construct()
    assert hasattr(cls, "construct")


# ─────────────────────────────────────────────────────────────────────────────
# Schema validation
# ─────────────────────────────────────────────────────────────────────────────


def test_knapsack_01_schema_accepts_canonical_input():
    from schemas.types import Knapsack01Schema
    s = Knapsack01Schema(
        items=[{"weight": 2, "value": 3}, {"weight": 3, "value": 4}],
        capacity=5,
    )
    assert s.scene == "knapsack_01"
    assert s.capacity == 5
    assert len(s.items) == 2


def test_knapsack_01_schema_caps_items_and_capacity():
    """Render-time guard against an LLM passing a 20-item knapsack."""
    from schemas.types import Knapsack01Schema
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Knapsack01Schema(items=[{"weight": 1, "value": 1}] * 6,
                          capacity=3)
    with pytest.raises(ValidationError):
        Knapsack01Schema(items=[{"weight": 1, "value": 1}], capacity=99)


def test_lcs_schema_validates_string_lengths():
    from schemas.types import LCSSchema
    from pydantic import ValidationError
    LCSSchema(s1="abc", s2="ab")           # OK
    with pytest.raises(ValidationError):
        LCSSchema(s1="", s2="x")            # empty rejected
    with pytest.raises(ValidationError):
        LCSSchema(s1="x" * 9, s2="y")       # too long


def test_edit_distance_schema_caps_string_length():
    from schemas.types import EditDistanceSchema
    from pydantic import ValidationError
    EditDistanceSchema(s1="cat", s2="bat")
    with pytest.raises(ValidationError):
        EditDistanceSchema(s1="x" * 7, s2="y")


def test_coin_change_2d_schema_accepts_canonical_input():
    from schemas.types import CoinChange2DSchema
    s = CoinChange2DSchema(coins=[1, 2, 5], amount=5)
    assert s.coins == [1, 2, 5]
    assert s.amount == 5


def test_lis_schema_requires_at_least_two_elements():
    from schemas.types import LISSchema
    from pydantic import ValidationError
    LISSchema(nums=[1, 2])
    with pytest.raises(ValidationError):
        LISSchema(nums=[1])    # too few


def test_dp_progression_schema_enumerates_problems():
    from schemas.types import DPProgressionSchema
    from pydantic import ValidationError
    DPProgressionSchema(problem="fibonacci", n=5)
    DPProgressionSchema(problem="unique_paths", n=4)
    with pytest.raises(ValidationError):
        DPProgressionSchema(problem="bogus_problem", n=4)


# ─────────────────────────────────────────────────────────────────────────────
# Integration: actually render each scene to MP4. Slow — opt-in.
# ─────────────────────────────────────────────────────────────────────────────


def _render(tmp_path: Path, scene_class: str, params: dict) -> subprocess.CompletedProcess:
    job_id = f"test-dp-{scene_class.lower()}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / f"{job_id}.json").write_text(json.dumps(params))

    media_dir = tmp_path / "media"
    return subprocess.run(
        [sys.executable, "-m", "manim",
         "-ql", "--media_dir", str(media_dir),
         "--disable_caching",
         str(BACKEND / "scenes" / "dsa_pattern_scene.py"), scene_class],
        cwd=str(BACKEND),
        env={**os.environ, "LUMEN_JOB_ID": job_id,
             "LUMEN_JOB_DIR": str(tmp_path)},
        capture_output=True, text=True, timeout=180,
    )


@pytest.mark.integration
@pytest.mark.parametrize("scene_class,params", [
    ("Knapsack01Scene",  {"items": [{"weight": 2, "value": 3},
                                    {"weight": 3, "value": 4}],
                          "capacity": 4}),
    ("LCSScene",         {"s1": "AGC", "s2": "GAC"}),
    ("EditDistanceScene", {"s1": "cat", "s2": "bat"}),
    ("CoinChange2DScene", {"coins": [1, 2], "amount": 3}),
    ("LISScene",         {"nums": [3, 1, 4, 1, 5]}),
    ("DPProgressionScene", {"problem": "fibonacci", "n": 4}),
])
def test_dp_scene_renders_to_mp4(tmp_path, scene_class, params):
    res = _render(tmp_path, scene_class, params)
    assert res.returncode == 0, (
        f"render failed for {scene_class}:\nstdout={res.stdout}\nstderr={res.stderr}"
    )
    mp4s = list((tmp_path / "media").rglob("*.mp4"))
    assert mp4s, f"no MP4 produced for {scene_class}"
    assert mp4s[0].stat().st_size > 1000, (
        f"{scene_class} MP4 is suspiciously small: {mp4s[0].stat().st_size} bytes"
    )
