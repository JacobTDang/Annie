"""
Supabase auth — optional sign-in (Item #17).

Anonymous use stays the default: when the SUPABASE_JWT_SECRET env var is
unset, ``current_user()`` returns None and everything works as before. When
it IS set, Authorization: Bearer <token> headers are verified and the user
record (sub, email, role) is attached to the request.

We use stdlib HMAC-SHA256 to verify the token (no PyJWT dep). This covers
Supabase's default HS256 signing. RS256 / JWKS rotation is intentionally
out of scope — operators using RS256 should add PyJWT themselves and swap
``_verify_signature``.

Public surface:
    current_user(request) -> dict | None
        Returns the verified JWT claims (with ``sub``, ``email``, ``role``)
        or None if anonymous / unverifiable.

    is_enabled() -> bool
        True iff SUPABASE_JWT_SECRET is set.

    verify_supabase_jwt(token, secret=None, now=None) -> dict | None
        Pure helper. Returns the JWT claims dict on success, None on any
        failure. Used by current_user() and by tests.
"""
from __future__ import annotations

import base64
import hmac
import hashlib
import json
import os
import time


def is_enabled() -> bool:
    return bool(os.environ.get("SUPABASE_JWT_SECRET", "").strip())


def _b64url_decode(data: str) -> bytes:
    """Decode a base64url string, padding it as needed."""
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _verify_signature(message: bytes, signature: bytes, secret: str) -> bool:
    expected = hmac.new(
        secret.encode("utf-8"), message, hashlib.sha256,
    ).digest()
    return hmac.compare_digest(expected, signature)


def verify_supabase_jwt(token: str, secret: str | None = None,
                         now: float | None = None) -> dict | None:
    """Verify an HS256 Supabase JWT. Returns claims dict, or None on any failure.

    ``secret`` defaults to the SUPABASE_JWT_SECRET env var.
    ``now`` is the current UNIX timestamp (defaults to time.time()) — exposed
    for deterministic tests.
    """
    if not token or not isinstance(token, str):
        return None
    secret = secret if secret is not None else os.environ.get("SUPABASE_JWT_SECRET", "")
    if not secret:
        return None

    parts = token.split(".")
    if len(parts) != 3:
        return None
    header_b64, payload_b64, signature_b64 = parts
    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(signature_b64)
    except (ValueError, json.JSONDecodeError):
        return None

    # Only support HS256 — fail closed if the token specifies anything else.
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        return None

    message = f"{header_b64}.{payload_b64}".encode("ascii")
    if not _verify_signature(message, signature, secret):
        return None

    # Expiry — Supabase always sets `exp`. Reject expired tokens.
    now = now if now is not None else time.time()
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and now >= exp:
        return None

    # nbf (not-before) is optional; honor it if present.
    nbf = payload.get("nbf")
    if isinstance(nbf, (int, float)) and now < nbf:
        return None

    return payload if isinstance(payload, dict) else None


def current_user(request) -> dict | None:
    """Extract + verify the Bearer token from a Flask request.

    Returns the claims dict (with ``sub``, ``email`` etc.) on success, or
    None if no token / invalid token / auth disabled.
    """
    if not is_enabled():
        return None
    auth_header = (request.headers.get("Authorization") or "").strip()
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header[7:].strip()
    return verify_supabase_jwt(token)
