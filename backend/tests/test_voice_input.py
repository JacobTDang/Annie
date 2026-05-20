"""Structural regression tests for Item #33 (browser voice input)."""
import os
import re


_REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
_VOICE_HELPER = os.path.join(
    _REPO_ROOT, "frontend", "src", "lib", "voiceInput.ts",
)
_PASTE_PAGE = os.path.join(
    _REPO_ROOT, "frontend", "src", "pages", "PasteProblemPage.tsx",
)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_voice_helper_exists():
    assert os.path.exists(_VOICE_HELPER), f"missing {_VOICE_HELPER}"


def test_voice_helper_exports_required_surface():
    text = _read(_VOICE_HELPER)
    assert re.search(r"export\s+function\s+isVoiceInputSupported", text)
    assert re.search(r"export\s+function\s+createVoiceRecognizer", text)
    assert re.search(r"export\s+interface\s+VoiceRecognizer\b", text)


def test_voice_helper_uses_native_speech_recognition():
    """We deliberately do NOT pull in transformers.js — the helper must rely
    on the browser's native SpeechRecognition global."""
    text = _read(_VOICE_HELPER)
    assert "SpeechRecognition" in text
    assert "webkitSpeechRecognition" in text
    # Confirm we are NOT importing the heavy Whisper dep (comments mentioning
    # the decision are fine — actual imports are not).
    assert not re.search(r"^\s*import .*transformers", text, re.MULTILINE)
    assert not re.search(r"^\s*import .*whisper", text, re.MULTILINE)


def test_paste_page_renders_mic_button_when_supported():
    text = _read(_PASTE_PAGE)
    # Wired the imports
    assert "isVoiceInputSupported" in text
    assert "createVoiceRecognizer" in text
    # Conditional render — only when the browser supports it
    assert "voiceSupported &&" in text or "{voiceSupported" in text
    # Button label / state
    assert "Listening" in text
    # Lucide mic icon
    assert "Mic" in text


def test_paste_page_releases_mic_on_unmount():
    """Critical UX: if the component unmounts mid-record, we MUST abort
    the recognizer so the mic indicator goes away."""
    text = _read(_PASTE_PAGE)
    assert "abort()" in text
