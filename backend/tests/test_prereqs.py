"""Tests for the topic prerequisite graph (Item #35)."""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app


_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
_PREREQS_PATH = os.path.join(_REPO_ROOT, "backend", "prereqs.json")
_PAGE = os.path.join(_REPO_ROOT, "frontend", "src", "pages", "PrereqGraphPage.tsx")


@pytest.fixture
def client():
    return create_app(testing=True).test_client()


# ── Data integrity ─────────────────────────────────────────────────────────


def test_prereqs_file_exists_and_is_valid_json():
    assert os.path.exists(_PREREQS_PATH)
    with open(_PREREQS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict)


def test_prereqs_has_required_domains():
    with open(_PREREQS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    for d in ["calculus", "dsa"]:
        assert d in data, f"missing domain: {d}"


def test_prereqs_have_no_dangling_references():
    """Every prereq must itself appear as a node in the SAME domain."""
    with open(_PREREQS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    for domain, scenes in data.items():
        if domain.startswith("_"):
            continue
        keys = set(scenes.keys())
        for scene, prereqs in scenes.items():
            for p in prereqs:
                assert p in keys, (
                    f"{domain}.{scene} has dangling prereq '{p}' (not a node)"
                )


def test_prereqs_have_no_cycles():
    """Graph must be a DAG — no cycles."""
    with open(_PREREQS_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    for domain, scenes in data.items():
        if domain.startswith("_"):
            continue

        WHITE, GRAY, BLACK = 0, 1, 2
        state = {k: WHITE for k in scenes}

        def visit(node: str) -> None:
            if state[node] == GRAY:
                pytest.fail(f"cycle detected in {domain} involving {node}")
            if state[node] == BLACK:
                return
            state[node] = GRAY
            for p in scenes.get(node, []):
                visit(p)
            state[node] = BLACK

        for node in scenes:
            visit(node)


# ── /api/prereqs endpoint ──────────────────────────────────────────────────


def test_prereqs_endpoint_returns_domains(client):
    res = client.get("/api/prereqs")
    assert res.status_code == 200
    body = res.get_json()
    assert "domains" in body
    assert "calculus" in body["domains"]
    assert "dsa" in body["domains"]


def test_prereqs_endpoint_excludes_meta_block(client):
    """The _meta key in prereqs.json must NOT leak into the API response."""
    res = client.get("/api/prereqs")
    body = res.get_json()
    assert "_meta" not in body["domains"]
    for domain_data in body["domains"].values():
        assert "_meta" not in domain_data


# ── Frontend page wiring ───────────────────────────────────────────────────


def test_prereq_page_exists_and_is_wired_into_app():
    assert os.path.exists(_PAGE)
    app = os.path.join(_REPO_ROOT, "frontend", "src", "App.tsx")
    with open(app, encoding="utf-8") as fh:
        text = fh.read()
    assert "PrereqGraphPage" in text
    assert "prereqs" in text  # route + sidebar key


def test_prereq_page_fetches_from_correct_endpoint():
    with open(_PAGE, encoding="utf-8") as fh:
        text = fh.read()
    assert "/api/prereqs" in text
