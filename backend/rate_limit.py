"""
Per-IP sliding-window rate limiter (Item #18).

Hand-rolled, in-memory — no Redis dep. Sufficient for single-process Flask in
dev/hackathon scope. In production, put nginx / Cloudflare / a proper limiter
in front; this is a backstop.

Usage:
    from rate_limit import check_rate_limit
    allowed, retry_after = check_rate_limit(key="ip:1.2.3.4",
                                              max_requests=10,
                                              window_seconds=86400)
    if not allowed:
        return jsonify({"error": "rate limit exceeded"}), 429, \\
               {"Retry-After": str(retry_after)}
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


_LOCK = threading.Lock()
_HITS: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(key: str, max_requests: int,
                      window_seconds: int) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds).

    The window is a sliding count over the last ``window_seconds``. When the
    limit is exceeded, ``retry_after`` is the seconds-to-wait until the
    oldest hit ages out of the window.

    A ``max_requests`` of 0 or negative means "no limit" → always allowed.
    """
    if max_requests <= 0:
        return True, 0

    now = time.monotonic()
    cutoff = now - window_seconds

    with _LOCK:
        bucket = _HITS[key]
        # Drop hits older than the window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= max_requests:
            # The retry-after is how long until the oldest hit falls out
            oldest = bucket[0]
            retry_after = max(1, int(oldest + window_seconds - now) + 1)
            return False, retry_after

        bucket.append(now)
        return True, 0


def reset_all() -> None:
    """Clear every bucket. For tests."""
    with _LOCK:
        _HITS.clear()


def current_count(key: str, window_seconds: int) -> int:
    """How many hits ``key`` has within the current window. For tests."""
    now = time.monotonic()
    cutoff = now - window_seconds
    with _LOCK:
        bucket = _HITS.get(key)
        if not bucket:
            return 0
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        return len(bucket)
