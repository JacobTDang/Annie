"""Tests for the OpenAPI 3.1 schema endpoint (Item #21)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from openapi_spec import build_openapi_spec


@pytest.fixture
def client():
    app = create_app(testing=True)
    return app.test_client()


def test_openapi_endpoint_returns_200(client):
    res = client.get("/openapi.json")
    assert res.status_code == 200
    assert res.headers["Content-Type"].startswith("application/json")


def test_openapi_endpoint_is_valid_openapi_31_doc(client):
    res = client.get("/openapi.json")
    spec = res.get_json()
    assert spec["openapi"].startswith("3.1")
    assert "info" in spec and spec["info"]["title"]
    assert "paths" in spec and len(spec["paths"]) > 0


def test_openapi_documents_critical_endpoints(client):
    res = client.get("/openapi.json")
    spec = res.get_json()
    expected = [
        # Core
        "/health",
        "/ask",
        "/render",
        "/status/{job_id}",
        # Agent path
        "/api/direct-lesson",
        "/api/direct-lesson-stream",
        # Sharing
        "/api/share",
        "/api/share/{code}",
        "/api/share/mine",
        "/api/public/recent",
        # Pinning + library
        "/api/pin",
        "/api/pin/{job_id}",
        # Parser surface (frontend's primary path)
        "/api/parse-problem-v2",
        "/api/parse-followup",
        "/api/parse-leetcode",
        "/api/fetch-leetcode",
        # Multi-scene + breakdown + quiz
        "/api/render-lesson",
        "/api/breakdown",
        "/api/quiz",
        "/api/quiz-attempt",
        # OCR / notes
        "/api/ocr",
        "/api/format-note",
        # Topics + prereqs
        "/api/topics",
        "/api/prereqs",
        # Observability
        "/api/trace/{job_id}",
    ]
    missing = [p for p in expected if p not in spec["paths"]]
    assert not missing, f"missing endpoints in OpenAPI: {missing}"


def test_openapi_components_reference_resolve():
    """Every $ref in the spec must point at a real component."""
    spec = build_openapi_spec()
    schemas = spec["components"]["schemas"]
    responses = spec["components"]["responses"]

    def collect_refs(node, refs):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "$ref" and isinstance(v, str):
                    refs.append(v)
                else:
                    collect_refs(v, refs)
        elif isinstance(node, list):
            for item in node:
                collect_refs(item, refs)

    refs: list[str] = []
    collect_refs(spec, refs)
    assert refs, "no $refs in spec — that's suspicious"
    for ref in refs:
        if ref.startswith("#/components/schemas/"):
            name = ref.removeprefix("#/components/schemas/")
            assert name in schemas, f"dangling schema ref: {ref}"
        elif ref.startswith("#/components/responses/"):
            name = ref.removeprefix("#/components/responses/")
            assert name in responses, f"dangling response ref: {ref}"


def test_openapi_direct_lesson_documents_target_minutes(client):
    """Item #10 added target_minutes — schema must list it with bounds."""
    res = client.get("/openapi.json")
    spec = res.get_json()
    req = spec["components"]["schemas"]["DirectLessonRequest"]
    tm = req["properties"]["target_minutes"]
    assert tm["type"] == "number"
    assert tm["minimum"] == 0.5
    assert tm["maximum"] == 10.0


# ─────────────────────────────────────────────────────────────────────────────
# Route-count coverage — fails when a new Flask endpoint ships without an
# OpenAPI entry. Catches the kind of drift that made the schema lie about
# what was supported.
# ─────────────────────────────────────────────────────────────────────────────


# Routes intentionally NOT in the public schema (e.g. static file serving,
# debug-only endpoints). Add a comment when expanding so the rationale is
# tracked alongside the exclusion.
_OPENAPI_ROUTE_EXCLUSIONS = {
    "/media/<path:filename>",   # static file serving, not an API
    "/openapi.json",            # the spec itself
    "/topics",                  # duplicated by /api/topics (alias)
}


def _flask_route_paths() -> list[str]:
    """Grep `backend/app.py` for `@app.<verb>("<path>")` decorators."""
    import os as _os
    import re as _re
    path = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
        "app.py",
    )
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return _re.findall(
        r"@app\.(?:get|post|put|delete|patch|route)\(\"([^\"]+)\"",
        text,
    )


def _flask_to_openapi(path: str) -> str:
    """Translate Flask path-syntax (<id>, <int:id>, <path:filename>) into
    the OpenAPI {id} curly-brace form."""
    import re as _re
    return _re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", path)


def test_openapi_path_count_matches_route_count(client):
    """For every Flask route, either the spec documents it OR it appears in
    the explicit _OPENAPI_ROUTE_EXCLUSIONS allowlist. Catches drift."""
    res = client.get("/openapi.json")
    spec_paths = set(res.get_json()["paths"].keys())

    flask_paths = _flask_route_paths()
    undocumented = []
    for fp in flask_paths:
        if fp in _OPENAPI_ROUTE_EXCLUSIONS:
            continue
        canonical = _flask_to_openapi(fp)
        if canonical not in spec_paths:
            undocumented.append(fp)
    assert not undocumented, (
        "These routes ship without an OpenAPI entry — add them to "
        "openapi_spec.py or to _OPENAPI_ROUTE_EXCLUSIONS with a comment: "
        f"{undocumented}"
    )
