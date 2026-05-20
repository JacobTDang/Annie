"""Tests for the Fly.io deploy surface (deploy-config item).

We don't actually `fly deploy` from CI — the tests validate the static
manifests so a typo doesn't surface as a 500 in production.
"""
import os
import re

import pytest
import yaml


_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
_BACKEND_FLY = os.path.join(_REPO_ROOT, "fly.toml")
_FRONTEND_FLY = os.path.join(_REPO_ROOT, "frontend", "fly.toml")
_BACKEND_DOCKERFILE = os.path.join(_REPO_ROOT, "backend", "Dockerfile")
_FRONTEND_DOCKERFILE = os.path.join(_REPO_ROOT, "frontend", "Dockerfile")
_NGINX_CONF = os.path.join(_REPO_ROOT, "frontend", "nginx.conf")
_BACKEND_APP = os.path.join(_REPO_ROOT, "backend", "app.py")
_BACKEND_REQS = os.path.join(_REPO_ROOT, "backend", "requirements.txt")
_DEPLOY_WF = os.path.join(_REPO_ROOT, ".github", "workflows", "deploy.yml")
_README = os.path.join(_REPO_ROOT, "README.md")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ─────────────────────────────────────────────────────────────────────────────
# Backend fly.toml
# ─────────────────────────────────────────────────────────────────────────────


def test_backend_fly_toml_exists_and_targets_backend_dockerfile():
    assert os.path.exists(_BACKEND_FLY), "missing fly.toml at repo root"
    text = _read(_BACKEND_FLY)
    # Build context implicit (repo root); dockerfile must point at backend/
    assert 'dockerfile = "backend/Dockerfile"' in text


def test_backend_fly_toml_mounts_media_volume():
    """The local-storage backend writes to /app/backend/media; without a
    volume mount, pinned videos + cache + jobs.db evaporate on redeploy."""
    text = _read(_BACKEND_FLY)
    assert "[mounts]" in text
    assert 'destination = "/app/backend/media"' in text
    assert 'source = "lumen_media"' in text


def test_backend_fly_toml_sets_jobs_db_path():
    """SQLite jobs DB (Item #13) must live on the persistent volume too."""
    text = _read(_BACKEND_FLY)
    assert "LUMEN_JOBS_DB" in text
    assert "/app/backend/media/jobs.db" in text


def test_backend_fly_toml_declares_healthcheck():
    text = _read(_BACKEND_FLY)
    assert "/health" in text
    assert "[checks." in text or "[[checks]]" in text


# ─────────────────────────────────────────────────────────────────────────────
# Frontend fly.toml
# ─────────────────────────────────────────────────────────────────────────────


def test_frontend_fly_toml_exists_and_routes_to_backend_internal():
    assert os.path.exists(_FRONTEND_FLY)
    text = _read(_FRONTEND_FLY)
    assert 'dockerfile = "frontend/Dockerfile"' in text
    # Internal DNS routing so backend traffic doesn't egress
    assert "lumen-api.internal" in text


# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile + app.py — production runtime
# ─────────────────────────────────────────────────────────────────────────────


def test_backend_dockerfile_uses_gunicorn():
    """Flask's dev server is not safe in prod. Catches a regression to
    `python app.py` as the entrypoint."""
    text = _read(_BACKEND_DOCKERFILE)
    assert "gunicorn" in text.lower()
    # Specifically must be the CMD, not just a comment
    assert re.search(r"CMD\s*\[[^\]]*gunicorn", text)


def test_requirements_includes_gunicorn():
    text = _read(_BACKEND_REQS)
    assert re.search(r"^gunicorn", text, re.MULTILINE), (
        "gunicorn must be in backend/requirements.txt — base, not extras"
    )


def test_backend_app_reads_port_env_var():
    """Fly + most PaaS platforms inject PORT. The dev fallback (5000) is
    fine, but the app MUST honor an override."""
    text = _read(_BACKEND_APP)
    assert 'os.environ.get("PORT"' in text


def test_backend_app_binds_all_interfaces():
    """Inside a container, 127.0.0.1 isn't reachable from outside the pod."""
    text = _read(_BACKEND_APP)
    assert 'host="0.0.0.0"' in text or "host='0.0.0.0'" in text


# ─────────────────────────────────────────────────────────────────────────────
# nginx + frontend Dockerfile
# ─────────────────────────────────────────────────────────────────────────────


def test_nginx_proxy_host_is_configurable():
    """The hard-coded `server backend:5000;` from Item #16 must not regress —
    Fly needs `lumen-api.internal:5000` and the template handles both."""
    text = _read(_NGINX_CONF)
    assert "${BACKEND_HOST}" in text
    assert "${BACKEND_PORT}" in text
    # Defensive: there shouldn't be a literal `server backend:5000;` line
    assert "server backend:5000" not in text


def test_frontend_dockerfile_uses_nginx_template_dir():
    """`/etc/nginx/templates/` is the path nginx:alpine's entrypoint scans
    for envsubst. Without this rename the BACKEND_HOST substitution never runs."""
    text = _read(_FRONTEND_DOCKERFILE)
    assert "/etc/nginx/templates" in text


def test_frontend_dockerfile_sets_default_backend_host():
    """Local docker-compose path still works — Compose's service network
    exposes the backend as `backend`."""
    text = _read(_FRONTEND_DOCKERFILE)
    assert "ENV BACKEND_HOST" in text
    assert "backend" in text


# ─────────────────────────────────────────────────────────────────────────────
# CI deploy workflow
# ─────────────────────────────────────────────────────────────────────────────


def test_deploy_workflow_exists_and_is_manual_only():
    """Auto-deploy on push is too risky for a hackathon repo. Force the
    workflow to be manually triggered from the Actions tab."""
    assert os.path.exists(_DEPLOY_WF)
    wf = yaml.safe_load(_read(_DEPLOY_WF))
    triggers = wf.get("on") or wf.get(True)
    assert "workflow_dispatch" in triggers
    # And NOT push — paranoid double-check
    assert "push" not in triggers


def test_deploy_workflow_uses_fly_token():
    text = _read(_DEPLOY_WF)
    assert "FLY_API_TOKEN" in text
    assert "secrets.FLY_API_TOKEN" in text


def test_deploy_workflow_runs_both_app_deploys():
    wf = yaml.safe_load(_read(_DEPLOY_WF))
    jobs = wf["jobs"]
    assert "backend" in jobs
    assert "frontend" in jobs
    # Frontend must wait for backend to be healthy first (Fly internal DNS
    # only resolves once the backend app exists)
    assert jobs["frontend"].get("needs") == "backend"


# ─────────────────────────────────────────────────────────────────────────────
# README pointer
# ─────────────────────────────────────────────────────────────────────────────


def test_readme_documents_fly_deploy():
    text = _read(_README)
    assert "Fly.io" in text or "fly.io" in text.lower()
    assert "fly deploy" in text.lower()
    assert "lumen_media" in text or "lumen-media" in text.lower()
