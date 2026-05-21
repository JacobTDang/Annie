"""
Real-time collaboration (Item #30).

Each room is an append-only log of opaque Yjs update messages. The server
NEVER parses the Yjs binary format beyond the outer y-websocket frame
(message-type + sub-type + length + payload). When a new peer asks for
the room's state via Sync Step 1, the server replies with every logged
update as a stream of Sync Step 2 frames concatenated into one WebSocket
message. The Yjs client decodes them sequentially and converges.

Why no server-side YDoc:
  `y_py.YDoc` is `unsendable` — PyO3 enforces single-thread ownership.
  Flask-Sock spawns one OS thread per WebSocket connection, so two
  clients in the same room try to mutate the same YDoc from different
  threads → Rust panic. The append-only log sidesteps the issue
  entirely: file I/O has no such thread restriction, and Yjs CRDT
  updates are commutative + idempotent so replay order doesn't matter.

Public API:
    register_collab_routes(app)
        Attaches /api/collab/<room_id> as a WebSocket endpoint.
    append_update(room_id, update_bytes)
        Atomic O_APPEND write. Used by the route handler + tests.
    replay_updates(room_id) -> Iterable[bytes]
        Streams every logged update for a room.
    snapshot_room(room_id, encoded_state) / load_room(room_id)
        Backwards-compatible shims over the log file. New code should
        prefer append_update + replay_updates.

Threading model: per-socket thread does its own log append (filesystem
serializes via O_APPEND). The room registry's single lock protects
membership; broadcasts iterate a snapshot outside the lock.
"""
from __future__ import annotations

import os
import threading
from collections import defaultdict
from typing import Any, Iterable


# ─────────────────────────────────────────────────────────────────────────────
# y-websocket varuint + message-type constants
# ─────────────────────────────────────────────────────────────────────────────

MSG_SYNC      = 0
MSG_AWARENESS = 1

SYNC_STEP_1 = 0
SYNC_STEP_2 = 1
SYNC_UPDATE = 2


def _read_varuint(buf: bytes, offset: int) -> tuple[int, int]:
    """Decode a y-protocol varuint. Returns (value, new_offset)."""
    value = 0
    shift = 0
    while True:
        if offset >= len(buf):
            raise ValueError("truncated varuint")
        b = buf[offset]
        offset += 1
        value |= (b & 0x7F) << shift
        if not (b & 0x80):
            return value, offset
        shift += 7
        if shift > 35:
            raise ValueError("varuint too large")


def _write_varuint(value: int) -> bytes:
    """Encode a non-negative int as y-protocol varuint."""
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _read_varuint_payload(buf: bytes, offset: int) -> tuple[bytes, int]:
    """Read a length-prefixed byte payload; returns (payload, new_offset)."""
    length, offset = _read_varuint(buf, offset)
    end = offset + length
    if end > len(buf):
        raise ValueError("truncated payload")
    return buf[offset:end], end


def _write_varuint_payload(payload: bytes) -> bytes:
    return _write_varuint(len(payload)) + payload


# ─────────────────────────────────────────────────────────────────────────────
# Persistence — per-room append-only update logs
# ─────────────────────────────────────────────────────────────────────────────

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_COLLAB_DIR = os.path.join(_BACKEND_DIR, "media", "collab")

# Module-level so tests can monkeypatch + writes use a single source of truth.
_collab_dir: str = os.environ.get("LUMEN_COLLAB_DIR", _DEFAULT_COLLAB_DIR)

# Serializes log appends. Linux O_APPEND is atomic up to PIPE_BUF, but
# Windows file-write atomicity isn't guaranteed at all — without a Python
# lock, two threads racing on the same fd can interleave their bytes.
_LOG_LOCK = threading.Lock()


def _log_path(room_id: str) -> str:
    return os.path.join(_collab_dir, "logs", f"{room_id}.log")


def append_update(room_id: str, update_bytes: bytes) -> bool:
    """Append one Yjs update to the room's log. Best-effort.

    Each entry is `[varuint(len)] [update bytes]` — same length-prefix
    framing as inside a SYNC_UPDATE message. Atomic from the
    filesystem's perspective: O_APPEND on POSIX writes the whole frame
    or none of it (single write() under the lock for typical update
    sizes; Linux guarantees up to PIPE_BUF, Windows ReplaceFile uses
    transactional move).

    Returns True on success, False if the write failed. Failures get
    logged but never raised — the relay path always continues.
    """
    if not update_bytes:
        return False
    path = _log_path(room_id)
    framed = _write_varuint_payload(update_bytes)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # `_LOG_LOCK` covers the entire open-write-close so concurrent
        # writers can't interleave their frames (Windows lacks atomic
        # O_APPEND semantics). The cost is minimal — appends are small
        # and brief.
        with _LOG_LOCK:
            with open(path, "ab") as fh:
                fh.write(framed)
        return True
    except OSError as exc:
        print(f"[collab] append_update failed for {room_id}: {exc}")
        return False


def replay_updates(room_id: str) -> Iterable[bytes]:
    """Yield every logged update (raw bytes, without the length prefix)
    for ``room_id``. Empty iterator if the log file doesn't exist."""
    path = _log_path(room_id)
    if not os.path.exists(path):
        return
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return
    offset = 0
    while offset < len(data):
        try:
            payload, offset = _read_varuint_payload(data, offset)
        except ValueError:
            # Truncated tail — stop yielding cleanly. The good entries
            # before this point are still valid.
            return
        yield payload


