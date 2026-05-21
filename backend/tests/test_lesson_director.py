"""
Tests for the Lesson Director agent and the dynamic tool executor.

Unit tests: mock the LLM (_call_model) — fast, no Manim, no API keys.
Integration tests: marked with @pytest.mark.integration — render a real DynamicScene.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.lesson_director import (
    NarrativePlan,
    ScenePlan,
    ToolCall,
    narrative_plan,
    build_scene,
    direct_lesson,
)
from schemas.tools import VALID_TOOL_NAMES, VISUAL_TOOLS
from schemas.types import LessonPlan, StepPlan


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

MOCK_NARRATIVE = {
    "lesson_title": "Two Pointers for Palindrome",
    "core_insight": "Using two pointers from opposite ends avoids redundant comparisons.",
    "narrative_arc": "hook: show O(n²) nested loops → insight: opposite pointer convergence → resolution: O(n) palindrome check",
    "scenes": [
        {"title": "The Brute Force Problem", "objective": "Understand why nested loops are slow.", "is_aha_moment": False},
        {"title": "The Pointer Insight", "objective": "See how two pointers replace the inner loop.", "is_aha_moment": True},
        {"title": "The Solution", "objective": "Watch the algorithm find 'racecar' is a palindrome.", "is_aha_moment": False},
    ],
}

MOCK_TOOL_CALLS = [
    {"tool": "show_array", "args": {"values": ["r","a","c","e","c","a","r"], "element_id": "array_0", "label": "s"}},
    {"tool": "set_caption", "args": {"text": "Two pointers converge from both ends"}},
    {"tool": "add_pointer", "args": {"name": "L", "element_id": "array_0", "index": 0, "color": "GREEN"}},
    {"tool": "add_pointer", "args": {"name": "R", "element_id": "array_0", "index": 6, "color": "RED"}},
    {"tool": "highlight_cells", "args": {"element_id": "array_0", "indices": [0, 6], "color": "YELLOW"}},
    {"tool": "emphasize", "args": {"element_id": "array_0", "index": -1}},
    {"tool": "pause", "args": {"beats": 2}},
    {"tool": "show_result", "args": {"value": "True", "label": "is_palindrome"}},
]


# ─────────────────────────────────────────────────────────────────────────────
# Phase A — tool schema sanity checks
# ─────────────────────────────────────────────────────────────────────────────

def test_all_tools_have_required_fields():
    for t in VISUAL_TOOLS:
        assert "name" in t, f"Tool missing 'name': {t}"
        assert "description" in t, f"Tool '{t['name']}' missing 'description'"
        assert "parameters" in t, f"Tool '{t['name']}' missing 'parameters'"


def test_valid_tool_names_matches_catalog():
    assert len(VALID_TOOL_NAMES) == len(VISUAL_TOOLS)
    for t in VISUAL_TOOLS:
        assert t["name"] in VALID_TOOL_NAMES


def test_tool_names_are_snake_case():
    for name in VALID_TOOL_NAMES:
        assert name == name.lower(), f"Tool name not lowercase: {name}"
        assert " " not in name, f"Tool name contains space: {name}"


# ─────────────────────────────────────────────────────────────────────────────
# Phase C — lesson director unit tests (mocked LLM)
# ─────────────────────────────────────────────────────────────────────────────

def test_narrative_plan_parses_correctly(mocker):
    mocker.patch(
        "agent.lesson_director._call_model",
        return_value=json.dumps(MOCK_NARRATIVE),
    )
    plan = narrative_plan("Check if a string is a palindrome")
    assert plan.lesson_title == "Two Pointers for Palindrome"
    assert len(plan.scenes) == 3
    assert any(s.is_aha_moment for s in plan.scenes)
    assert plan.core_insight


def test_narrative_plan_enforces_2_to_4_scenes(mocker):
    bad = {**MOCK_NARRATIVE, "scenes": [MOCK_NARRATIVE["scenes"][0]]}  # only 1 scene
    mocker.patch("agent.lesson_director._call_model", return_value=json.dumps(bad))
    with pytest.raises(ValueError, match="2-4 scenes"):
        narrative_plan("anything")


def test_narrative_plan_includes_length_hint_in_system(mocker):
    """Item #10 regression: target_minutes must shape the prompt sent to the LLM."""
    captured = {}

    def fake_call(system, user, *args, **kwargs):
        captured["system"] = system
        return json.dumps(MOCK_NARRATIVE)

    mocker.patch("agent.lesson_director._call_model", side_effect=fake_call)
    narrative_plan("any question", target_minutes=0.5)
    assert "very short" in captured["system"].lower()
    assert "target length" in captured["system"].lower()

    captured.clear()
    narrative_plan("any question", target_minutes=5.0)
    assert "long" in captured["system"].lower()


def test_build_scene_includes_carryover_element_ids(mocker):
    """Item #2 regression: previous_scene_elements must appear in the scene prompt."""
    captured = {}

    def fake_call(system, user, *args, **kwargs):
        captured["user"] = user
        return json.dumps(MOCK_TOOL_CALLS)

    mocker.patch("agent.lesson_director._call_model", side_effect=fake_call)
    sp = ScenePlan(title="t", objective="o", is_aha_moment=False)
    build_scene("q", sp, "insight",
                 previous_scene_elements=["arr_main", "ptr_left", "ptr_right"])
    user_text = captured["user"]
    assert "CONTINUITY" in user_text
    assert "arr_main" in user_text
    assert "ptr_left" in user_text
    assert "ptr_right" in user_text


