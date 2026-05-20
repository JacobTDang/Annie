"""Tests for the real-time-collab WebSocket relay (Item #30)."""
import os
import sys
import threading
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import collab


@pytest.fixture(autouse=True)
def _reset_rooms(tmp_path, monkeypatch):
    """Each test starts with an empty room registry + tmp collab dir so
    persistence tests don't leak files into backend/media/collab/."""
    monkeypatch.setattr(collab, "_collab_dir", str(tmp_path / "collab"))
    with collab._ROOMS_LOCK:
        collab._rooms.clear()
        collab._docs.clear()
        collab._dirty.clear()
    yield
    with collab._ROOMS_LOCK:
        collab._rooms.clear()
        collab._docs.clear()
        collab._dirty.clear()


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


# ─────────────────────────────────────────────────────────────────────────────
# y-protocol varuint encode/decode
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("n", [0, 1, 127, 128, 255, 16384, 1_000_000])
def test_varuint_roundtrip(n):
    encoded = collab._write_varuint(n)
    decoded, offset = collab._read_varuint(encoded, 0)
    assert decoded == n
    assert offset == len(encoded)


def test_varuint_truncated_raises():
    with pytest.raises(ValueError, match="truncated"):
        collab._read_varuint(b"\x80", 0)   # continuation bit set, no follow-up


def test_varuint_payload_roundtrip():
    payload = b"hello world" * 10
    framed = collab._write_varuint_payload(payload)
    out, offset = collab._read_varuint_payload(framed, 0)
    assert out == payload
    assert offset == len(framed)


# ─────────────────────────────────────────────────────────────────────────────
# Persistence — snapshot ↔ load round-trip via y-py
# ─────────────────────────────────────────────────────────────────────────────


def _have_y_py() -> bool:
    try:
        import y_py  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _have_y_py(), reason="y-py not installed")
def test_snapshot_then_load_round_trip():
    import y_py
    doc = y_py.YDoc()
    text = doc.get_text("monaco")
    with doc.begin_transaction() as txn:
        text.extend(txn, "hello world")
    encoded = y_py.encode_state_as_update(doc)

    collab.snapshot_room("persist-1", encoded)
    loaded = collab.load_room("persist-1")
    assert loaded == encoded

    # Reload into a fresh doc and confirm content survived
    doc2 = y_py.YDoc()
    y_py.apply_update(doc2, loaded)
    assert str(doc2.get_text("monaco")) == "hello world"


def test_load_missing_room_returns_none():
    assert collab.load_room("never-existed") is None


# ─────────────────────────────────────────────────────────────────────────────
# Server-side Y.Doc lifecycle
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not _have_y_py(), reason="y-py not installed")
def test_get_or_create_doc_loads_from_snapshot():
    import y_py
    # Pre-seed a snapshot on disk
    doc = y_py.YDoc()
    with doc.begin_transaction() as txn:
        doc.get_text("monaco").extend(txn, "preexisting")
    collab.snapshot_room("with-snapshot", y_py.encode_state_as_update(doc))

    # First _get_or_create_doc call should load the snapshot
    server_doc = collab._get_or_create_doc("with-snapshot")
    assert server_doc is not None
    assert str(server_doc.get_text("monaco")) == "preexisting"


@pytest.mark.skipif(not _have_y_py(), reason="y-py not installed")
def test_room_empties_trigger_final_persist(tmp_path, monkeypatch):
    """When the last peer leaves, the server's Y.Doc must be flushed so
    next-time joiners get the latest state."""
    import y_py
    sock = MagicMock()
    collab._add_socket("empty-flush", sock)
    # Manually populate the server doc + mark dirty
    doc = collab._get_or_create_doc("empty-flush")
    with doc.begin_transaction() as txn:
        doc.get_text("monaco").extend(txn, "just before disconnect")
    collab._dirty.add("empty-flush")

    collab._remove_socket("empty-flush", sock)
    # Snapshot should exist on disk now
    blob = collab.load_room("empty-flush")
    assert blob is not None
    # Round-trip to verify content
    doc2 = y_py.YDoc()
    y_py.apply_update(doc2, blob)
    assert str(doc2.get_text("monaco")) == "just before disconnect"


def test_reconnect_during_persist_keeps_doc(monkeypatch):
    """Post-review regression: when the last socket leaves, _remove_socket
    releases _ROOMS_LOCK to do disk I/O. If a new peer connects during that
    window, the cleanup must NOT evict the doc out from under them.

    The test stubs _maybe_persist with a slow-noop instead of calling
    real persist — the real y_py.encode_state_as_update would touch the
    YDoc from a non-owning thread (YDoc is `unsendable`), tripping a
    PyO3 panic that's unrelated to the eviction-race contract under test.
    """
    persist_started = threading.Event()
    persist_can_finish = threading.Event()

    def slow_persist(room_id, force=False):
        persist_started.set()
        persist_can_finish.wait(timeout=2.0)
    monkeypatch.setattr(collab, "_maybe_persist", slow_persist)

    # Seed a sentinel "doc" so we can detect identity changes without touching y_py
    sentinel_doc = object()
    sock_a = MagicMock()
    collab._add_socket("race-room", sock_a)
    with collab._ROOMS_LOCK:
        collab._docs["race-room"] = sentinel_doc

    # Thread 1: remove the last socket → enters persist (which blocks)
    def remover():
        collab._remove_socket("race-room", sock_a)
    rm_thread = threading.Thread(target=remover)
    rm_thread.start()

    # Wait until the persist has started + the room has been popped
    assert persist_started.wait(timeout=2.0)
    # Sanity: the room is gone from _rooms but the doc is still in _docs
    with collab._ROOMS_LOCK:
        assert "race-room" not in collab._rooms
        assert "race-room" in collab._docs

    # Thread 2: new peer joins the same room during the persist
    sock_b = MagicMock()
    collab._add_socket("race-room", sock_b)

    # Release the persist + let the cleanup run
    persist_can_finish.set()
    rm_thread.join(timeout=2.0)

    # The doc should still be present (room re-occupied so cleanup bailed)
    with collab._ROOMS_LOCK:
        assert "race-room" in collab._docs, "cleanup evicted doc despite rejoin"
        assert collab._docs["race-room"] is sentinel_doc


