"""Regression test: agent-emitted ``null`` params must not crash scenes.

When the Lesson Director (or a misbehaving model) emits JSON like
``{"n": null, "amount": null}`` for a scene's params file, the scene's
downstream ``int(p.get("n", 8))`` would previously raise
``TypeError: int() argument must be ... not 'NoneType'`` because
``dict.get(K, default)`` returns the explicit None instead of the
default.

The fix: every ``_load_params`` (across all scene files) strips
None-valued keys from the loaded JSON via ``_strip_dict_nulls``. This
test pins that contract — adding a new scene file with a stale
``_load_params`` will fail this test until the strip is added.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# Every scene file with a _load_params (or load_params) entry point.
_SCENE_MODULES = [
    "scenes.dsa_scene",
    "scenes.dsa_primitives",
    "scenes.calculus_scene",
    "scenes.algebra_scene",
    "scenes.trig_scene",
    "scenes.threed_scene",
    "scenes.arithmetic_scene",
    "scenes.array_scene",
]


def _get_loader(mod_name: str):
    """Return whichever of ``_load_params`` or ``load_params`` the module exports."""
    import importlib
    mod = importlib.import_module(mod_name)
    for attr in ("_load_params", "load_params"):
        fn = getattr(mod, attr, None)
        if callable(fn):
            return fn, mod
    pytest.fail(f"{mod_name} has neither _load_params nor load_params")


def _get_strip(mod):
    """Return the module's _strip_dict_nulls helper. Catches modules that
    skipped adding the strip."""
    fn = getattr(mod, "_strip_dict_nulls", None)
    assert callable(fn), (
        f"{mod.__name__} is missing the _strip_dict_nulls helper — its "
        f"_load_params will pass agent nulls through unchanged"
    )
    return fn


@pytest.mark.parametrize("mod_name", _SCENE_MODULES)
def test_scene_module_has_null_strip(mod_name):
    """Every scene module's _load_params must invoke _strip_dict_nulls."""
    loader, mod = _get_loader(mod_name)
    _get_strip(mod)
    # Also assert it's actually called from the loader, not just declared
    import inspect
    loader_src = inspect.getsource(loader)
    assert "_strip_dict_nulls" in loader_src, (
        f"{mod_name}._load_params doesn't call _strip_dict_nulls — "
        f"the helper exists but isn't wired in"
    )


@pytest.mark.parametrize("mod_name", _SCENE_MODULES)
def test_strip_drops_top_level_nulls(mod_name):
    _, mod = _get_loader(mod_name)
    strip = _get_strip(mod)
    out = strip({"a": 1, "b": None, "c": "x"})
    assert out == {"a": 1, "c": "x"}, (
        f"{mod_name}._strip_dict_nulls didn't drop the null entry: {out}"
    )


@pytest.mark.parametrize("mod_name", _SCENE_MODULES)
def test_strip_recurses_into_nested_dicts(mod_name):
    _, mod = _get_loader(mod_name)
    strip = _get_strip(mod)
    out = strip({"outer": {"keep": 1, "drop": None}})
    assert out == {"outer": {"keep": 1}}


@pytest.mark.parametrize("mod_name", _SCENE_MODULES)
def test_strip_preserves_list_shape(mod_name):
    """Lists may legitimately contain None entries (e.g. sparse coin arrays).
    The strip must NOT touch list contents."""
    _, mod = _get_loader(mod_name)
    strip = _get_strip(mod)
    out = strip({"coins": [1, None, 3]})
    assert out == {"coins": [1, None, 3]}


@pytest.mark.parametrize("mod_name", _SCENE_MODULES)
def test_strip_recurses_into_dicts_inside_lists(mod_name):
    """A dict embedded in a list still gets its None keys dropped."""
    _, mod = _get_loader(mod_name)
    strip = _get_strip(mod)
    out = strip({"items": [{"weight": 1, "value": None},
                            {"weight": 2, "value": 3}]})
    assert out == {"items": [{"weight": 1}, {"weight": 2, "value": 3}]}


@pytest.mark.parametrize("mod_name", _SCENE_MODULES)
def test_load_params_round_trip_strips_nulls(mod_name, tmp_path, monkeypatch):
    """End-to-end: write a JSON file with nulls, set the env vars, call
    the module's loader, verify nulls are gone."""
    job_id = "test-null-strip"
    monkeypatch.setenv("MANIM_JOB_ID", job_id)
    monkeypatch.setenv("MANIM_TEMP_DIR", str(tmp_path))
    (tmp_path / f"{job_id}.json").write_text(
        json.dumps({"n": None, "amount": 6, "caption": None}),
    )

    loader, _ = _get_loader(mod_name)
    p = loader()
    assert "n" not in p, f"{mod_name} didn't strip null n: {p}"
    assert "caption" not in p
    assert p.get("amount") == 6
    # Critically: int(p.get("n", 8)) should now work
    assert int(p.get("n", 8)) == 8


def test_dp_array_scene_handles_explicit_nulls():
    """The specific bug report regression: DPArrayScene.construct() must
    not crash when params contains {"n": null, "amount": null}."""
    # Just confirm the symbolic fix is in place — running the actual
    # scene needs Manim's renderer which is expensive. The
    # round-trip test above proves the data path works.
    from scenes.dsa_scene import _load_params, _strip_dict_nulls
    assert callable(_strip_dict_nulls)
    # And the DPArrayScene defends with `or` fallbacks as belt-and-suspenders
    import inspect
    from scenes.dsa_scene import DPArrayScene
    src = inspect.getsource(DPArrayScene.construct)
    assert 'p.get("n")' in src and "or 8" in src
    assert 'p.get("amount")' in src and "or 6" in src