def test_build_scene_no_continuity_block_when_no_prior_elements(mocker):
    """First-scene case: empty list → no CONTINUITY block leaks into prompt."""
    captured = {}

    def fake_call(system, user, *args, **kwargs):
        captured["user"] = user
        return json.dumps(MOCK_TOOL_CALLS)

    mocker.patch("agent.lesson_director._call_model", side_effect=fake_call)
    sp = ScenePlan(title="t", objective="o", is_aha_moment=False)
    build_scene("q", sp, "insight", previous_scene_elements=[])
    assert "CONTINUITY" not in captured["user"]


def test_accumulate_elements_carries_union_forward():
    """Scene N sees union of element_ids from scenes [0, N-1]."""
    from agent.lesson_director import _accumulate_elements
    scenes = [
        ScenePlan(title="a", objective="o", key_elements=["arr"]),
        ScenePlan(title="b", objective="o", key_elements=["ptr_L", "ptr_R"]),
        ScenePlan(title="c", objective="o", key_elements=["arr"]),  # dupe
        ScenePlan(title="d", objective="o", key_elements=["result"]),
    ]
    carry = _accumulate_elements(scenes)
    assert carry[0] == []
    assert carry[1] == ["arr"]
    assert carry[2] == ["arr", "ptr_L", "ptr_R"]
    # arr was already seen — should not duplicate
    assert carry[3] == ["arr", "ptr_L", "ptr_R"]


def test_narrative_plan_default_target_minutes_is_short(mocker):
    """Default target_minutes (1.5) should produce the short/medium hint, not very-short or long."""
    captured = {}

    def fake_call(system, user, *args, **kwargs):
        captured["system"] = system
        return json.dumps(MOCK_NARRATIVE)

    mocker.patch("agent.lesson_director._call_model", side_effect=fake_call)
    narrative_plan("any question")  # default target_minutes=1.5
    sys_text = captured["system"].lower()
    assert "target length" in sys_text
    # default 1.5 falls in the "short" bucket (1.0 ≤ x < 2.5)
    assert "short" in sys_text


def test_build_scene_returns_valid_tool_calls(mocker):
    mocker.patch(
        "agent.lesson_director._call_model",
        return_value=json.dumps(MOCK_TOOL_CALLS),
    )
    scene_plan = ScenePlan(
        title="The Pointer Insight",
        objective="See how two pointers replace the inner loop.",
        is_aha_moment=True,
    )
    calls = build_scene("palindrome check", scene_plan, "two pointers avoid redundancy")
    assert len(calls) > 0
    for c in calls:
        assert isinstance(c, ToolCall)
        assert c.tool in VALID_TOOL_NAMES


def test_build_scene_skips_unknown_tools(mocker):
    tool_calls_with_bad = MOCK_TOOL_CALLS + [{"tool": "nonexistent_tool", "args": {}}]
    mocker.patch(
        "agent.lesson_director._call_model",
        return_value=json.dumps(tool_calls_with_bad),
    )
    scene_plan = ScenePlan(title="Test", objective="Test.", is_aha_moment=False)
    calls = build_scene("test", scene_plan, "insight")
    assert all(c.tool in VALID_TOOL_NAMES for c in calls)


# ─────────────────────────────────────────────────────────────────────────────
# critique_scene — self-critique pass
# ─────────────────────────────────────────────────────────────────────────────

def test_critique_scene_returns_revised_calls(mocker):
    """When the critique LLM returns a valid revised array, those calls are returned."""
    from agent.lesson_director import critique_scene, ToolCall
    revised = [
        {"tool": "set_caption", "args": {"text": "improved"}},
        {"tool": "show_array", "args": {"values": ["a"], "element_id": "arr"}},
        {"tool": "emphasize", "args": {"element_id": "arr"}},
        {"tool": "pause", "args": {"beats": 2}},
        {"tool": "show_result", "args": {"value": "ok"}},
    ]
    mocker.patch("agent.lesson_director._call_model", return_value=json.dumps(revised))
    original = [ToolCall(tool="show_array", args={"values": ["a"]})]
    sp = ScenePlan(title="t", objective="o", is_aha_moment=True)
    out = critique_scene(original, sp, "insight")
    assert [c.tool for c in out] == [
        "set_caption", "show_array", "emphasize", "pause", "show_result"
    ]


def test_critique_scene_falls_back_on_invalid_json(mocker):
    """If the critique LLM returns garbage, original tool_calls survive."""
    from agent.lesson_director import critique_scene, ToolCall
    mocker.patch("agent.lesson_director._call_model", return_value="not json")
    original = [
        ToolCall(tool="show_array", args={"values": ["a"]}),
        ToolCall(tool="emphasize", args={"element_id": "arr"}),
        ToolCall(tool="show_result", args={"value": "x"}),
    ]
    sp = ScenePlan(title="t", objective="o", is_aha_moment=True)
    out = critique_scene(original, sp, "insight")
    assert out == original


def test_critique_scene_falls_back_on_too_few_calls(mocker):
    """If critique returns a list missing the structural pieces, keep original."""
    from agent.lesson_director import critique_scene, ToolCall
    # Returns only 1 call (no caption, no element, no emphasize, no result)
    mocker.patch(
        "agent.lesson_director._call_model",
        return_value=json.dumps([{"tool": "pause", "args": {}}]),
    )
    original = [ToolCall(tool=t, args={}) for t in
                ["set_caption", "show_array", "emphasize", "pause", "show_result"]]
    sp = ScenePlan(title="t", objective="o", is_aha_moment=True)
    out = critique_scene(original, sp, "insight")
    assert len(out) == 5  # original kept because revision is structurally broken


