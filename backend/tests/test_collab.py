"""Tests for the real-time-collab WebSocket relay (Item #30)."""
import os
import sys
import threading
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import collab


@pytest.fixture(autouse=True)
def _reset_rooms():
    """Each test starts with an empty room registry."""
    with collab._ROOMS_LOCK:
        collab._rooms.clear()
    yield
    with collab._ROOMS_LOCK:
        collab._rooms.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Room id validation
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("rid", [
    "abc", "abc123", "lesson-42", "room_with_underscores",
    "A" * 64,        # max length
])
def test_valid_room_ids(rid):
    assert collab._validate_room_id(rid) is True


@pytest.mark.parametrize("rid", [
    "",
    "A" * 65,                       # too long
    "../etc/passwd",                # path injection
    "room with space",
    "room/slash",
    "room?query",
    None,                           # falsy → rejected without raising
])
def test_invalid_room_ids(rid):
    assert collab._validate_room_id(rid) is False


# ─────────────────────────────────────────────────────────────────────────────
# Room registry primitives
# ─────────────────────────────────────────────────────────────────────────────


def test_add_then_remove_socket_round_trip():
    sock = MagicMock()
    collab._add_socket("r1", sock)
    assert collab.room_size("r1") == 1
    collab._remove_socket("r1", sock)
    assert collab.room_size("r1") == 0


def test_room_pruned_when_empty():
    """Empty rooms must not linger in the registry — prevents unbounded growth
    from short-lived rooms over the lifetime of the process."""
    sock = MagicMock()
    collab._add_socket("ephemeral", sock)
    collab._remove_socket("ephemeral", sock)
    with collab._ROOMS_LOCK:
        assert "ephemeral" not in collab._rooms


def test_remove_socket_idempotent():
    """Removing a never-added socket must be safe."""
    sock = MagicMock()
    collab._remove_socket("missing", sock)
    assert collab.room_size("missing") == 0


def test_peers_snapshot_excludes_sender():
    a, b, c = MagicMock(), MagicMock(), MagicMock()
    collab._add_socket("r", a)
    collab._add_socket("r", b)
    collab._add_socket("r", c)
    peers = collab._peers_snapshot("r", exclude=b)
    assert set(peers) == {a, c}


def test_peers_snapshot_unknown_room_returns_empty():
    assert collab._peers_snapshot("nope", exclude=None) == []


# ─────────────────────────────────────────────────────────────────────────────
# Broadcast — the core relay behavior
# ─────────────────────────────────────────────────────────────────────────────


def test_broadcast_fans_out_to_all_peers_except_sender():
    a, b, c = MagicMock(), MagicMock(), MagicMock()
    collab._add_socket("r", a)
    collab._add_socket("r", b)
    collab._add_socket("r", c)

    sent = collab._broadcast("r", b"hello", sender=a)
    assert sent == 2  # b and c
    b.send.assert_called_once_with(b"hello")
    c.send.assert_called_once_with(b"hello")
    a.send.assert_not_called()


def test_broadcast_skips_other_rooms():
    """Cross-room leakage would let any client read any room. Verify the
    relay is room-scoped."""
    a = MagicMock()
    b = MagicMock()
    collab._add_socket("room1", a)
    collab._add_socket("room2", b)
    sent = collab._broadcast("room1", b"x", sender=a)
    assert sent == 0
    b.send.assert_not_called()


def test_broadcast_drops_dead_sockets():
    """If a peer's .send raises, the broadcast continues to others AND the
    dead socket is removed from the room."""
    a = MagicMock()
    b = MagicMock()
    b.send.side_effect = ConnectionError("peer gone")
    c = MagicMock()
    collab._add_socket("r", a)
    collab._add_socket("r", b)
    collab._add_socket("r", c)
    sent = collab._broadcast("r", b"hi", sender=a)
    assert sent == 1   # only c succeeded
    c.send.assert_called_once_with(b"hi")
    # b should have been dropped
    with collab._ROOMS_LOCK:
        assert b not in collab._rooms["r"]


def test_broadcast_handles_binary_yjs_frames():
    """Yjs uses raw binary CRDT messages. The relay must be byte-transparent
    — no UTF-8 decoding attempts that would corrupt the protocol."""
    a, b = MagicMock(), MagicMock()
    collab._add_socket("r", a)
    collab._add_socket("r", b)
    binary_payload = bytes(range(256))
    collab._broadcast("r", binary_payload, sender=a)
    b.send.assert_called_once_with(binary_payload)


# ─────────────────────────────────────────────────────────────────────────────
# Concurrency — the lock must serialize correctly
# ─────────────────────────────────────────────────────────────────────────────


def test_concurrent_add_remove_doesnt_corrupt_registry():
    """Hammer the registry from multiple threads; assert no exceptions and
    the final state is consistent."""
    n_threads = 16
    per_thread = 100
    barrier = threading.Barrier(n_threads)

    def hammer():
        barrier.wait()
        socks = [MagicMock() for _ in range(per_thread)]
        for s in socks:
            collab._add_socket("hammer", s)
        for s in socks:
            collab._remove_socket("hammer", s)

    threads = [threading.Thread(target=hammer) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Every socket added was also removed → room should be empty/missing
    assert collab.room_size("hammer") == 0


# ─────────────────────────────────────────────────────────────────────────────
# Flask integration — route registration
# ─────────────────────────────────────────────────────────────────────────────


def test_route_registration_idempotent():
    """Repeated register_collab_routes calls must not duplicate the route."""
    from app import create_app
    app = create_app(testing=True)
    rules_before = {r.rule for r in app.url_map.iter_rules()}
    collab.register_collab_routes(app)  # should be a no-op
    rules_after = {r.rule for r in app.url_map.iter_rules()}
    assert rules_before == rules_after


def test_collab_route_attached_to_app():
    from app import create_app
    app = create_app(testing=True)
    rules = {r.rule for r in app.url_map.iter_rules()}
    assert "/api/collab/<room_id>" in rules
