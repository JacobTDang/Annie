"""Structural tests for the frontend collab page (Item #30)."""
import json
import os
import re


_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
_LIB = os.path.join(_REPO_ROOT, "frontend", "src", "lib", "collab.ts")
_PAGE = os.path.join(_REPO_ROOT, "frontend", "src", "pages", "CollabPage.tsx")
_APP = os.path.join(_REPO_ROOT, "frontend", "src", "App.tsx")
_PKG = os.path.join(_REPO_ROOT, "frontend", "package.json")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_yjs_deps_declared_in_package_json():
    """yjs + y-websocket + y-monaco must be installed dependencies (not
    peers) so the bundle ships with them."""
    pkg = json.loads(_read(_PKG))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    for name in ["yjs", "y-websocket", "y-monaco"]:
        assert name in deps, f"{name} missing from frontend/package.json"


def test_collab_lib_exports_required_surface():
    text = _read(_LIB)
    assert re.search(r"export\s+function\s+openCollabSession", text)
    assert re.search(r"export\s+function\s+isValidRoomId", text)
    assert re.search(r"export\s+interface\s+CollabSession", text)


def test_collab_lib_picks_correct_ws_scheme():
    """http→ws / https→wss mapping must exist so production deploys upgrade
    to the secure variant."""
    text = _read(_LIB)
    assert '"wss://"' in text
    assert '"ws://"' in text


def test_collab_lib_validates_room_id_consistently_with_backend():
    """Frontend regex must mirror the backend's _validate_room_id rule
    (alphanumeric + hyphen + underscore, length <= 64)."""
    text = _read(_LIB)
    assert "/^[A-Za-z0-9_-]+$/" in text
    assert "64" in text


def test_collab_page_lazy_imports_y_monaco():
    """y-monaco only matters once a Monaco editor + a Y.Doc both exist.
    Lazy importing keeps the binding lib out of the eager bundle."""
    text = _read(_PAGE)
    assert "await import" in text
    assert "y-monaco" in text


def test_collab_page_wires_status_and_peer_count():
    text = _read(_PAGE)
    # Connection status feedback + awareness peer count
    assert "status" in text and "connected" in text
    assert "awareness" in text


def test_collab_page_reads_room_id_from_url_hash():
    text = _read(_PAGE)
    assert "#room=" in text or "room=" in text
    # Hash is canonical so refresh/share both work
    assert "window.location.hash" in text


def test_collab_route_wired_into_app():
    text = _read(_APP)
    assert "CollabPage" in text
    assert 'route === "collab"' in text
    # Sidebar entry
    assert '"collab"' in text or '"Collab"' in text


def test_collab_page_is_lazy_imported_in_app():
    """The Yjs + y-monaco chunks are heavy; CollabPage must be lazy() so
    pages that don't need them don't pull them into the main bundle."""
    text = _read(_APP)
    assert "lazy(() => import('./pages/CollabPage'" in text