def test_critique_accepts_structurally_complete_simplification(mocker):
    """Bug 6 regression: a tight 4-call scene with all structural pieces should
    BEAT a bloated 10-call original. Old code rejected by length floor."""
    from agent.lesson_director import critique_scene, ToolCall
    # 4-call revision: has caption, element, exactly 1 emphasize, terminator
    revised = [
        {"tool": "set_caption", "args": {"text": "why"}},
        {"tool": "show_array", "args": {"values": ["1"], "element_id": "arr"}},
        {"tool": "emphasize", "args": {"element_id": "arr"}},
        {"tool": "show_result", "args": {"value": "done"}},
    ]
    mocker.patch("agent.lesson_director._call_model",
                 return_value=json.dumps(revised))
    # Original is bloated 10 calls
    original = [ToolCall(tool=t, args={}) for t in
                ["set_caption", "show_array", "highlight_cells", "pause",
                 "move_pointer", "highlight_cells", "pause", "emphasize",
                 "pause", "show_result"]]
    sp = ScenePlan(title="t", objective="o", is_aha_moment=True)
    out = critique_scene(original, sp, "insight")
    assert len(out) == 4  # accepted the tight revision


def test_critique_rejects_structurally_incomplete(mocker):
    """A revision missing 'emphasize' is rejected — keep original even if longer."""
    from agent.lesson_director import critique_scene, ToolCall
    # Missing emphasize, missing terminator
    revised = [
        {"tool": "set_caption", "args": {"text": "x"}},
        {"tool": "show_array", "args": {"values": ["1"], "element_id": "arr"}},
        {"tool": "highlight_cells", "args": {"element_id": "arr", "indices": [0]}},
        {"tool": "pause", "args": {}},
        {"tool": "pause", "args": {}},
    ]
    mocker.patch("agent.lesson_director._call_model",
                 return_value=json.dumps(revised))
    original = [ToolCall(tool=t, args={}) for t in
                ["set_caption", "show_array", "emphasize", "show_result"]]
    sp = ScenePlan(title="t", objective="o", is_aha_moment=True)
    out = critique_scene(original, sp, "insight")
    assert len(out) == 4   # original kept


def test_critique_scene_empty_input_returns_empty(mocker):
    """If build_scene returned no calls, critique short-circuits."""
    from agent.lesson_director import critique_scene
    mock = mocker.patch("agent.lesson_director._call_model")
    sp = ScenePlan(title="t", objective="o", is_aha_moment=False)
    out = critique_scene([], sp, "insight")
    assert out == []
    mock.assert_not_called()


def test_build_scene_safe_falls_back_on_connection_error(mocker):
    """Bug 2 regression: ConnectionError (or any non-ValueError) from the LLM
    must NOT propagate out of _build_scene_safe — it must return the minimal
    fallback so the lesson can still render with a placeholder scene."""
    from agent.lesson_director import _build_scene_safe

    mocker.patch(
        "agent.lesson_director.build_scene",
        side_effect=ConnectionError("network down"),
    )
    sp = ScenePlan(title="title", objective="objective", is_aha_moment=False)
    # Must not raise; must return the 3-call fallback
    calls = _build_scene_safe("q", sp, "core_insight", "", max_retries=2)
    assert len(calls) == 3
    tools = [c.tool for c in calls]
    assert tools == ["set_caption", "show_text", "pause"]


def test_build_scene_safe_invokes_critique(mocker):
    """_build_scene_safe runs critique after a successful build_scene."""
    from agent.lesson_director import _build_scene_safe, ToolCall

    built = [
        ToolCall(tool="set_caption", args={"text": "x"}),
        ToolCall(tool="show_array", args={"values": ["a"]}),
        ToolCall(tool="emphasize", args={"element_id": "arr"}),
        ToolCall(tool="show_result", args={"value": "y"}),
    ]
    mocker.patch("agent.lesson_director.build_scene", return_value=built)
    critique = mocker.patch("agent.lesson_director.critique_scene", return_value=built)

    sp = ScenePlan(title="t", objective="o", is_aha_moment=False)
    _build_scene_safe("q", sp, "insight", "", max_retries=2)
    critique.assert_called_once()


def test_build_scene_includes_previous_error_in_prompt(mocker):
    """When previous_error is given, the user message embeds it as guidance."""
    from agent.lesson_director import build_scene
    captured = {}
    def fake_call(system, user):
        captured["user"] = user
        return json.dumps(MOCK_TOOL_CALLS)
    mocker.patch("agent.lesson_director._call_model", side_effect=fake_call)
    sp = ScenePlan(title="t", objective="o", is_aha_moment=False)
    build_scene("q", sp, "core", previous_error="IndexError: 5 out of range")
    assert "previous attempt" in captured["user"].lower()
    assert "IndexError" in captured["user"]


def test_build_scene_without_previous_error_has_clean_prompt(mocker):
    """Default path: no error-recovery note in the user message."""
    from agent.lesson_director import build_scene
    captured = {}
    def fake_call(system, user):
        captured["user"] = user
        return json.dumps(MOCK_TOOL_CALLS)
    mocker.patch("agent.lesson_director._call_model", side_effect=fake_call)
    sp = ScenePlan(title="t", objective="o", is_aha_moment=False)
    build_scene("q", sp, "core")
    assert "previous attempt" not in captured["user"].lower()


def test_emphasize_supports_pace_arg():
    """The pace arg is wired through the tool catalog."""
    from schemas.tools import VISUAL_TOOLS
    emp = next(t for t in VISUAL_TOOLS if t["name"] == "emphasize")
    assert "pace" in emp["parameters"]
    assert set(emp["parameters"]["pace"]["enum"]) == {"slow", "normal", "fast"}


