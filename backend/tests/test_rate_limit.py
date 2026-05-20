"""Tests for the per-IP sliding-window rate limiter (Item #18)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import rate_limit
from app import create_app


@pytest.fixture(autouse=True)
def _reset_buckets():
    rate_limit.reset_all()
    yield
    rate_limit.reset_all()


def test_under_limit_allowed():
    for i in range(5):
        allowed, retry = rate_limit.check_rate_limit("k", 5, 60)
        assert allowed is True
        assert retry == 0


def test_over_limit_blocked_with_retry_after():
    for _ in range(3):
        rate_limit.check_rate_limit("k", 3, 60)
    allowed, retry = rate_limit.check_rate_limit("k", 3, 60)
    assert allowed is False
    # retry_after rounds up so it can be window + 1 in the worst case
    assert 0 < retry <= 61


def test_different_keys_are_isolated():
    for _ in range(3):
        rate_limit.check_rate_limit("a", 3, 60)
    # b should still have full budget
    allowed, _ = rate_limit.check_rate_limit("b", 3, 60)
    assert allowed is True


def test_zero_max_means_no_limit():
    for _ in range(100):
        allowed, _ = rate_limit.check_rate_limit("k", 0, 60)
        assert allowed is True


def test_current_count_reports_window_count():
    rate_limit.check_rate_limit("k", 10, 60)
    rate_limit.check_rate_limit("k", 10, 60)
    assert rate_limit.current_count("k", 60) == 2


# ─────────────────────────────────────────────────────────────────────────────
# Integration with Flask app — verify endpoints honor the limiter
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def client_with_limit(monkeypatch):
    """Client where the limiter is active (3 requests per very long window)."""
    monkeypatch.setenv("LUMEN_RATE_LIMIT", "3")
    monkeypatch.setenv("LUMEN_RATE_LIMIT_WINDOW_SECONDS", "86400")
    # NOTE: testing=False so the in-app guard isn't disabled
    app = create_app(testing=False)
    return app.test_client()


def test_direct_lesson_returns_429_after_limit(client_with_limit, mocker):
    """Item #18 regression: 4th call from same IP must hit 429."""
    mocker.patch("app.submit_direct_lesson", return_value="job-123")
    headers = {"X-Forwarded-For": "9.9.9.9"}
    for i in range(3):
        res = client_with_limit.post("/api/direct-lesson",
                                       json={"question": "x"},
                                       headers=headers)
        assert res.status_code == 202, f"call {i+1} should pass"
    res = client_with_limit.post("/api/direct-lesson",
                                   json={"question": "x"},
                                   headers=headers)
    assert res.status_code == 429
    assert "Retry-After" in res.headers
    body = res.get_json()
    assert "rate limit" in body["error"].lower()


def test_rate_limit_isolates_ips(client_with_limit, mocker):
    """Different IPs share no quota."""
    mocker.patch("app.submit_direct_lesson", return_value="job-x")
    for _ in range(3):
        client_with_limit.post("/api/direct-lesson",
                                json={"question": "x"},
                                headers={"X-Forwarded-For": "1.1.1.1"})
    # 1.1.1.1 is at cap; 2.2.2.2 should still pass
    res = client_with_limit.post("/api/direct-lesson",
                                   json={"question": "x"},
                                   headers={"X-Forwarded-For": "2.2.2.2"})
    assert res.status_code == 202


def test_health_not_rate_limited(client_with_limit):
    """Cheap endpoints (health/status) must NOT consume the budget."""
    for _ in range(20):
        res = client_with_limit.get("/health")
        assert res.status_code == 200


def test_rate_limit_disabled_in_testing_mode(mocker):
    """create_app(testing=True) must completely disable the limiter."""
    mocker.patch("app.submit_direct_lesson", return_value="job-z")
    app = create_app(testing=True)
    client = app.test_client()
    for _ in range(50):
        res = client.post("/api/direct-lesson",
                           json={"question": "x"},
                           headers={"X-Forwarded-For": "5.5.5.5"})
        assert res.status_code == 202
