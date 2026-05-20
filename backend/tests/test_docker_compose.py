"""Structural assertions for the Docker / Compose surface (Item #16).

We don't actually `docker compose up` — those are integration concerns that
belong on the operator. These tests verify the manifests are well-formed and
contain the services + volumes the README promises.
"""
import os

import pytest
import yaml


_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
_COMPOSE = os.path.join(_REPO_ROOT, "docker-compose.yml")
_BACKEND_DOCKERFILE = os.path.join(_REPO_ROOT, "backend", "Dockerfile")
_FRONTEND_DOCKERFILE = os.path.join(_REPO_ROOT, "frontend", "Dockerfile")
_NGINX_CONF = os.path.join(_REPO_ROOT, "frontend", "nginx.conf")
_DOCKERIGNORE = os.path.join(_REPO_ROOT, ".dockerignore")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(_read(_COMPOSE))


# ── Files exist ────────────────────────────────────────────────────────────


def test_required_files_present():
    for path in [_COMPOSE, _BACKEND_DOCKERFILE, _FRONTEND_DOCKERFILE,
                 _NGINX_CONF, _DOCKERIGNORE]:
        assert os.path.exists(path), f"missing {path}"


# ── docker-compose.yml ─────────────────────────────────────────────────────


def test_compose_yaml_parses(compose):
    assert isinstance(compose, dict)
    assert "services" in compose


def test_compose_declares_three_services(compose):
    """Plan default: backend + frontend + redis."""
    services = set(compose["services"].keys())
    assert {"backend", "frontend", "redis"}.issubset(services)


def test_compose_backend_uses_repo_root_context(compose):
    backend = compose["services"]["backend"]
    # The Dockerfile is at backend/Dockerfile but compose context must be `.`
    # so it can COPY frontend/ at the same level — same shape for both services.
    assert backend["build"]["dockerfile"] == "backend/Dockerfile"


def test_compose_mounts_media_volume(compose):
    backend = compose["services"]["backend"]
    vols = backend.get("volumes", [])
    assert any("lumen-media:/app/backend/media" in v for v in vols), (
        "backend must mount the shared media volume"
    )
    # And the volume itself is declared at the top level
    assert "lumen-media" in compose.get("volumes", {})


def test_compose_frontend_waits_on_backend_health(compose):
    fe = compose["services"]["frontend"]
    deps = fe.get("depends_on") or {}
    if isinstance(deps, list):
        assert "backend" in deps
    else:
        assert "backend" in deps
        assert deps["backend"].get("condition") == "service_healthy"


def test_compose_redis_is_alpine_image(compose):
    redis = compose["services"]["redis"]
    assert "redis:" in redis["image"]
    assert "alpine" in redis["image"]


def test_compose_uses_env_file_for_secrets(compose):
    backend = compose["services"]["backend"]
    env_files = backend.get("env_file") or []
    if isinstance(env_files, str):
        env_files = [env_files]
    assert any(".env" in p for p in env_files), (
        "backend must read secrets from backend/.env"
    )


# ── Dockerfiles ────────────────────────────────────────────────────────────


def test_backend_dockerfile_runs_app():
    text = _read(_BACKEND_DOCKERFILE)
    assert "FROM python:3.11" in text
    assert "ffmpeg" in text
    assert "libcairo2" in text  # Manim requirement
    assert "EXPOSE 5000" in text
    assert "CMD" in text and "python" in text


def test_backend_dockerfile_caches_pip_install():
    """Bug regression: copying source before pip install busts the cache on
    every code change. Requirements.txt must be COPYed before the source tree."""
    text = _read(_BACKEND_DOCKERFILE)
    req_pos = text.index("requirements.txt")
    src_copy_pos = text.index("COPY backend /app/backend")
    assert req_pos < src_copy_pos


def test_frontend_dockerfile_is_multistage():
    text = _read(_FRONTEND_DOCKERFILE)
    # Should have a node build stage and an nginx serve stage
    assert "FROM node:" in text
    assert "FROM nginx:" in text
    assert "AS build" in text
    # Final stage copies the dist/ artifact from the build stage
    assert "COPY --from=build" in text


def test_nginx_proxies_backend_routes():
    text = _read(_NGINX_CONF)
    for route in ["/api/", "/media/", "/status/", "/openapi.json"]:
        assert route in text, f"nginx must proxy {route}"
    # SPA fallback so client-side routing works
    assert "try_files" in text and "index.html" in text


def test_dockerignore_excludes_local_state():
    text = _read(_DOCKERIGNORE)
    for entry in ["venv", "node_modules", "backend/.env", ".git"]:
        assert entry in text, f".dockerignore must exclude {entry}"
