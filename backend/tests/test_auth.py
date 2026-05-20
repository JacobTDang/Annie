"""Tests for the optional Supabase auth verifier (Item #17)."""
import base64
import hashlib
import hmac
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import auth


# ─────────────────────────────────────────────────────────────────────────────
# Helpers to mint test tokens (no third-party JWT library required)
# ─────────────────────────────────────────────────────────────────────────────


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _mint_jwt(payload: dict, secret: str, alg: str = "HS256") -> str:
    header = {"alg": alg, "typ": "JWT"}
    h_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode())
    p_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    message = f"{h_b64}.{p_b64}".encode("ascii")
    sig = hmac.new(secret.encode(), message, hashlib.sha256).digest()
    return f"{h_b64}.{p_b64}.{_b64url(sig)}"


# ─────────────────────────────────────────────────────────────────────────────
# is_enabled / current_user — env-gated
# ─────────────────────────────────────────────────────────────────────────────


def test_is_enabled_default_off(monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    assert auth.is_enabled() is False


def test_is_enabled_when_secret_set(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "sek")
    assert auth.is_enabled() is True


def test_current_user_none_when_auth_disabled(monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    fake = type("R", (), {"headers": {"Authorization": "Bearer xxx"}})()
    assert auth.current_user(fake) is None


def test_current_user_none_when_no_authorization_header(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "sek")
    fake = type("R", (), {"headers": {}})()
    assert auth.current_user(fake) is None


def test_current_user_returns_claims_for_valid_token(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "topsecret")
    token = _mint_jwt(
        {"sub": "user-1", "email": "a@b.com", "exp": int(time.time()) + 3600},
        "topsecret",
    )
    fake = type("R", (), {"headers": {"Authorization": f"Bearer {token}"}})()
    claims = auth.current_user(fake)
    assert claims is not None
    assert claims["sub"] == "user-1"
    assert claims["email"] == "a@b.com"


# ─────────────────────────────────────────────────────────────────────────────
# verify_supabase_jwt — pure helper edge cases
# ─────────────────────────────────────────────────────────────────────────────


def test_verify_rejects_garbage():
    assert auth.verify_supabase_jwt("not.a.jwt", secret="x") is None
    assert auth.verify_supabase_jwt("", secret="x") is None
    assert auth.verify_supabase_jwt(None, secret="x") is None  # type: ignore


def test_verify_rejects_wrong_secret():
    token = _mint_jwt({"sub": "u1", "exp": int(time.time()) + 60}, "secret-a")
    assert auth.verify_supabase_jwt(token, secret="secret-b") is None


def test_verify_rejects_expired_token():
    token = _mint_jwt({"sub": "u1", "exp": int(time.time()) - 60}, "x")
    assert auth.verify_supabase_jwt(token, secret="x") is None


def test_verify_rejects_alg_other_than_hs256():
    """Fail-closed against alg=none and RS256 (we deliberately don't handle it)."""
    # Build a token with alg: none — the signature is empty
    header = {"alg": "none", "typ": "JWT"}
    payload = {"sub": "evil"}
    h = _b64url(json.dumps(header).encode())
    p = _b64url(json.dumps(payload).encode())
    token = f"{h}.{p}."
    assert auth.verify_supabase_jwt(token, secret="x") is None


def test_verify_returns_claims_on_success():
    token = _mint_jwt(
        {"sub": "user-42", "email": "x@y", "role": "authenticated",
         "exp": int(time.time()) + 3600},
        "shh",
    )
    claims = auth.verify_supabase_jwt(token, secret="shh")
    assert claims["sub"] == "user-42"
    assert claims["role"] == "authenticated"


def test_verify_respects_nbf_not_before():
    token = _mint_jwt(
        {"sub": "u1", "nbf": int(time.time()) + 60,
         "exp": int(time.time()) + 3600},
        "k",
    )
    assert auth.verify_supabase_jwt(token, secret="k") is None


# ─────────────────────────────────────────────────────────────────────────────
# Frontend module sanity check (structural)
# ─────────────────────────────────────────────────────────────────────────────


def test_frontend_auth_module_exposes_required_surface():
    import os as _os
    path = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))),
        "frontend", "src", "lib", "auth.ts",
    )
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for name in ["isAuthEnabled", "getUser", "getAccessToken",
                 "signInWithEmail", "signOut", "LumenUser"]:
        assert name in text, f"frontend/src/lib/auth.ts must export {name}"
    # Lazy dynamic import so the SDK doesn't bloat the main bundle
    assert "await import" in text
