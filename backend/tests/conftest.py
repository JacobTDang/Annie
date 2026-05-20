import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def client():
    from app import create_app
    app = create_app(testing=True)
    with app.test_client() as c:
        yield c


def pytest_sessionfinish(session, exitstatus):
    """Drain the worker's background queue before pytest finalizes thread pools.

    Tests submit lessons via the InProcessQueue but rarely poll for completion,
    so without this hook the daemon `_run_lesson` thread runs past teardown
    and trips ``RuntimeError: cannot schedule new futures after interpreter
    shutdown`` when its inner ThreadPoolExecutor.submit fires.
    """
    try:
        # Lazy import — keeps conftest cheap when only collecting tests
        from renderer import worker as _worker
        _worker.shutdown(wait=True, timeout=5.0)
    except Exception:
        # Never let a teardown helper fail the test session
        pass
