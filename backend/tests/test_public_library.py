"""Tests for the public-share discovery endpoint (Item #31)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Point _SHARES_PATH at a tmpdir so tests don't pollute backend/data/."""
    import app as app_mod
    monkeypatch.setattr(app_mod, "_SHARES_PATH", str(tmp_path / "shares.json"))
    return create_app(testing=True).test_client()


def _share(client, parsed: dict, is_public: bool = False) -> str:
    res = client.post("/api/share",
                      json={"parsed": parsed, "is_public": is_public})
    assert res.status_code == 200, res.get_data(as_text=True)
    body = res.get_json()
    return body["shareCode"]


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/share — is_public flag
# ─────────────────────────────────────────────────────────────────────────────


def test_share_default_is_private(client):
    res = client.post("/api/share",
                      json={"parsed": {"scene": "x", "title": "T"}})
    assert res.status_code == 200
    assert res.get_json()["is_public"] is False


def test_share_can_be_marked_public(client):
    res = client.post("/api/share",
                      json={"parsed": {"scene": "x", "title": "T"},
                             "is_public": True})
    assert res.status_code == 200
    assert res.get_json()["is_public"] is True


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/share/<code> — must still unwrap the new shape correctly
# ─────────────────────────────────────────────────────────────────────────────


def test_existing_share_get_unwraps_parsed_payload(client):
    code = _share(client, {"scene": "tangent_line", "title": "Derivatives"})
    res = client.get(f"/api/share/{code}")
    assert res.status_code == 200
    assert res.get_json()["parsed"]["scene"] == "tangent_line"


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/public/recent
# ─────────────────────────────────────────────────────────────────────────────


def test_public_recent_returns_only_public_shares(client):
    pub_code = _share(client, {"scene": "limit", "title": "Limits 101",
                                  "domain": "math"}, is_public=True)
    priv_code = _share(client, {"scene": "limit", "title": "Private"},
                       is_public=False)
    res = client.get("/api/public/recent")
    assert res.status_code == 200
    codes = [s["code"] for s in res.get_json()["shares"]]
    assert pub_code in codes
    assert priv_code not in codes


def test_public_recent_empty_when_no_public_shares(client):
    _share(client, {"scene": "x", "title": "P1"}, is_public=False)
    _share(client, {"scene": "x", "title": "P2"}, is_public=False)
    res = client.get("/api/public/recent")
    assert res.status_code == 200
    assert res.get_json()["shares"] == []


def test_public_recent_orders_newest_first(client):
    import app as app_mod
    # Mint two public shares with controlled created_at timestamps
    with app_mod._SHARES_LOCK:
        shares = app_mod._load_shares()
        shares["AAAAAAAA"] = {"parsed": {"scene": "a", "title": "Old"},
                                "is_public": True, "created_at": 100}
        shares["BBBBBBBB"] = {"parsed": {"scene": "b", "title": "New"},
                                "is_public": True, "created_at": 999}
        app_mod._save_shares(shares)

    res = client.get("/api/public/recent")
    items = res.get_json()["shares"]
    assert [s["title"] for s in items] == ["New", "Old"]


def test_public_recent_respects_limit(client):
    for i in range(5):
        _share(client, {"scene": "x", "title": f"T{i}"}, is_public=True)
    res = client.get("/api/public/recent?limit=2")
    items = res.get_json()["shares"]
    assert len(items) == 2


def test_public_recent_clamps_invalid_limit(client):
    _share(client, {"scene": "x", "title": "T"}, is_public=True)
    res = client.get("/api/public/recent?limit=not-a-number")
    assert res.status_code == 200  # falls back to default


def test_legacy_bare_dict_share_is_not_exposed_as_public(client):
    """Pre-Item-#31 shares were bare parsed dicts (no is_public). They must
    NOT appear on the public endpoint by accident."""
    import app as app_mod
    with app_mod._SHARES_LOCK:
        shares = app_mod._load_shares()
        # Legacy shape — the dict IS the parsed payload, no is_public wrapper
        shares["LEGACY00"] = {"scene": "x", "title": "Legacy"}
        app_mod._save_shares(shares)
    res = client.get("/api/public/recent")
    assert res.status_code == 200
    codes = [s["code"] for s in res.get_json()["shares"]]
    assert "LEGACY00" not in codes


# ─────────────────────────────────────────────────────────────────────────────
# Frontend page structural surface
# ─────────────────────────────────────────────────────────────────────────────


def test_public_library_page_exists_and_is_wired():
    repo = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    page = os.path.join(repo, "frontend", "src", "pages", "PublicLibraryPage.tsx")
    assert os.path.exists(page)
    with open(page, encoding="utf-8") as fh:
        text = fh.read()
    assert "/api/public/recent" in text
    # App.tsx must wire the route + sidebar entry
    app = os.path.join(repo, "frontend", "src", "App.tsx")
    with open(app, encoding="utf-8") as fh:
        app_text = fh.read()
    assert "PublicLibraryPage" in app_text
    assert 'route === "public"' in app_text or "route === 'public'" in app_text