def test_narrative_plan_accepts_known_style(mocker):
    """When style is given, the system prompt is prefixed with the style hint."""
    from agent.lesson_director import narrative_plan, NARRATIVE_STYLES
    captured = {}
    def fake_call(system, user):
        captured["system"] = system
        return json.dumps(MOCK_NARRATIVE)
    mocker.patch("agent.lesson_director._call_model", side_effect=fake_call)
    narrative_plan("any question", style="socratic")
    assert NARRATIVE_STYLES["socratic"] in captured["system"]


def test_narrative_plan_ignores_unknown_style(mocker):
    """Unknown style → fall back silently to default prompt (no crash)."""
    from agent.lesson_director import narrative_plan
    captured = {}
    def fake_call(system, user):
        captured["system"] = system
        return json.dumps(MOCK_NARRATIVE)
    mocker.patch("agent.lesson_director._call_model", side_effect=fake_call)
    narrative_plan("any question", style="not_a_real_style")
    assert "STYLE:" not in captured["system"]


def test_direct_lesson_endpoint_rejects_invalid_style(client):
    res = client.post("/api/direct-lesson",
                      json={"question": "x", "style": "bogus"})
    assert res.status_code == 400
    assert "valid" in res.get_json()


def test_direct_lesson_endpoint_accepts_valid_style(client, mocker):
    mocker.patch("app.submit_direct_lesson", return_value="job-123")
    res = client.post("/api/direct-lesson",
                      json={"question": "x", "style": "speedrun"})
    assert res.status_code == 202


def test_camera_tools_registered_in_catalog():
    """Item #7 regression: pan_to, zoom_to, zoom_out exposed to the LLM."""
    from schemas.tools import VALID_TOOL_NAMES, VISUAL_TOOLS
    assert "pan_to" in VALID_TOOL_NAMES
    assert "zoom_to" in VALID_TOOL_NAMES
    assert "zoom_out" in VALID_TOOL_NAMES
    by_name = {t["name"]: t for t in VISUAL_TOOLS}
    assert "element_id" in by_name["pan_to"]["parameters"]
    assert "level" in by_name["zoom_to"]["parameters"]
    assert by_name["zoom_out"]["required"] == []


def test_camera_tools_handlers_exist_on_executor():
    """The executor must have _tool_pan_to / _tool_zoom_to / _tool_zoom_out methods."""
    from scenes.tool_executor import ToolExecutor
    assert callable(getattr(ToolExecutor, "_tool_pan_to", None))
    assert callable(getattr(ToolExecutor, "_tool_zoom_to", None))
    assert callable(getattr(ToolExecutor, "_tool_zoom_out", None))


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 — Grid-aware DP tools (Item: grid-arrow-primitive)
# ─────────────────────────────────────────────────────────────────────────────


def test_grid_tools_in_visual_catalog():
    """The three new grid tools must be registered + grouped correctly."""
    from schemas.tools import VISUAL_TOOLS, VALID_TOOL_NAMES, _TOOL_GROUPS
    for name in ["set_grid_cell", "highlight_grid_cells", "draw_grid_arrow"]:
        assert name in VALID_TOOL_NAMES, f"missing tool: {name}"
        spec = next((t for t in VISUAL_TOOLS if t["name"] == name), None)
        assert spec is not None, f"tool {name} not in VISUAL_TOOLS list"
        assert "description" in spec and "parameters" in spec
    # Grouped under the cell/value bucket for the prompt catalog
    cell_group = _TOOL_GROUPS["## Cell / value operations"]
    for name in ["set_grid_cell", "highlight_grid_cells", "draw_grid_arrow"]:
        assert name in cell_group


def test_grid_tools_handlers_exist_on_executor():
    from scenes.tool_executor import ToolExecutor
    assert callable(getattr(ToolExecutor, "_tool_set_grid_cell", None))
    assert callable(getattr(ToolExecutor, "_tool_highlight_grid_cells", None))
    assert callable(getattr(ToolExecutor, "_tool_draw_grid_arrow", None))


def test_grid_tools_noop_when_element_missing():
    """Tools must silently no-op when the element_id isn't a grid (or
    doesn't exist). The dispatch wrapper logs but doesn't raise."""
    from scenes.tool_executor import ToolExecutor

    class _SceneStub:
        def __init__(self):
            self.plays = []
        def play(self, *args, **kwargs):
            self.plays.append(kwargs.get("run_time"))

    sc = _SceneStub()
    ex = ToolExecutor(sc)
    # No grid registered under "missing" — every tool should bail
    ex._tool_set_grid_cell("missing", 0, 0, "1")
    ex._tool_highlight_grid_cells("missing", [[0, 0]], "YELLOW")
    ex._tool_draw_grid_arrow("missing", 0, 0, 1, 0)
    assert sc.plays == []


def test_grid_tools_bounds_check():
    """Out-of-range (r, c) coordinates must not crash. Real LLM output
    occasionally has off-by-one errors — graceful no-op is the contract."""
    from scenes.tool_executor import ToolExecutor
    from scenes.dsa_primitives import GridPanel

    class _SceneStub:
        def __init__(self): self.plays = []
        def play(self, *args, **kwargs): self.plays.append(args)

    sc = _SceneStub()
    ex = ToolExecutor(sc)
    grid = GridPanel([["0", "0"], ["0", "0"]])
    ex.state["g"] = grid

    before = len(sc.plays)
    ex._tool_set_grid_cell("g", 99, 99, "x")    # row OOB
    ex._tool_set_grid_cell("g", 0, 99, "x")     # col OOB
    ex._tool_draw_grid_arrow("g", 0, 0, 5, 5)   # to OOB
    ex._tool_draw_grid_arrow("g", -1, 0, 0, 0)  # from OOB
    # Each rejected call adds 0 plays
    assert len(sc.plays) == before


