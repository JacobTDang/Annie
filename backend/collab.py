"""
Real-time collaboration (Item #30).

The backend maintains a canonical Y.Doc per room. Connecting clients
exchange the y-websocket sync protocol with the server, which:
  - applies their updates to the server doc (so the server stays current),
  - relays the same update bytes to every other peer in the room (so all
    clients converge),
  - periodically snapshots the doc to disk so a server restart or an empty
    room doesn't lose state.

The y-websocket message format is a single varuint message-type byte followed
by a varuint length + payload. We only need to distinguish:

  type 0 — SYNC   (sync step 1/2 + update)
    sub-type 0 — SyncStep1: client sends its state vector
    sub-type 1 — SyncStep2: response with the missing updates
    sub-type 2 — Update:    incremental updates broadcast both ways

  type 1 — AWARENESS (presence/cursors)
    Pure relay — server doesn't track presence, just forwards.

Anything else: relay verbatim (forward-compat).

Persistence path: `<media>/collab/<room_id>.yjs` — raw Y.encodeStateAsUpdate
bytes. Loaded on first peer join, saved on a debounced timer + when the
room empties.

Public API:
    register_collab_routes(app)
        Mounts GET /api/collab/<room_id> as a WebSocket endpoint.

    snapshot_room(room_id) / load_room(room_id)
        Direct disk helpers (used by tests + the future scheduled-saver).
"""
from __future__ import annotations

import os
import threading
from collections import defaultdict
from typing import Any


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
# Persistence
# ─────────────────────────────────────────────────────────────────────────────

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_COLLAB_DIR = os.path.join(_BACKEND_DIR, "media", "collab")

# Module-level so tests can monkeypatch + writes use a single source of truth.
_collab_dir: str = os.environ.get("LUMEN_COLLAB_DIR", _DEFAULT_COLLAB_DIR)


def _snapshot_path(room_id: str) -> str:
    return os.path.join(_collab_dir, f"{room_id}.yjs")


def snapshot_room(room_id: str, encoded_state: bytes) -> None:
    """Atomically write the encoded Y.Doc state to disk."""
    os.makedirs(_collab_dir, exist_ok=True)
    path = _snapshot_path(room_id)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(encoded_state)
    os.replace(tmp, path)


