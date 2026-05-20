"""
Real-time collaboration WebSocket layer (Item #30).

Brokers Yjs document updates between clients in the same room. Yjs encodes
its sync + awareness messages as binary (CRDT vector clocks + ops), so the
relay is intentionally protocol-agnostic — it just forwards binary frames
from one socket to every other socket in the same room.

This is a minimum-viable y-websocket-compatible relay. Persistence + auth
gating are deliberately deferred to follow-up items (collab-persistence,
collab-auth) so the surface stays auditable.

Public API:
    register_collab_routes(app)
        Attaches GET /api/collab/<room_id> as a WebSocket endpoint.

    _rooms (test surface)
        Module-level dict mapping room_id → set of connected sockets.
        Tests reach in to assert membership without spinning up real clients.

Threading model: simple_websocket is sync per-socket (one thread per
connection). The room map + per-room socket sets are protected by a single
module-level lock. The relay path is O(N) over room members and runs on
every received frame, so we keep the critical section as small as possible:
acquire → snapshot peer list → release → fan-out (outside the lock).
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Iterable


# ─────────────────────────────────────────────────────────────────────────────
# In-memory room registry
# ─────────────────────────────────────────────────────────────────────────────

_ROOMS_LOCK = threading.Lock()
_rooms: dict[str, set] = defaultdict(set)


def _validate_room_id(room_id: str) -> bool:
    """Room ids must be short alphanumeric / hyphenated tokens to keep URLs
    cleanly shareable + prevent slash-injection in any persistence layer."""
    if not room_id or len(room_id) > 64:
        return False
    return all(c.isalnum() or c in "-_" for c in room_id)


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
    """Atomic snapshot of all sockets in ``room_id`` except ``exclude``.

    Returned outside the lock so the fan-out can iterate without blocking
    other rooms.
    """
    with _ROOMS_LOCK:
        peers = _rooms.get(room_id)
        if not peers:
            return []
        return [s for s in peers if s is not exclude]


def room_size(room_id: str) -> int:
    """Number of clients currently connected to ``room_id``. Used by tests
    and by the future presence endpoint."""
    with _ROOMS_LOCK:
        return len(_rooms.get(room_id, ()))


def _broadcast(room_id: str, message, sender) -> int:
    """Forward ``message`` to every peer in ``room_id`` except ``sender``.

    Returns the number of successful sends. Dead sockets (any send error)
    are silently dropped from the room — the per-client thread will also
    notice the disconnect and clean up. Best-effort, idempotent.
    """
    peers = _peers_snapshot(room_id, sender)
    sent = 0
    for peer in peers:
        try:
            peer.send(message)
            sent += 1
        except Exception:
            # Connection died — clean up so we don't keep retrying it.
            _remove_socket(room_id, peer)
    return sent


# ─────────────────────────────────────────────────────────────────────────────
# Flask-Sock route registration
# ─────────────────────────────────────────────────────────────────────────────


def register_collab_routes(app) -> None:
    """Wire the /api/collab/<room_id> WebSocket route onto ``app``.

    Safe to call multiple times: subsequent registrations are no-ops if the
    route is already present.
    """
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
                    # client closed cleanly
                    break
                _broadcast(room_id, msg, sender=ws)
        except Exception as exc:
            # Network hiccup / abrupt close — drop and let cleanup run
            app.logger.debug("[collab] socket error: %s", exc)
        finally:
            _remove_socket(room_id, ws)
