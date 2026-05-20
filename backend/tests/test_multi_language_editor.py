"""Tests for Item #26 — multi-language code editor."""
import os
import re


_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
_RUN_JS = os.path.join(_REPO_ROOT, "frontend", "src", "lib", "runJS.ts")
_PANEL = os.path.join(_REPO_ROOT, "frontend", "src", "CodeEditorPanel.tsx")
_PKG = os.path.join(_REPO_ROOT, "frontend", "package.json")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ── runJS helper ───────────────────────────────────────────────────────────


def test_run_js_helper_exists():
    assert os.path.exists(_RUN_JS)


def test_run_js_helper_exposes_required_surface():
    text = _read(_RUN_JS)
    assert re.search(r"export\s+function\s+runJS", text)
    assert "LANGUAGES" in text
    assert "SupportedLanguage" in text


def test_run_js_uses_worker_for_sandboxing():
    """Sandbox guarantee: user code must run in a Worker, not in the page."""
    text = _read(_RUN_JS)
    assert "new Worker" in text
    assert "Blob" in text  # constructed from blob URL
    assert "terminate()" in text  # hard-kill on timeout


def test_run_js_enforces_a_timeout():
    text = _read(_RUN_JS)
    assert "setTimeout" in text
    # Hard-coded default must be a sane non-zero ms value (we use 5_000)
    assert "5_000" in text or "5000" in text


def test_languages_catalog_marks_cpp_as_unavailable():
    """C++ requires wasm-clang which isn't bundled — must be flagged."""
    text = _read(_RUN_JS)
    # Find the cpp entry and check it carries available: false
    m = re.search(r"id:\s*\"cpp\"[\s\S]*?available:\s*(true|false)", text)
    assert m, "cpp entry not found in LANGUAGES catalog"
    assert m.group(1) == "false"


def test_languages_includes_python_and_javascript():
    text = _read(_RUN_JS)
    assert re.search(r"id:\s*\"python\"", text)
    assert re.search(r"id:\s*\"javascript\"", text)


# ── Panel wiring ───────────────────────────────────────────────────────────


def test_panel_imports_run_js_and_languages():
    text = _read(_PANEL)
    assert "runJS" in text
    assert "LANGUAGES" in text
    assert "SupportedLanguage" in text


def test_panel_renders_language_dropdown():
    text = _read(_PANEL)
    # The <select> element must exist and iterate LANGUAGES
    assert "<select" in text
    assert "LANGUAGES.map" in text
    # Visual cue for unavailable languages
    assert "(soon)" in text or "Coming soon" in text


def test_panel_branches_on_language():
    """handleRun must dispatch based on language, not always Python."""
    text = _read(_PANEL)
    assert 'language === "python"' in text
    assert 'language === "javascript"' in text


# ── Bundle-size guardrail ──────────────────────────────────────────────────


def test_wasm_clang_not_added_to_dependencies():
    """Confirms we deliberately avoided pulling in a 30 MB wasm-clang dep."""
    pkg = _read(_PKG)
    assert "wasm-clang" not in pkg
    assert "@wasmer" not in pkg
