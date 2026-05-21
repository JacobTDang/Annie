"""Structural assertions for the DP Practice starter catalog.

The catalog lives in `frontend/src/data/dpPracticeProblems.ts` and is
referenced by the new DP Practice page. We don't parse TypeScript here —
just regex out the scene names and pattern keys and confirm they line
up with backend's SCENE_REGISTRY. Catches the typical rename drift
where a backend scene gets renamed but the static catalog doesn't.
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
_CATALOG = os.path.join(_REPO_ROOT, "frontend", "src", "data",
                          "dpPracticeProblems.ts")
_PAGE = os.path.join(_REPO_ROOT, "frontend", "src", "pages",
                       "DPPracticePage.tsx")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


_VALID_PATTERNS = frozenset({
    "knapsack_01", "lcs", "edit_distance",
    "coin_change_2d", "lis", "dp_progression",
})


def test_catalog_file_exists():
    assert os.path.exists(_CATALOG), f"missing {_CATALOG}"


def test_catalog_patterns_match_scene_registry():
    """Every `pattern: "..."` value must be a real SCENE_REGISTRY key."""
    from renderer.worker import SCENE_REGISTRY
    text = _read(_CATALOG)
    found = re.findall(r'pattern:\s*"([a-z0-9_]+)"', text)
    assert found, "no `pattern: \"...\"` entries found — catalog likely empty"
    for p in found:
        assert p in _VALID_PATTERNS, f"unknown pattern in catalog: {p}"
        assert p in SCENE_REGISTRY, (
            f"pattern '{p}' isn't in SCENE_REGISTRY — backend renamed "
            f"the scene but the static catalog still references it"
        )


def test_catalog_scenes_match_scene_registry():
    """Every `scene: "..."` value in the steps must be a SCENE_REGISTRY key."""
    from renderer.worker import SCENE_REGISTRY
    text = _read(_CATALOG)
    found = re.findall(r'scene:\s*"([a-z0-9_]+)"', text)
    assert found, "no `scene: \"...\"` step entries found"
    for s in found:
        assert s in SCENE_REGISTRY, f"step references unknown scene: {s}"


def test_catalog_topic_ids_match_patterns():
    """For SRS-aware difficulty hints to work, each problem's topicId
    must match its pattern (the SRS system keys by topicId)."""
    text = _read(_CATALOG)
    # Find each problem block by looking for the pattern, then the topicId
    # in the same nearby region. Loose regex over the TS source.
    entries = re.findall(
        r'pattern:\s*"([a-z0-9_]+)"[\s\S]*?topicId:\s*"([a-z0-9_]+)"',
        text,
    )
    assert entries, "couldn't extract pattern+topicId pairs"
    for pattern, topic_id in entries:
        assert pattern == topic_id, (
            f"pattern '{pattern}' has topicId '{topic_id}' — they must "
            f"match for SRS scheduling to apply correctly"
        )


def test_every_problem_has_non_empty_starter_code():
    """Catches an empty `python: ""` or `cpp: ""` field which would let
    the user click "Show solution" and see nothing."""
    text = _read(_CATALOG)
    # Find each starterCode object and check for non-empty referenced consts
    refs = re.findall(
        r"starterCode:\s*\{\s*python:\s*([A-Z_]+),\s*cpp:\s*([A-Z_]+)\s*\}",
        text,
    )
    assert refs, "starterCode references not found in expected shape"
    for py_const, cpp_const in refs:
        # Both must be uppercase const names (not "" inline)
        assert py_const.isupper() and "_" in py_const, (
            f"python starter must reference a const, got: {py_const}"
        )
        assert cpp_const.isupper() and "_" in cpp_const, (
            f"cpp starter must reference a const, got: {cpp_const}"
        )
        # The const must be defined earlier in the file with non-empty body
        py_def = re.search(rf"const {py_const} = `([\s\S]*?)`;", text)
        cpp_def = re.search(rf"const {cpp_const} = `([\s\S]*?)`;", text)
        assert py_def and py_def.group(1).strip(), (
            f"{py_const} is empty — cards referencing it will have no Python code"
        )
        assert cpp_def and cpp_def.group(1).strip(), (
            f"{cpp_const} is empty — cards referencing it will have no C++ code"
        )


def test_page_is_wired_into_app():
    app = _read(os.path.join(_REPO_ROOT, "frontend", "src", "App.tsx"))
    assert "DPPracticePage" in app
    assert '"dp-practice"' in app
    assert "Brain" in app


def test_page_uses_dp_practice_catalog():
    """The page must import DP_PRACTICE_PROBLEMS — otherwise it renders empty."""
    text = _read(_PAGE)
    assert "DP_PRACTICE_PROBLEMS" in text
    assert "dpPracticeProblems" in text


def test_page_uses_difficulty_hint_for_srs_badges():
    """The SRS-aware Practice more / Mastered badges must hook into the
    existing quiz-history difficulty hint."""
    text = _read(_PAGE)
    assert "difficultyHintFor" in text


def test_page_posts_to_render_lesson():
    """Each Render click must POST to /api/render-lesson (existing endpoint)
    rather than reimplementing the render submit."""
    text = _read(_PAGE)
    assert "/api/render-lesson" in text


def test_catalog_has_coverage_for_every_pattern():
    """Every DP pattern must have at least one starter entry — otherwise
    the chip filter shows an empty grid."""
    text = _read(_CATALOG)
    found = set(re.findall(r'pattern:\s*"([a-z0-9_]+)"', text))
    missing = _VALID_PATTERNS - found
    assert not missing, f"patterns with no starter entries: {missing}"
