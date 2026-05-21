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
# Persistence — append-only update log
# ─────────────────────────────────────────────────────────────────────────────


def _decode_frames(buf: bytes) -> list[tuple[int, int, bytes]]:
    """Decode a concatenated stream of `[type][sub][len][payload]` frames.
    Returns a list of (msg_type, sub_type, payload)."""
    out: list[tuple[int, int, bytes]] = []
    i = 0
    while i < len(buf):
        msg_type = buf[i]
        sub_type, i = collab._read_varuint(buf, i + 1)
        payload, i = collab._read_varuint_payload(buf, i)
        out.append((msg_type, sub_type, payload))
    return out


def test_append_update_then_replay_roundtrips_in_order():
    """The persistence promise: write updates, read them back in the
    exact same order with byte-identical content."""
    updates = [b"first-update", b"second", b"\x00\x01\x02 binary"]
    for u in updates:
        assert collab.append_update("rt", u) is True
    got = list(collab.replay_updates("rt"))
    assert got == updates


def test_replay_missing_room_yields_nothing():
    assert list(collab.replay_updates("never-existed")) == []


def test_append_update_empty_returns_false():
    """Empty payloads are rejected so a zero-length frame can't poison
    the log."""
    assert collab.append_update("empty", b"") is False
    assert list(collab.replay_updates("empty")) == []


