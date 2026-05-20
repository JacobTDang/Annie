"""Structural regression tests for Item #27 (solution diff against reference)."""
import os
import re


_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
_HELPER = os.path.join(
    _REPO_ROOT, "frontend", "src", "lib", "compareSolutions.ts",
)
_PANEL = os.path.join(_REPO_ROOT, "frontend", "src", "CodeEditorPanel.tsx")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_compare_solutions_helper_exists():
    assert os.path.exists(_HELPER), f"{_HELPER} missing"


def test_compare_solutions_exports_required_functions():
    text = _read(_HELPER)
    # Pure helpers that the panel + future tests depend on
    assert re.search(r"export\s+function\s+normalizeOutput", text)
    assert re.search(r"export\s+function\s+outputsMatch", text)
    assert re.search(r"export\s+async\s+function\s+compareSolutions", text)
    assert re.search(r"export\s+interface\s+CompareResult", text)


def test_normalize_strips_trailing_whitespace_and_blank_lines():
    """A quick semantic check on the regexes used in normalizeOutput."""
    text = _read(_HELPER)
    # The function trims trailing whitespace per line and trailing newlines
    assert ".replace(/\\s+$/g, \"\")" in text or ".replace(/\\s+$/g, '')" in text
    assert ".replace(/\\n+$/, \"\")" in text or ".replace(/\\n+$/, '')" in text


def test_panel_accepts_reference_code_prop():
    text = _read(_PANEL)
    # Prop is plumbed in
    assert "referenceCode" in text, (
        "CodeEditorPanel must accept a referenceCode prop (Item #27)"
    )
    # Helper is imported
    assert "compareSolutions" in text
    # Panel renders the comparison badge
    assert "Matches reference" in text
    assert "Differs from reference" in text
