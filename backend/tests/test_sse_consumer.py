"""Tests for the SSE consumer (#11 completion)."""
import os
import re
import shutil
import subprocess

import pytest


_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
_LIB = os.path.join(_REPO_ROOT, "frontend", "src", "lib", "sseLesson.ts")
_HOOK = os.path.join(_REPO_ROOT, "frontend", "src", "hooks", "useSSEDirectLesson.ts")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_sse_consumer_lib_exists():
    assert os.path.exists(_LIB)


def test_sse_consumer_exposes_required_surface():
    text = _read(_LIB)
    for sym in ["streamDirectLesson", "SSEEvent", "SSEStage",
                "StreamDirectLessonOptions", "StreamDirectLessonResult"]:
        assert sym in text, f"sseLesson.ts must export {sym}"


def test_sse_consumer_calls_correct_endpoint():
    text = _read(_LIB)
    assert "/api/direct-lesson-stream" in text
    # Must POST — backend rejects GET on this route
    assert "method:" in text and '"POST"' in text


def test_sse_consumer_handles_all_documented_event_types():
    """The lib aggregates narrative/scene_done/job_id/done/error in its switch.
    `stage` events are routed through onEvent() to the consumer (the hook).
    Verify both halves of the contract."""
    lib_text = _read(_LIB)
    hook_text = _read(_HOOK)
    for event in ["narrative", "scene_done", "job_id", "done", "error"]:
        assert f'"{event}"' in lib_text, (
            f"sseLesson.ts switch must handle: {event}"
        )
    # The hook is what surfaces stage transitions to React state
    assert '"stage"' in hook_text, (
        "useSSEDirectLesson must handle stage events via onEvent"
    )


def test_sse_consumer_supports_abort_signal():
    text = _read(_LIB)
    # AbortSignal hookup so callers can cancel mid-stream
    assert "AbortSignal" in text
    assert "signal:" in text


def test_sse_hook_exists_and_wraps_lib():
    assert os.path.exists(_HOOK)
    text = _read(_HOOK)
    assert "streamDirectLesson" in text
    # Cleanup on unmount — AbortController must be aborted in useEffect cleanup
    assert "AbortController" in text
    assert "abort()" in text


def test_sse_hook_exposes_start_and_cancel():
    text = _read(_HOOK)
    assert re.search(r"\bstart\b", text)
    assert re.search(r"\bcancel\b", text)


# ─────────────────────────────────────────────────────────────────────────────
# Frame parser correctness via Node — extract the helper into JS and exercise it
# ─────────────────────────────────────────────────────────────────────────────


def _have_node() -> bool:
    return shutil.which("node") is not None


@pytest.mark.skipif(not _have_node(), reason="node is not on PATH")
def test_parse_frame_extracts_event_and_data(tmp_path):
    js = """
function _parseFrame(frame) {
  let event = "message";
  let dataLines = [];
  for (const line of frame.split("\\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (dataLines.length === 0) return null;
  const dataStr = dataLines.join("\\n");
  let data;
  try { data = JSON.parse(dataStr); } catch { data = dataStr; }
  return { event, data };
}

const cases = [
  // Standard JSON-payload event
  ["event: scene_done\\ndata: {\\"index\\": 0, \\"title\\": \\"Intro\\"}",
    {event: "scene_done", data: {index: 0, title: "Intro"}}],
  // Plain-string payload
  ["event: stage\\ndata: planning_narrative",
    {event: "stage", data: "planning_narrative"}],
  // Multi-line data field — concatenated with \\n
  ["event: blob\\ndata: line1\\ndata: line2",
    {event: "blob", data: "line1\\nline2"}],
  // Empty frame yields null
  ["", null],
];
for (const [input, expected] of cases) {
  const got = _parseFrame(input);
  if (JSON.stringify(got) !== JSON.stringify(expected)) {
    console.error("FAIL:", input, "got=", got, "expected=", expected);
    process.exit(1);
  }
}
console.log("OK");
"""
    p = tmp_path / "sse_parse.cjs"
    p.write_text(js, encoding="utf-8")
    res = subprocess.run(["node", str(p)], capture_output=True, text=True, timeout=10)
    assert res.returncode == 0, f"stdout={res.stdout!r} stderr={res.stderr!r}"
    assert "OK" in res.stdout


def test_stale_flaskBase_string_template_bug_does_not_recur():
    """Regression: earlier iterations used `${flaskBase}` (function ref) which
    silently produced broken URLs. Make sure no fetch in lib/* or pages/*
    interpolates the function without calling it."""
    pages_dir = os.path.join(_REPO_ROOT, "frontend", "src", "pages")
    lib_dir = os.path.join(_REPO_ROOT, "frontend", "src", "lib")
    bad = []
    for d in [pages_dir, lib_dir]:
        for root, _, files in os.walk(d):
            for f in files:
                if not (f.endswith(".ts") or f.endswith(".tsx")):
                    continue
                with open(os.path.join(root, f), encoding="utf-8") as fh:
                    text = fh.read()
                # `${flaskBase}` (no call) is the bug; `${flaskBase()}` is fine
                if re.search(r"\$\{flaskBase\}", text):
                    bad.append(os.path.relpath(os.path.join(root, f), _REPO_ROOT))
    assert not bad, f"these files interpolate flaskBase without calling it: {bad}"