def test_grid_arrow_picks_appropriate_edge_anchors():
    """GridArrow.between must choose top/bottom/left/right edge anchors
    based on relative position so the arrowhead doesn't overlap text."""
    from scenes.dsa_primitives import GridPanel, GridArrow

    grid = GridPanel([["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]])

    # Vertical: dp[0][1] → dp[1][1] (down)
    arrow_down = GridArrow.between(grid, (0, 1), (1, 1))
    assert arrow_down is not None

    # Horizontal: dp[1][0] → dp[1][1] (right)
    arrow_right = GridArrow.between(grid, (1, 0), (1, 1))
    assert arrow_right is not None

    # Diagonal: dp[0][0] → dp[1][1]
    arrow_diag = GridArrow.between(grid, (0, 0), (1, 1))
    assert arrow_diag is not None

    # Labeled arrow returns a VGroup containing the arrow + label
    from manim import VGroup
    labeled = GridArrow.between(grid, (0, 0), (1, 1), label="diag")
    assert isinstance(labeled, VGroup)


def test_show_grid_accepts_2d_or_flat_values():
    """Bug fix regression: previously _tool_show_grid passed (rows, cols,
    flat) to GridPanel(values, position, cell_size), silently erroring.
    Now it reshapes flat → 2D (or passes 2D through unchanged)."""
    from scenes.tool_executor import ToolExecutor

    plays: list = []

    class _SceneStub:
        def play(self, *args, **kwargs): plays.append(args)

    ex = ToolExecutor(_SceneStub())

    # Path 1: flat values + rows/cols → reshape
    ex._tool_set_caption = lambda **kw: None  # bypass unrelated
    ex._tool_show_grid(rows=2, cols=3, values=[1, 2, 3, 4, 5, 6],
                       element_id="flat")
    assert "flat" in ex.state
    assert ex.state["flat"].rows == 2
    assert ex.state["flat"].cols == 3

    # Path 2: already-2D values → pass through
    plays.clear()
    ex._tool_show_grid(rows=2, cols=2, values=[["a", "b"], ["c", "d"]],
                       element_id="2d")
    assert "2d" in ex.state
    assert ex.state["2d"].rows == 2
    assert ex.state["2d"].cols == 2


def test_camera_tools_noop_when_camera_lacks_frame():
    """Camera tools must silently no-op on a plain Scene that has no .frame.

    The LLM should be allowed to emit camera calls; if the scene doesn't
    support them, we drop the call rather than crashing.
    """
    from scenes.tool_executor import ToolExecutor

    class _PlainScene:
        class _Cam:
            pass

        def __init__(self):
            self.camera = self._Cam()  # no .frame
            self.plays = []

        def play(self, *args, **kwargs):
            self.plays.append(kwargs.get("run_time"))

    sc = _PlainScene()
    ex = ToolExecutor(sc)
    ex.state["whatever"] = object()
    ex._tool_pan_to("whatever")
    ex._tool_zoom_to("whatever", level=1.5)
    ex._tool_zoom_out()
    assert sc.plays == []  # nothing rendered, nothing crashed


def test_zoom_to_clamps_level():
    """zoom_to clamps level to [1.05, 2.5] so the LLM can't break the scene."""
    from scenes.tool_executor import ToolExecutor

    captured: dict = {}

    class _Frame:
        def __init__(self):
            self.animate = self  # chainable mock
        def move_to(self, *args, **kwargs):
            return self
        def scale(self, factor):
            captured["scale"] = factor
            return self

    class _SceneStub:
        def __init__(self, frame):
            self.camera = type("C", (), {"frame": frame})()
        def play(self, *args, **kwargs):
            pass

    target = type("M", (), {"get_center": lambda self: (0, 0, 0)})()
    sc = _SceneStub(_Frame())
    ex = ToolExecutor(sc)
    ex.state["t"] = target

    ex._tool_zoom_to("t", level=100.0)
    # 100 clamps to 2.5 → scale factor is 1/2.5 = 0.4
    assert abs(captured["scale"] - 0.4) < 1e-6

    ex._tool_zoom_to("t", level=0.01)
    # 0.01 clamps to 1.05 → scale factor is 1/1.05
    assert abs(captured["scale"] - (1.0 / 1.05)) < 1e-6

    ex._tool_zoom_to("t", level="not a number")  # bad input → default 1.5
    assert abs(captured["scale"] - (1.0 / 1.5)) < 1e-6


def test_tool_executor_emphasize_honors_pace():
    """Calling emphasize with pace='slow' triggers a longer play + an extra wait."""
    from scenes.tool_executor import ToolExecutor

    class _Stub:
        def __init__(self):
            self.plays = []
            self.waits = []
        def play(self, *anims, **kwargs):
            self.plays.append(kwargs.get("run_time"))
        def wait(self, t=None):
            self.waits.append(t)

    # Seed an element to emphasize
    sc = _Stub()
    executor = ToolExecutor(sc)
    from scenes.dsa_primitives import ArrayStrip
    strip = ArrayStrip(["1", "2"], position=(0, 0, 0))
    executor.state["arr"] = strip
    executor.vgroups["arr"] = strip.vgroup

    executor._tool_emphasize("arr", index=-1, pace="slow")
    assert sc.plays == [1.0]
    assert sc.waits == [0.6]    # slow includes the built-in hold

    sc.plays.clear(); sc.waits.clear()
    executor._tool_emphasize("arr", index=-1, pace="fast")
    assert sc.plays == [0.3]
    assert sc.waits == []        # fast has no hold


def test_direct_lesson_produces_lesson_plan(mocker):
    call_count = {"n": 0}

    def mock_call(system, user):
        if call_count["n"] == 0:
            call_count["n"] += 1
            return json.dumps(MOCK_NARRATIVE)
        call_count["n"] += 1
        return json.dumps(MOCK_TOOL_CALLS)

    mocker.patch("agent.lesson_director._call_model", side_effect=mock_call)
    lesson = direct_lesson("Check if a string is a palindrome")

    assert isinstance(lesson, LessonPlan)
    assert lesson.concept == "Two Pointers for Palindrome"
    assert len(lesson.steps) == 3
    for step in lesson.steps:
        assert step.tool == "dynamic_lesson_step"
        assert "tool_calls" in step.params
        assert isinstance(step.params["tool_calls"], list)


def test_direct_lesson_fallback_on_bad_scene(mocker):
    """If build_scene fails for one scene, a minimal fallback scene is used."""
    call_count = {"n": 0}

    def mock_call(system, user):
        if call_count["n"] == 0:
            call_count["n"] += 1
            return json.dumps(MOCK_NARRATIVE)
        call_count["n"] += 1
        return "not valid json"  # triggers ValueError

    mocker.patch("agent.lesson_director._call_model", side_effect=mock_call)
    # Should not raise — falls back gracefully
    lesson = direct_lesson("test question")
    assert len(lesson.steps) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Phase D — endpoint tests
# ─────────────────────────────────────────────────────────────────────────────

def test_direct_lesson_endpoint_missing_question(client):
    res = client.post("/api/direct-lesson", json={})
    assert res.status_code == 400


def test_direct_lesson_endpoint_blank_question(client):
    res = client.post("/api/direct-lesson", json={"question": "   "})
    assert res.status_code == 400


def test_direct_lesson_endpoint_happy_path(client, mocker):
    """Endpoint returns a job_id immediately without waiting for the agent."""
    mocker.patch("app.submit_direct_lesson", return_value="test-job-id")
    res = client.post("/api/direct-lesson",
                      json={"question": "Explain two-pointer palindrome"})
    assert res.status_code == 202
    data = res.get_json()
    assert data["job_id"] == "test-job-id"


def test_direct_lesson_endpoint_returns_quickly(client, mocker):
    """Even if the underlying submit_direct_lesson is slow, the endpoint
    returns quickly because the agent runs in a background thread.
    We assert by mocking submit_direct_lesson to a fast no-op."""
    import time
    mocker.patch("app.submit_direct_lesson", return_value="fast-job")
    start = time.time()
    res = client.post("/api/direct-lesson", json={"question": "anything"})
    elapsed = time.time() - start
    assert res.status_code == 202
    assert elapsed < 1.0  # generous; real call is <50ms


# ─────────────────────────────────────────────────────────────────────────────
# Async submit_direct_lesson — Phase B
# ─────────────────────────────────────────────────────────────────────────────

def test_submit_direct_lesson_returns_immediately(mocker):
    """submit_direct_lesson must return a job_id without blocking on the agent."""
    from renderer.worker import submit_direct_lesson, get_job
    import time

    # Mock the agent to sleep 1 second; submit_direct_lesson should still
    # return in well under that.
    def slow_narrative(*args, **kwargs):
        time.sleep(1.0)
        from agent.lesson_director import NarrativePlan, ScenePlan
        return NarrativePlan(
            lesson_title="x", core_insight="y", narrative_arc="z",
            scenes=[ScenePlan(title="A", objective="o"),
                    ScenePlan(title="B", objective="o")],
        )

    mocker.patch("agent.lesson_director.narrative_plan", side_effect=slow_narrative)

    start = time.time()
    job_id = submit_direct_lesson("test")
    elapsed = time.time() - start

    assert elapsed < 0.2  # must return immediately
    job = get_job(job_id)
    assert job is not None
    assert job["status"] == "pending"
    assert job["stage"] == "planning_narrative"


def test_run_direct_lesson_stage_progression(mocker):
    """As the agent advances, stage transitions through planning → building → mirror."""
    from renderer.worker import _run_direct_lesson, _jobs
    from agent.lesson_director import NarrativePlan, ScenePlan, ToolCall

    fake_narrative = NarrativePlan(
        lesson_title="T", core_insight="I", narrative_arc="A",
        scenes=[ScenePlan(title="One", objective="o")],
    )
    mocker.patch("agent.lesson_director.narrative_plan", return_value=fake_narrative)
    mocker.patch("agent.lesson_director.build_scene", return_value=[
        ToolCall(tool="set_caption", args={"text": "test"}),
    ])

    # Stub submit_lesson — set inner job to done immediately
    def stub_submit(steps):
        from renderer.worker import _jobs
        inner_id = "inner-test-job"
        _jobs[inner_id] = {"status": "done", "url": "/media/lessons/x.mp4",
                           "error": None, "progress": 1.0, "stage": "done"}
        return inner_id
    mocker.patch("renderer.worker.submit_lesson", side_effect=stub_submit)

    outer_id = "outer-test"
    _jobs[outer_id] = {"status": "pending", "url": None, "error": None,
                       "progress": 0.0, "stage": "planning_narrative"}
    _run_direct_lesson(outer_id, "test question")

    assert _jobs[outer_id]["status"] == "done"
    assert _jobs[outer_id]["stage"] == "done"
    assert _jobs[outer_id]["url"] == "/media/lessons/x.mp4"


def test_run_direct_lesson_retry_uses_parallel_executor(mocker):
    """Bug 3 regression: when the first render fails and we retry, all scene
    rebuilds must happen in parallel (not serial). Detect by counting how
    many _safe_build_scene calls are in-flight simultaneously."""
    import threading as _th
    from renderer.worker import _run_direct_lesson, _jobs
    from agent.lesson_director import NarrativePlan, ScenePlan, ToolCall

    fake_narrative = NarrativePlan(
        lesson_title="T", core_insight="I", narrative_arc="A",
        scenes=[
            ScenePlan(title="A", objective="o1"),
            ScenePlan(title="B", objective="o2"),
            ScenePlan(title="C", objective="o3"),
        ],
    )
    mocker.patch("agent.lesson_director.narrative_plan", return_value=fake_narrative)

    # Track max concurrent in-flight builds via a semaphore counter
    in_flight = {"n": 0, "peak": 0}
    counter_lock = _th.Lock()

    def slow_build(*args, **kwargs):
        with counter_lock:
            in_flight["n"] += 1
            in_flight["peak"] = max(in_flight["peak"], in_flight["n"])
        try:
            import time as _ti
            _ti.sleep(0.15)  # long enough to see overlap if parallel
            return [ToolCall(tool="set_caption", args={"text": "x"})]
        finally:
            with counter_lock:
                in_flight["n"] -= 1

    mocker.patch("agent.lesson_director._build_scene_safe", side_effect=slow_build)
    # Worker imports it locally — patch there too
    mocker.patch("renderer.worker._safe_build_scene", side_effect=slow_build)

    # Inner lesson: first call returns an errored job, second succeeds
    inner_call_count = {"n": 0}
    def fake_submit(steps):
        inner_call_count["n"] += 1
        iid = f"inner-{inner_call_count['n']}"
        if inner_call_count["n"] == 1:
            _jobs[iid] = {"status": "error", "url": None,
                           "error": "first render bad", "progress": 0.0,
                           "stage": "error"}
        else:
            _jobs[iid] = {"status": "done", "url": "/media/x.mp4",
                           "error": None, "progress": 1.0, "stage": "done"}
        return iid
    mocker.patch("renderer.worker.submit_lesson", side_effect=fake_submit)

    outer_id = "test-retry-parallel"
    _jobs[outer_id] = {"status": "pending", "url": None, "error": None,
                       "progress": 0.0, "stage": "planning_narrative"}
    _run_direct_lesson(outer_id, "test", None)

    assert _jobs[outer_id]["status"] == "done"
    # Initial build = 3 parallel, retry build = 3 parallel. Peak must be ≥ 2
    # somewhere during execution. (Strict equality with 3 can flake on slow CI;
    # 2 is enough to prove non-serial behavior.)
    assert in_flight["peak"] >= 2, f"retry was serial (peak={in_flight['peak']})"


def test_run_direct_lesson_retry_records_stage_timing(mocker):
    """Bug 4 regression: a retry must add a 'building_scenes_retry' stage to
    the trace so the cost is visible in /api/trace/<id>."""
    from renderer.worker import _run_direct_lesson, _jobs
    from agent.trace import get_trace
    from agent.lesson_director import NarrativePlan, ScenePlan, ToolCall

    fake_narrative = NarrativePlan(
        lesson_title="T", core_insight="I", narrative_arc="A",
        scenes=[ScenePlan(title="One", objective="o")],
    )
    mocker.patch("agent.lesson_director.narrative_plan", return_value=fake_narrative)
    mocker.patch("agent.lesson_director._build_scene_safe",
                 return_value=[ToolCall(tool="set_caption", args={"text": "x"})])
    mocker.patch("renderer.worker._safe_build_scene",
                 return_value=[ToolCall(tool="set_caption", args={"text": "x"})])

    inner_call_count = {"n": 0}
    def fake_submit(steps):
        inner_call_count["n"] += 1
        iid = f"inner-stage-{inner_call_count['n']}"
        if inner_call_count["n"] == 1:
            _jobs[iid] = {"status": "error", "url": None,
                           "error": "boom", "progress": 0.0, "stage": "error"}
        else:
            _jobs[iid] = {"status": "done", "url": "/media/x.mp4",
                           "error": None, "progress": 1.0, "stage": "done"}
        return iid
    mocker.patch("renderer.worker.submit_lesson", side_effect=fake_submit)

    outer_id = "test-retry-stage"
    _jobs[outer_id] = {"status": "pending", "url": None, "error": None,
                       "progress": 0.0, "stage": "planning_narrative"}
    _run_direct_lesson(outer_id, "test", None)

    trace = get_trace(outer_id)
    assert trace is not None
    stage_names = [s.stage for s in trace.stages]
    assert "building_scenes_retry" in stage_names


def test_run_direct_lesson_agent_failure_records_error(mocker):
    """If the agent raises, the outer job ends in error with stage='error'."""
    from renderer.worker import _run_direct_lesson, _jobs
    mocker.patch("agent.lesson_director.narrative_plan",
                 side_effect=ValueError("LLM down"))

    outer_id = "outer-err-test"
    _jobs[outer_id] = {"status": "pending", "url": None, "error": None,
                       "progress": 0.0, "stage": "planning_narrative"}
    _run_direct_lesson(outer_id, "anything")

    assert _jobs[outer_id]["status"] == "error"
    assert _jobs[outer_id]["stage"] == "error"
    assert "LLM down" in _jobs[outer_id]["error"]


# ─────────────────────────────────────────────────────────────────────────────
# Phase B — ToolExecutor unit test (no Manim render — uses mock scene)
# ─────────────────────────────────────────────────────────────────────────────

class MockScene:
    """Minimal stand-in for a Manim Scene so ToolExecutor can be unit-tested."""
    def __init__(self):
        self.played = []

    def play(self, *anims, **kwargs):
        self.played.extend(anims)

    def wait(self, t=None):
        pass


def test_tool_executor_skips_unknown_tool():
    """ToolExecutor.execute must not raise on an unknown tool name."""
    # Import here to avoid Manim import at module level in non-render context
    from scenes.tool_executor import ToolExecutor
    mock_scene = MockScene()
    executor = ToolExecutor(mock_scene)
    # Should log a warning and return without raising
    executor.execute("completely_made_up_tool", {"foo": "bar"})


# ─────────────────────────────────────────────────────────────────────────────
# Integration — render a real DynamicScene
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_dynamic_scene_renders(tmp_path):
    """
    Render a minimal DynamicScene with a known tool call sequence.
    Asserts the output MP4 exists and is non-empty.
    """
    import json, subprocess, tempfile

    job_id = "test_dynamic_001"
    temp_dir = str(tmp_path)
    params = {
        "title": "Two Pointers",
        "tool_calls": [
            {"tool": "show_array",
             "args": {"values": ["r","a","c","e","c","a","r"],
                      "label": "s", "element_id": "arr"}},
            {"tool": "set_caption",
             "args": {"text": "L and R converge from opposite ends"}},
            {"tool": "add_pointer",
             "args": {"name": "L", "element_id": "arr", "index": 0, "color": "GREEN"}},
            {"tool": "add_pointer",
             "args": {"name": "R", "element_id": "arr", "index": 6, "color": "RED"}},
            {"tool": "highlight_cells",
             "args": {"element_id": "arr", "indices": [0, 6], "color": "YELLOW"}},
            {"tool": "emphasize", "args": {"element_id": "arr", "index": -1}},
            {"tool": "pause", "args": {"beats": 1}},
            {"tool": "show_result", "args": {"value": "True", "label": "palindrome"}},
        ],
    }

    params_path = tmp_path / f"{job_id}.json"
    params_path.write_text(json.dumps(params))

    backend_dir = os.path.dirname(os.path.dirname(__file__))
    media_dir = str(tmp_path / "media")
    os.makedirs(media_dir, exist_ok=True)

    env = {**os.environ,
           "MANIM_JOB_ID": job_id,
           "MANIM_TEMP_DIR": str(tmp_path)}

    result = subprocess.run(
        [sys.executable, "-m", "manim", "-ql",
         "--media_dir", media_dir,
         "--disable_caching",
         os.path.join(backend_dir, "scenes", "tool_executor.py"),
         "DynamicScene"],
        capture_output=True,
        text=True,
        cwd=backend_dir,
        env=env,
        timeout=120,
    )

    assert result.returncode == 0, (
        f"DynamicScene render failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    # Find the output MP4
    mp4_files = list(tmp_path.rglob("DynamicScene.mp4"))
    assert mp4_files, (
        f"No DynamicScene.mp4 found under {tmp_path}. "
        f"Manim output:\n{result.stderr[-1000:]}"
    )
    assert mp4_files[0].stat().st_size > 1000, "MP4 is suspiciously small"


def _run_dynamic_scene(tmp_path, job_id: str, params: dict):
    """Helper: write params JSON, invoke Manim, return subprocess result."""
    import json, subprocess
    params_path = tmp_path / f"{job_id}.json"
    params_path.write_text(json.dumps(params))
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    media_dir = str(tmp_path / "media")
    os.makedirs(media_dir, exist_ok=True)
    env = {**os.environ, "MANIM_JOB_ID": job_id, "MANIM_TEMP_DIR": str(tmp_path)}
    return subprocess.run(
        [sys.executable, "-m", "manim", "-ql",
         "--media_dir", media_dir, "--disable_caching",
         os.path.join(backend_dir, "scenes", "tool_executor.py"), "DynamicScene"],
        capture_output=True, text=True, cwd=backend_dir, env=env, timeout=120,
    )


@pytest.mark.integration
def test_dynamic_scene_hashmap_and_stack_render(tmp_path):
    """Regression test for bugs A+B: show_hashmap and show_stack must render
    without crashing (both had silent errors before the fix)."""
    params = {
        "title": "Hashmap + Stack smoke test",
        "tool_calls": [
            {"tool": "show_array",
             "args": {"values": ["3", "1", "4", "1", "5"], "label": "nums", "element_id": "arr"}},
            {"tool": "show_hashmap",
             "args": {"title": "seen", "anchor": "UR", "element_id": "map"}},
            {"tool": "show_stack",
             "args": {"title": "mono_stack", "anchor": "DR", "element_id": "stk"}},
            {"tool": "set_caption", "args": {"text": "Building frequency map and monotonic stack"}},
            {"tool": "set_hashmap_entry", "args": {"element_id": "map", "key": "3", "value": "1"}},
            {"tool": "push_stack", "args": {"element_id": "stk", "value": "3", "color": "YELLOW"}},
            {"tool": "push_stack", "args": {"element_id": "stk", "value": "1", "color": "GREEN"}},
            {"tool": "pop_stack", "args": {"element_id": "stk"}},
            {"tool": "emphasize", "args": {"element_id": "map"}},
            {"tool": "show_result", "args": {"value": "OK", "label": "test"}},
        ],
    }
    result = _run_dynamic_scene(tmp_path, "test_hashmap_stack_001", params)
    assert result.returncode == 0, (
        f"Hashmap+Stack render failed:\n{result.stdout}\n{result.stderr}"
    )
    mp4_files = list(tmp_path.rglob("DynamicScene.mp4"))
    assert mp4_files and mp4_files[0].stat().st_size > 1000