def load_room(room_id: str) -> bytes | None:
    """Return the on-disk snapshot bytes for ``room_id``, or None if absent."""
    path = _snapshot_path(room_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# In-memory state — rooms hold both the live socket set and the server's Y.Doc
# ─────────────────────────────────────────────────────────────────────────────

_ROOMS_LOCK = threading.Lock()
_rooms: dict[str, set] = defaultdict(set)
_docs: dict[str, Any] = {}            # room_id → y_py.YDoc
_dirty: set[str] = set()              # rooms with unsaved changes


def _validate_room_id(room_id: str) -> bool:
    if not room_id or len(room_id) > 64:
        return False
    return all(c.isalnum() or c in "-_" for c in room_id)


def _get_or_create_doc(room_id: str):
    """Lazily create a server Y.Doc, loading the disk snapshot if present.

    Returns None if y-py isn't installed — the relay still works in that
    case, just without persistence.
    """
    try:
        import y_py  # type: ignore
    except ImportError:
        return None
    with _ROOMS_LOCK:
        doc = _docs.get(room_id)
        if doc is None:
            doc = y_py.YDoc()
            snapshot = load_room(room_id)
            if snapshot:
                try:
                    y_py.apply_update(doc, snapshot)
                except Exception:
                    # Corrupt snapshot — start fresh; next save overwrites it.
                    doc = y_py.YDoc()
            _docs[room_id] = doc
        return doc


def _apply_update_to_server_doc(room_id: str, update_bytes: bytes) -> None:
    """Fold an incoming Yjs update into the server's canonical Y.Doc."""
    doc = _get_or_create_doc(room_id)
    if doc is None or not update_bytes:
        return
    try:
        import y_py  # type: ignore
        y_py.apply_update(doc, update_bytes)
        _dirty.add(room_id)
    except Exception:
        # An invalid update from one client must not poison the room — log
        # and drop. The other clients will eventually re-sync their states.
        pass


def _build_sync_step_2(room_id: str, client_state_vector: bytes) -> bytes:
    """Compose the y-websocket Sync Step 2 reply: every update the client is
    missing relative to its state vector."""
    doc = _get_or_create_doc(room_id)
    if doc is None:
        return b""
    try:
        import y_py  # type: ignore
        diff = y_py.encode_state_as_update(doc, client_state_vector)
    except Exception:
        return b""
    # Frame: [MSG_SYNC] [SYNC_STEP_2] [varuint(len) payload]
    return bytes([MSG_SYNC, SYNC_STEP_2]) + _write_varuint_payload(diff)


def _build_sync_step_1(room_id: str) -> bytes:
    """Compose Sync Step 1: send the server's state vector so the client
    can reply with whatever it's missing. Sent right after a peer connects."""
    doc = _get_or_create_doc(room_id)
    if doc is None:
        return b""
    try:
        import y_py  # type: ignore
        sv = y_py.encode_state_vector(doc)
    except Exception:
        return b""
    return bytes([MSG_SYNC, SYNC_STEP_1]) + _write_varuint_payload(sv)


def _handle_sync_message(room_id: str, msg: bytes) -> bytes | None:
    """Parse an inbound y-protocol message and update the server doc.

    Returns an optional reply payload (raw frame) the server should send back
    to the originating client. For Sync Step 1 we reply with Step 2; for
    Step 2 / Update we just absorb (the broadcast happens separately).
    """
    if len(msg) < 1 or msg[0] != MSG_SYNC:
        return None
    try:
        sub_type, offset = _read_varuint(msg, 1)
    except ValueError:
        return None

    if sub_type == SYNC_STEP_1:
        # Client wants what it's missing → reply with Step 2
        try:
            state_vector, _ = _read_varuint_payload(msg, offset)
        except ValueError:
            return None
        return _build_sync_step_2(room_id, state_vector)

    if sub_type in (SYNC_STEP_2, SYNC_UPDATE):
        # Both shapes carry an `update` payload. Apply to server doc.
        try:
            update_bytes, _ = _read_varuint_payload(msg, offset)
        except ValueError:
            return None
        _apply_update_to_server_doc(room_id, update_bytes)
        return None

    return None


def _maybe_persist(room_id: str, force: bool = False) -> None:
    """Snapshot a dirty room to disk. Cheap when not dirty."""
    if room_id not in _dirty and not force:
        return
    doc = _docs.get(room_id)
    if doc is None:
        return
    try:
        import y_py  # type: ignore
        # Empty state vector → full snapshot
        encoded = y_py.encode_state_as_update(doc)
    except Exception:
        return
    try:
        snapshot_room(room_id, encoded)
        _dirty.discard(room_id)
    except OSError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Socket bookkeeping (unchanged from the relay-only version)
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
        room_empty = not peers
        if room_empty:
            _rooms.pop(room_id, None)
    if room_empty:
        # Final flush so an empty room's last edits survive the eviction.
        _maybe_persist(room_id, force=True)
        # Free the Y.Doc — it'll be reloaded from disk if anyone rejoins.
        # Critical: re-check that the room is STILL empty under the lock. A
        # peer can join between the persist() above (slow disk I/O) and
        # this line; popping the doc out from under them would corrupt
        # their in-flight session. Post-review fix.
        with _ROOMS_LOCK:
            if room_id not in _rooms:
                _docs.pop(room_id, None)
                _dirty.discard(room_id)


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

        # Kick off the sync handshake by sending our Sync Step 1.
        sync_step_1 = _build_sync_step_1(room_id)
        if sync_step_1:
            try:
                ws.send(sync_step_1)
            except Exception:
                _remove_socket(room_id, ws)
                return

        try:
            while True:
                msg = ws.receive()
                if msg is None:
                    break
                # Bytes → maintain server doc + optional reply
                if isinstance(msg, (bytes, bytearray)):
                    reply = _handle_sync_message(room_id, bytes(msg))
                    if reply:
                        try:
                            ws.send(reply)
                        except Exception:
                            break
                # Always relay to other peers (sync messages + awareness)
                _broadcast(room_id, msg, sender=ws)
        except Exception as exc:
            app.logger.debug("[collab] socket error: %s", exc)
        finally:
            _remove_socket(room_id, ws)