@pytest.mark.skipif(not _have_y_py(), reason="y-py not installed")
def test_room_empties_drops_doc_from_memory():
    """After the last peer leaves, the in-memory Y.Doc must be released
    so room memory doesn't grow unbounded."""
    sock = MagicMock()
    collab._add_socket("evict-me", sock)
    collab._get_or_create_doc("evict-me")
    assert "evict-me" in collab._docs
    collab._remove_socket("evict-me", sock)
    assert "evict-me" not in collab._docs


# ─────────────────────────────────────────────────────────────────────────────
# y-protocol message handling
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.skipif(not _have_y_py(), reason="y-py not installed")
def test_sync_step_1_yields_sync_step_2():
    """When a client sends Sync Step 1 (state vector), the server must
    reply with Sync Step 2 (the diff). Sub-type byte 1 follows the type."""
    import y_py
    # Seed the server doc with some content so there's a diff to send
    doc = collab._get_or_create_doc("sync-test")
    with doc.begin_transaction() as txn:
        doc.get_text("monaco").extend(txn, "server-state")

    # Build a Sync Step 1 with an EMPTY state vector (client knows nothing)
    empty_state_vector = y_py.encode_state_vector(y_py.YDoc())
    msg = bytes([collab.MSG_SYNC, collab.SYNC_STEP_1]) \
          + collab._write_varuint_payload(empty_state_vector)

    reply = collab._handle_sync_message("sync-test", msg)
    assert reply is not None
    assert reply[0] == collab.MSG_SYNC
    # Sub-type follows; varuint-encoded but for small values it's just the byte
    sub_type, _ = collab._read_varuint(reply, 1)
    assert sub_type == collab.SYNC_STEP_2


@pytest.mark.skipif(not _have_y_py(), reason="y-py not installed")
def test_sync_update_applies_to_server_doc():
    """Sync Update messages must be folded into the server's Y.Doc so it
    stays canonical."""
    import y_py
    # Simulate a client-side doc with content, then encode its update
    client_doc = y_py.YDoc()
    with client_doc.begin_transaction() as txn:
        client_doc.get_text("monaco").extend(txn, "from-client")
    update_bytes = y_py.encode_state_as_update(client_doc)

    msg = bytes([collab.MSG_SYNC, collab.SYNC_UPDATE]) \
          + collab._write_varuint_payload(update_bytes)
    collab._handle_sync_message("update-test", msg)

    server_doc = collab._docs["update-test"]
    assert str(server_doc.get_text("monaco")) == "from-client"


def test_garbage_messages_dont_crash_handler():
    """Malformed inbound bytes from a buggy/hostile client must not blow up
    the relay thread."""
    # Truncated varuint after a valid type byte
    assert collab._handle_sync_message("rA", bytes([collab.MSG_SYNC, 0x80])) is None
    # Empty message
    assert collab._handle_sync_message("rB", b"") is None
    # Non-sync type byte (awareness etc.) — server doesn't reply
    assert collab._handle_sync_message("rC", bytes([collab.MSG_AWARENESS, 0])) is None


@pytest.mark.skipif(not _have_y_py(), reason="y-py not installed")
def test_full_handshake_persists_across_restart(tmp_path, monkeypatch):
    """End-to-end: client A sends an update, room empties (persist trigger),
    client B reconnects, server replies with Sync Step 2 containing A's content."""
    import y_py

    # Client A: connect, send an update, disconnect
    sockA = MagicMock()
    collab._add_socket("e2e", sockA)
    client_a_doc = y_py.YDoc()
    with client_a_doc.begin_transaction() as txn:
        client_a_doc.get_text("monaco").extend(txn, "persisted-by-A")
    update_a = y_py.encode_state_as_update(client_a_doc)
    msg_a = bytes([collab.MSG_SYNC, collab.SYNC_UPDATE]) \
            + collab._write_varuint_payload(update_a)
    collab._handle_sync_message("e2e", msg_a)
    collab._remove_socket("e2e", sockA)
    # Server should have flushed to disk on empty
    assert collab.load_room("e2e") is not None
    # And freed memory
    assert "e2e" not in collab._docs

    # Client B: connect, send Sync Step 1 with an empty state vector
    sockB = MagicMock()
    collab._add_socket("e2e", sockB)
    empty_sv = y_py.encode_state_vector(y_py.YDoc())
    step1 = bytes([collab.MSG_SYNC, collab.SYNC_STEP_1]) \
            + collab._write_varuint_payload(empty_sv)
    reply = collab._handle_sync_message("e2e", step1)
    assert reply is not None

    # B applies the server's Step 2 reply — should contain A's content
    # Reply frame: [type][sub_type][varuint(len)][update]
    sub_type, offset = collab._read_varuint(reply, 1)
    assert sub_type == collab.SYNC_STEP_2
    update_bytes, _ = collab._read_varuint_payload(reply, offset)
    client_b_doc = y_py.YDoc()
    y_py.apply_update(client_b_doc, update_bytes)
    assert str(client_b_doc.get_text("monaco")) == "persisted-by-A"
