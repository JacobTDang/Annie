"""Tests for adaptive difficulty hints (Item #34)."""
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.lesson_director import narrative_plan, _difficulty_hint
from app import create_app, _parse_difficulty_hint


MOCK_NARRATIVE = {
    "lesson_title": "Two Pointers for Palindrome",
    "core_insight": "Opposite-end pointers replace the inner loop.",
    "narrative_arc": "hook → insight → resolution",
    "scenes": [
        {"title": "Setup", "objective": "ok", "is_aha_moment": False},
        {"title": "Insight", "objective": "ok", "is_aha_moment": True},
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# _difficulty_hint pure helper
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("input_val", [None, "normal", "", "garbage"])
def test_difficulty_hint_returns_empty_for_default_or_unknown(input_val):
    assert _difficulty_hint(input_val) == ""


def test_difficulty_hint_extend_includes_struggled_signal():
    out = _difficulty_hint("extend").lower()
    assert "struggle" in out
    assert "extend" in out or "worked example" in out


def test_difficulty_hint_skip_includes_master_signal():
    out = _difficulty_hint("skip").lower()
    assert "master" in out
    assert "recap" in out


# ─────────────────────────────────────────────────────────────────────────────
# narrative_plan integration
# ─────────────────────────────────────────────────────────────────────────────


def test_narrative_plan_extend_hint_appears_in_system_prompt(mocker):
    captured = {}

    def fake_call(system, user, *args, **kwargs):
        captured["system"] = system
        return json.dumps(MOCK_NARRATIVE)

    mocker.patch("agent.lesson_director._call_model", side_effect=fake_call)
    narrative_plan("any q", difficulty_hint="extend")
    assert "struggle" in captured["system"].lower()


def test_narrative_plan_skip_hint_appears_in_system_prompt(mocker):
    captured = {}

    def fake_call(system, user, *args, **kwargs):
        captured["system"] = system
        return json.dumps(MOCK_NARRATIVE)

    mocker.patch("agent.lesson_director._call_model", side_effect=fake_call)
    narrative_plan("any q", difficulty_hint="skip")
    assert "master" in captured["system"].lower()
    assert "recap" in captured["system"].lower()


def test_narrative_plan_normal_hint_does_not_inject_anything(mocker):
    captured = {}

    def fake_call(system, user, *args, **kwargs):
        captured["system"] = system
        return json.dumps(MOCK_NARRATIVE)

    mocker.patch("agent.lesson_director._call_model", side_effect=fake_call)
    narrative_plan("any q", difficulty_hint="normal")
    # Neither the extend nor the skip phrasing leaks in
    s = captured["system"].lower()
    assert "struggle" not in s
    assert "fast recap" not in s


# ─────────────────────────────────────────────────────────────────────────────
# _parse_difficulty_hint route helper
# ─────────────────────────────────────────────────────────────────────────────


def test_parse_difficulty_hint_accepts_known_values():
    assert _parse_difficulty_hint({"difficulty_hint": "extend"}) == "extend"
    assert _parse_difficulty_hint({"difficulty_hint": "skip"}) == "skip"
    assert _parse_difficulty_hint({"difficulty_hint": "normal"}) == "normal"


def test_parse_difficulty_hint_rejects_garbage_silently():
    """Unknown values normalize to None (treated as default)."""
    assert _parse_difficulty_hint({"difficulty_hint": "wild"}) is None
    assert _parse_difficulty_hint({"difficulty_hint": 42}) is None
    assert _parse_difficulty_hint({}) is None


# ─────────────────────────────────────────────────────────────────────────────
# Route integration — difficulty_hint reaches the worker
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    return create_app(testing=True).test_client()


def test_direct_lesson_forwards_difficulty_hint(client, mocker):
    spy = mocker.patch("app.submit_direct_lesson", return_value="job-x")
    client.post("/api/direct-lesson",
                 json={"question": "x", "difficulty_hint": "extend"})
    assert spy.call_count == 1
    call = spy.call_args
    assert call.kwargs.get("difficulty_hint") == "extend"


def test_direct_lesson_ignores_unknown_difficulty_hint(client, mocker):
    spy = mocker.patch("app.submit_direct_lesson", return_value="job-x")
    client.post("/api/direct-lesson",
                 json={"question": "x", "difficulty_hint": "wild"})
    assert spy.call_args.kwargs.get("difficulty_hint") is None


# ─────────────────────────────────────────────────────────────────────────────
# Frontend module structural surface
# ─────────────────────────────────────────────────────────────────────────────


def test_frontend_quiz_history_module_exposes_required_api():
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "frontend", "src", "lib", "quizHistory.ts",
    )
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for sym in ["recordAttempt", "accuracyForTopic", "difficultyHintFor",
                "classifyAccuracy", "resetQuizHistory", "DifficultyHint"]:
        assert sym in text, f"quizHistory.ts must export {sym}"
    # Threshold constants — flag if they ever silently change
    assert "0.5" in text   # extend below 50%
    assert "0.9" in text   # skip at/above 90%