# Back-compat shims for older tests that called snapshot_room/load_room
# directly. New code should use append_update + replay_updates.

def snapshot_room(room_id: str, encoded_state: bytes) -> None:
    """Treat a snapshot as one big update: replace the log with a single
    framed entry. Kept for back-compat with the pre-refactor tests."""
    path = _log_path(room_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    framed = _write_varuint_payload(encoded_state)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(framed)
    os.replace(tmp, path)


def load_room(room_id: str) -> bytes | None:
    """Return the FIRST logged update for back-compat. Real callers
    should iterate replay_updates() to see every entry."""
    for update in replay_updates(room_id):
        return update
    return None


# ─────────────────────────────────────────────────────────────────────────────
# In-memory state — rooms hold the live socket set only (no server YDoc)
# ─────────────────────────────────────────────────────────────────────────────

_ROOMS_LOCK = threading.Lock()
_rooms: dict[str, set] = defaultdict(set)


def _validate_room_id(room_id: str) -> bool:
    if not room_id or len(room_id) > 64:
        return False
    return all(c.isalnum() or c in "-_" for c in room_id)


def _handle_sync_message(room_id: str, msg: bytes) -> bytes | None:
    """Parse an inbound y-protocol message.

    On SYNC_UPDATE / SYNC_STEP_2: append the payload to the room's log.
    Returns None (no reply — broadcast handles fan-out).

    On SYNC_STEP_1: synthesize a chain of SYNC_STEP_2 frames, one per
    logged update, concatenated into a single bytes object. The Yjs
    client reads them sequentially from the same WS message and applies
    each. We use a stream of small frames rather than merging because
    merging Yjs updates requires y-py — which is exactly what we're
    avoiding here.

    Garbage / unknown message types: return None and let the broadcast
    layer relay them verbatim.
    """
    if len(msg) < 1 or msg[0] != MSG_SYNC:
        return None
    try:
        sub_type, offset = _read_varuint(msg, 1)
    except ValueError:
        return None

    if sub_type in (SYNC_STEP_2, SYNC_UPDATE):
        try:
            update_bytes, _ = _read_varuint_payload(msg, offset)
        except ValueError:
            return None
        append_update(room_id, update_bytes)
        return None

    if sub_type == SYNC_STEP_1:
        # Client wants state. Send every logged update as its own STEP_2.
        # Build one big buffer of concatenated frames — the Yjs decoder
        # treats this as a stream.
        parts: list[bytes] = []
        for update in replay_updates(room_id):
            parts.append(
                bytes([MSG_SYNC, SYNC_STEP_2])
                + _write_varuint_payload(update),
            )
        if not parts:
            return None
        return b"".join(parts)

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Socket bookkeeping
# ─────────────────────────────────────────────────────────────────────────────


def _add_socket(room_id: str, sock) -> None:
    with _ROOMS_LOCK:
        _rooms[room_id].add(sock)


def _remove_socket(room_id: str, sock) -> None:
    with _ROOMS_LOCK:
        peers = _rooms.get(room_id)
        if not peers:
            return
        peers.discard(sock)
        if not peers:
            _rooms.pop(room_id, None)


def _peers_snapshot(room_id: str, exclude) -> list:
    with _ROOMS_LOCK:
        peers = _rooms.get(room_id)
        if not peers:
            return []
        return [s for s in peers if s is not exclude]


def room_size(room_id: str) -> int:
    with _ROOMS_LOCK:
        return len(_rooms.get(room_id, ()))


def _broadcast(room_id: str, message, sender) -> int:
    peers = _peers_snapshot(room_id, sender)
    sent = 0
    for peer in peers:
        try:
            peer.send(message)
            sent += 1
        except Exception:
            _remove_socket(room_id, peer)
    return sent


# ─────────────────────────────────────────────────────────────────────────────
# Flask-Sock route
# ─────────────────────────────────────────────────────────────────────────────

def register_collab_routes(app) -> None:
    if any(r.rule == "/api/collab/<room_id>" for r in app.url_map.iter_rules()):
        return
    try:
        from flask_sock import Sock
    except ImportError:
        app.logger.warning(
            "[collab] flask-sock not installed — /api/collab/<room_id> disabled. "
            "`pip install flask-sock` to enable.",
        )
        return

    sock = Sock(app)

    @sock.route("/api/collab/<room_id>")
    def _collab(ws, room_id: str):
        if not _validate_room_id(room_id):
            try:
                ws.close(reason=1008, message="invalid room id")
            except Exception:
                pass
            return

        _add_socket(room_id, ws)

        try:
            while True:
                msg = ws.receive()
                if msg is None:
                    break
                # Parse + log known sync messages. Always relay verbatim.
                if isinstance(msg, (bytes, bytearray)):
                    reply = _handle_sync_message(room_id, bytes(msg))
                    if reply:
                        try:
                            ws.send(reply)
                        except Exception:
                            break
                _broadcast(room_id, msg, sender=ws)
        except Exception as exc:
            app.logger.debug("[collab] socket error: %s", exc)
        finally:
            _remove_socket(room_id, ws)