def test_concurrent_appends_dont_corrupt_log():
    """Post-y-py regression: previously the server kept a `_docs[room_id]`
    YDoc that was `unsendable` across threads, so multi-client collab
    panicked. Now the persistence layer is an O_APPEND log — the kernel
    serializes appends. Hammer with 8 threads × 50 writes, assert all
    400 entries decode cleanly + appear in the log."""
    n_threads = 8
    per_thread = 50
    barrier = threading.Barrier(n_threads)

    def hammer(tid: int):
        barrier.wait()
        for i in range(per_thread):
            # Unique payload per (thread, index) so we can detect lost or
            # corrupted writes.
            payload = f"t{tid:02d}-i{i:03d}".encode()
            collab.append_update("hammer", payload)

    threads = [threading.Thread(target=hammer, args=(t,))
               for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    got = list(collab.replay_updates("hammer"))
    assert len(got) == n_threads * per_thread, (
        f"lost writes: got {len(got)} of {n_threads * per_thread}"
    )
    # Every entry decodes cleanly (the assertion above already implies
    # this — if any frame was truncated, replay would have stopped early)
    # and matches the expected payload format.
    for entry in got:
        s = entry.decode()
        assert s.startswith("t") and "-i" in s


def test_snapshot_room_backcompat_replaces_log():
    """The legacy snapshot_room API still works — it overwrites the log
    with a single framed entry. Used by external callers that don't
    track the multi-update model."""
    collab.snapshot_room("snap", b"single-blob")
    assert list(collab.replay_updates("snap")) == [b"single-blob"]
    # Calling again replaces (not appends)
    collab.snapshot_room("snap", b"replacement")
    assert list(collab.replay_updates("snap")) == [b"replacement"]


def test_load_room_backcompat_returns_first_entry():
    """The legacy load_room API returns just the first entry."""
    assert collab.load_room("missing") is None
    collab.append_update("multi", b"alpha")
    collab.append_update("multi", b"beta")
    assert collab.load_room("multi") == b"alpha"


# ─────────────────────────────────────────────────────────────────────────────
# y-protocol message handling
# ─────────────────────────────────────────────────────────────────────────────


def test_sync_update_message_appends_to_log_and_no_reply():
    """SYNC_UPDATE: payload goes into the log, no reply to the sender
    (the broadcast layer handles fan-out separately)."""
    update_payload = b"client-update-bytes"
    msg = bytes([collab.MSG_SYNC, collab.SYNC_UPDATE]) \
          + collab._write_varuint_payload(update_payload)

    reply = collab._handle_sync_message("upd", msg)
    assert reply is None

    logged = list(collab.replay_updates("upd"))
    assert logged == [update_payload]


def test_sync_step_2_message_appends_to_log_and_no_reply():
    """SYNC_STEP_2 (a client's incremental reply to our hypothetical
    Step 1) carries an update — same handling as SYNC_UPDATE."""
    update_payload = b"step-2-update"
    msg = bytes([collab.MSG_SYNC, collab.SYNC_STEP_2]) \
          + collab._write_varuint_payload(update_payload)

    reply = collab._handle_sync_message("s2", msg)
    assert reply is None

    logged = list(collab.replay_updates("s2"))
    assert logged == [update_payload]


def test_sync_step_1_replays_log_to_new_joiner():
    """SYNC_STEP_1: server replies with every logged update framed as
    individual SYNC_STEP_2 messages. The Yjs client decodes the reply as
    a stream of frames and applies each."""
    # Pre-seed three updates
    payloads = [b"update-a", b"update-b", b"update-c"]
    for p in payloads:
        collab.append_update("replay", p)

    # Client sends a Step 1 (the state-vector payload is irrelevant to us —
    # we send everything we know regardless).
    msg = bytes([collab.MSG_SYNC, collab.SYNC_STEP_1]) \
          + collab._write_varuint_payload(b"any-state-vector")

    reply = collab._handle_sync_message("replay", msg)
    assert reply is not None

    frames = _decode_frames(reply)
    assert len(frames) == 3, f"expected 3 Step 2 frames, got {len(frames)}"
    for (msg_type, sub_type, payload), expected in zip(frames, payloads):
        assert msg_type == collab.MSG_SYNC
        assert sub_type == collab.SYNC_STEP_2
        assert payload == expected


def test_sync_step_1_on_empty_room_returns_none():
    """No logged updates = no Step 2 frames to send. None tells the route
    handler not to fan out an empty reply."""
    msg = bytes([collab.MSG_SYNC, collab.SYNC_STEP_1]) \
          + collab._write_varuint_payload(b"")
    assert collab._handle_sync_message("empty-replay", msg) is None


def test_garbage_messages_dont_crash_handler():
    """Malformed inbound bytes from a buggy/hostile client must not blow up
    the relay thread."""
    # Truncated varuint after a valid type byte
    assert collab._handle_sync_message("rA", bytes([collab.MSG_SYNC, 0x80])) is None
    # Empty message
    assert collab._handle_sync_message("rB", b"") is None
    # Non-sync type byte (awareness etc.) — server doesn't reply
    assert collab._handle_sync_message("rC", bytes([collab.MSG_AWARENESS, 0])) is None


def test_full_handshake_persists_across_restart():
    """End-to-end: client A's update gets logged, room empties, client B
    reconnects, server replies with a Step 2 frame carrying A's update."""
    # Client A: connect, send an update, disconnect
    sockA = MagicMock()
    collab._add_socket("e2e", sockA)
    a_update = b"persisted-by-A-update-bytes"
    msg_a = bytes([collab.MSG_SYNC, collab.SYNC_UPDATE]) \
            + collab._write_varuint_payload(a_update)
    collab._handle_sync_message("e2e", msg_a)
    collab._remove_socket("e2e", sockA)

    # Log should hold A's update
    assert list(collab.replay_updates("e2e")) == [a_update]

    # Client B: connect, send Sync Step 1
    sockB = MagicMock()
    collab._add_socket("e2e", sockB)
    step1 = bytes([collab.MSG_SYNC, collab.SYNC_STEP_1]) \
            + collab._write_varuint_payload(b"")
    reply = collab._handle_sync_message("e2e", step1)
    assert reply is not None

    # Reply must contain A's update as a Step 2 frame
    frames = _decode_frames(reply)
    assert len(frames) == 1
    msg_type, sub_type, payload = frames[0]
    assert msg_type == collab.MSG_SYNC
    assert sub_type == collab.SYNC_STEP_2
    assert payload == a_update


def test_no_y_py_dependency_in_module():
    """Regression guard: collab.py must not actually USE y_py — the
    unsendable panic was the whole reason for this refactor. Docstring
    references to y_py are fine (they explain why we removed it)."""
    import re
    import inspect
    src = inspect.getsource(collab)
    # Strip docstring sections (triple-quoted blocks)
    code_only = re.sub(r'"""[\s\S]*?"""', "", src)
    code_only = re.sub(r"'''[\s\S]*?'''", "", code_only)
    # Also strip single-line comments
    code_only = re.sub(r"^\s*#.*$", "", code_only, flags=re.MULTILINE)
    assert "import y_py" not in code_only
    # No attribute access like y_py.YDoc, y_py.apply_update, etc.
    assert not re.search(r"\by_py\.\w+", code_only)
