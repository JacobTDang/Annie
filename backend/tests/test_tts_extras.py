"""Structural tests for the TTS extras setup (Item #8 follow-up)."""
import os

import yaml


_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
_EXTRAS = os.path.join(_REPO_ROOT, "backend", "requirements-extras.txt")
_SECRETS_DOC = os.path.join(_REPO_ROOT, "docs", "SECRETS.md")
_CI_WORKFLOW = os.path.join(_REPO_ROOT, ".github", "workflows", "test.yml")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_tts_extras_file_exists_and_lists_edge_tts():
    assert os.path.exists(_EXTRAS), (
        "backend/requirements-extras.txt missing — install pointer in "
        "SECRETS.md is a lie without it."
    )
    text = _read(_EXTRAS)
    # Active line for edge-tts must be present and not commented out
    import re
    assert re.search(r"^edge-tts", text, re.MULTILINE), (
        "edge-tts must be an active dependency in requirements-extras.txt"
    )


def test_secrets_doc_links_to_extras_install():
    """The TTS env var row would be misleading without an install pointer."""
    text = _read(_SECRETS_DOC)
    assert "requirements-extras.txt" in text, (
        "docs/SECRETS.md must mention requirements-extras.txt so operators "
        "know how to actually get audio out of LUMEN_TTS_ENABLED=1"
    )
    # Mention of edge-tts as the default provider
    assert "edge-tts" in text.lower()


def test_ci_integration_job_installs_extras():
    """The integration job (manual workflow_dispatch) hits the real TTS chain;
    extras MUST be installed in CI or the audio tests are silent."""
    wf = yaml.safe_load(_read(_CI_WORKFLOW))
    integ = wf["jobs"]["integration"]
    steps = integ["steps"]
    commands = " ".join(s.get("run", "") for s in steps)
    assert "requirements-extras.txt" in commands, (
        "integration job must `pip install -r backend/requirements-extras.txt`"
    )


def test_extras_does_not_leak_into_base_requirements():
    """Bundle-size guardrail — edge-tts and pyttsx3 must NOT be in the base
    requirements.txt. They're opt-in by design."""
    base = _read(os.path.join(_REPO_ROOT, "backend", "requirements.txt"))
    import re
    # Match a top-level (uncommented) entry — comments are fine
    for pkg in ["edge-tts", "pyttsx3"]:
        assert not re.search(rf"^{re.escape(pkg)}\b", base, re.MULTILINE), (
            f"{pkg} should live in requirements-extras.txt, not base"
        )
