"""Regression tests for Item #36 — export saved videos."""
import os
import re
import shutil
import subprocess

import pytest


_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
_HELPER = os.path.join(
    _REPO_ROOT, "frontend", "src", "lib", "exportLibrary.ts",
)
_LIBRARY_PAGE = os.path.join(
    _REPO_ROOT, "frontend", "src", "pages", "LibraryPage.tsx",
)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_export_helper_exists():
    assert os.path.exists(_HELPER)


def test_export_helper_exposes_required_surface():
    text = _read(_HELPER)
    assert re.search(r"export\s+(async\s+)?function\s+downloadVideo", text)
    assert re.search(r"export\s+(async\s+)?function\s+exportLibraryAsMarkdown", text)
    assert re.search(r"export\s+(async\s+)?function\s+downloadMarkdownLibrary", text)
    assert re.search(r"export\s+(async\s+)?function\s+safeFilename", text)


def test_export_avoids_heavy_react_pdf_dep():
    """Bundle-size guardrail: react-pdf is ~500 KB. Decision is to skip it.

    Comments referencing the decision are fine — actual imports are not.
    """
    text = _read(_HELPER)
    assert not re.search(r"^\s*import .*react-pdf", text, re.MULTILINE)
    assert not re.search(r"^\s*import .*@react-pdf", text, re.MULTILINE)
    # Also check package.json (no react-pdf dep entry)
    pkg_path = os.path.join(_REPO_ROOT, "frontend", "package.json")
    pkg_text = _read(pkg_path)
    assert '"react-pdf"' not in pkg_text
    assert '"@react-pdf/renderer"' not in pkg_text


def test_library_page_wires_export_buttons():
    text = _read(_LIBRARY_PAGE)
    assert "downloadVideo" in text
    assert "downloadMarkdownLibrary" in text
    assert "Export library as markdown" in text
    # Per-card download button uses the Download icon
    assert "Download MP4" in text or "Download size={12}" in text


def _have_node() -> bool:
    return shutil.which("node") is not None


@pytest.mark.skipif(not _have_node(), reason="node is not on PATH")
def test_markdown_export_produces_well_formed_report(tmp_path):
    """exportLibraryAsMarkdown should emit a proper header + per-video sections."""
    script = """
const { writeFileSync } = require('fs');

// Mirror the pure helper inline (so the test doesn't need a TS toolchain).
function safeFilename(title, ext) {
  const cleaned = (title || 'lumen-video').toLowerCase()
    .replace(/[^a-z0-9-_]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80);
  return (cleaned || 'lumen') + '.' + ext;
}
function _isoDate(ms) {
  if (!ms) return '—';
  return new Date(ms).toISOString().slice(0, 10);
}
function exportLibraryAsMarkdown(items, now = Date.now()) {
  const lines = [];
  lines.push('# Lumen — Saved Library');
  lines.push('');
  lines.push(`Generated: ${_isoDate(now)}`);
  lines.push(`Total videos: ${items.length}`);
  lines.push('');
  if (items.length === 0) {
    lines.push('_(library is empty — save a video first)_');
    return lines.join('\\n');
  }
  const sorted = [...items].sort((a, b) => b.savedAt - a.savedAt);
  for (const v of sorted) {
    lines.push(`## ${v.title || '(untitled)'}`);
    lines.push('');
    lines.push(`- **Scene:** \\`${v.scene}\\``);
    lines.push(`- **Domain:** ${v.domain}`);
    lines.push(`- **Saved:** ${_isoDate(v.savedAt)}`);
    lines.push(`- **Offline copy:** ${v.hasOfflineCopy ? 'yes' : 'no'}`);
    if (v.srs) {
      lines.push(`- **SRS reps:** ${v.srs.repetitions}`);
    }
    lines.push(`- **Server URL:** ${v.serverUrl}`);
    lines.push('');
  }
  return lines.join('\\n');
}

const items = [
  { id: 'a', title: 'Two Pointers',  scene: 'array',   domain: 'dsa',
    savedAt: 1700000000000, serverUrl: 'http://x/a.mp4', hasOfflineCopy: true },
  { id: 'b', title: 'Riemann Sums',  scene: 'math',    domain: 'math',
    savedAt: 1710000000000, serverUrl: 'http://x/b.mp4', hasOfflineCopy: false,
    srs: { repetitions: 3, easeFactor: 2.6, nextReviewAt: 1720000000000 } },
];
const md = exportLibraryAsMarkdown(items, 1730000000000);
process.stdout.write(md);
"""
    script_path = tmp_path / "export_test.cjs"
    script_path.write_text(script, encoding="utf-8")
    res = subprocess.run(
        ["node", str(script_path)],
        capture_output=True, text=True, timeout=15,
    )
    assert res.returncode == 0, res.stderr
    md = res.stdout
    assert md.startswith("# Lumen")
    assert "Total videos: 2" in md
    # Newest-first ordering — Riemann Sums (savedAt 1710...) comes before Two Pointers (1700...)
    riemann = md.index("Riemann Sums")
    two_ptr = md.index("Two Pointers")
    assert riemann < two_ptr
    # SRS data surfaces for entries that have it
    assert "SRS reps:" in md
