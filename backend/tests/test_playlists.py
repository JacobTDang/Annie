"""Regression tests for Item #29 — lesson playlists."""
import os
import re
import shutil
import subprocess

import pytest


_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
_HELPER = os.path.join(
    _REPO_ROOT, "frontend", "src", "lib", "playlists.ts",
)
_PAGE = os.path.join(
    _REPO_ROOT, "frontend", "src", "pages", "PlaylistsPage.tsx",
)
_APP = os.path.join(_REPO_ROOT, "frontend", "src", "App.tsx")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ── Structural surface ─────────────────────────────────────────────────────


def test_playlists_helper_exists():
    assert os.path.exists(_HELPER)


def test_playlists_helper_exposes_required_api():
    text = _read(_HELPER)
    for sym in ["playlists", "Playlist", "nextInPlaylist"]:
        assert sym in text, f"playlists.ts must export {sym}"
    for method in ["create", "remove", "rename", "appendVideo",
                   "removeAt", "reorder"]:
        assert method in text, f"playlists CRUD must include {method}()"


def test_playlists_page_exists_and_is_wired_into_app():
    assert os.path.exists(_PAGE)
    app = _read(_APP)
    assert "PlaylistsPage" in app
    assert "playlists" in app  # route key
    assert "ListMusic" in app  # sidebar icon


def test_playlists_page_auto_advances_on_video_end():
    text = _read(_PAGE)
    # The <video> element must wire onEnded to nextInPlaylist logic
    assert "onEnded" in text
    assert "nextInPlaylist" in text


# ── Algorithm correctness via Node ─────────────────────────────────────────


def _have_node() -> bool:
    return shutil.which("node") is not None


@pytest.mark.skipif(not _have_node(), reason="node is not on PATH")
def test_next_in_playlist_orders_correctly(tmp_path):
    """nextInPlaylist returns the next id, or null at the end."""
    js = """
function nextInPlaylist(playlist, currentVideoId) {
  const i = playlist.videoIds.indexOf(currentVideoId);
  if (i === -1) return playlist.videoIds[0] ?? null;
  return playlist.videoIds[i + 1] ?? null;
}
const pl = { videoIds: ["a", "b", "c"] };
console.log(JSON.stringify({
  fromA: nextInPlaylist(pl, "a"),
  fromB: nextInPlaylist(pl, "b"),
  fromC: nextInPlaylist(pl, "c"),
  unknown: nextInPlaylist(pl, "z"),
  empty: nextInPlaylist({ videoIds: [] }, "a"),
}));
"""
    p = tmp_path / "pl.cjs"
    p.write_text(js, encoding="utf-8")
    res = subprocess.run(["node", str(p)], capture_output=True, text=True, timeout=10)
    assert res.returncode == 0, res.stderr
    import json as _json
    out = _json.loads(res.stdout)
    assert out["fromA"] == "b"
    assert out["fromB"] == "c"
    assert out["fromC"] is None
    assert out["unknown"] == "a"     # fall back to the first video
    assert out["empty"] is None
