"""Structural assertions for Item #22 — secrets are documented.

Every env var the backend reads should appear in BOTH:
  - backend/.env.example (so a fresh checkout knows what to set)
  - docs/SECRETS.md (the canonical reference table)
"""
import os
import re

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_EXAMPLE = os.path.join(_REPO_ROOT, "backend", ".env.example")
_SECRETS_DOC = os.path.join(_REPO_ROOT, "docs", "SECRETS.md")


# Every variable the backend reads via os.environ — keep this in sync with
# new env reads. The test fails fast if a new variable is added without docs.
_REQUIRED_VARS = [
    "OPENROUTER_API_KEY",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_MODEL",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "SENTRY_DSN",
    "LUMEN_RATE_LIMIT",
    "LUMEN_RATE_LIMIT_WINDOW_SECONDS",
    "LUMEN_TTS_ENABLED",
]


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_env_example_exists():
    assert os.path.exists(_ENV_EXAMPLE), f"missing {_ENV_EXAMPLE}"


def test_secrets_doc_exists():
    assert os.path.exists(_SECRETS_DOC), f"missing {_SECRETS_DOC}"


@pytest.mark.parametrize("var", _REQUIRED_VARS)
def test_var_appears_in_env_example(var):
    text = _read(_ENV_EXAMPLE)
    assert re.search(rf"^#?\s*{re.escape(var)}=", text, re.MULTILINE), (
        f"{var} should be documented (commented or set) in backend/.env.example"
    )


@pytest.mark.parametrize("var", _REQUIRED_VARS)
def test_var_appears_in_secrets_doc(var):
    text = _read(_SECRETS_DOC)
    assert var in text, f"{var} missing from docs/SECRETS.md table"


def test_secrets_doc_mentions_github_actions():
    """The doc must call out the GH Actions Secrets workflow side."""
    text = _read(_SECRETS_DOC)
    assert "github" in text.lower() and "secrets" in text.lower()


def test_env_example_does_not_contain_real_keys():
    """Defensive: catch a stray real-looking key in the example file."""
    text = _read(_ENV_EXAMPLE)
    suspicious = re.findall(r"=(sk-[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9_-]{30,})",
                              text)
    assert not suspicious, f"possible real keys in .env.example: {suspicious}"
