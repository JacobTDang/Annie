// Real-time collaboration client (Item #30).
//
// Connects to the backend's `/api/collab/<room>` WebSocket relay and shares
// a Yjs document between every client in the same room. The Yjs binding for
// Monaco lives in `pages/CollabPage.tsx` — this lib just owns the transport
// + room URL building so the page stays render-focused.

import * as Y from "yjs";
import { WebsocketProvider } from "y-websocket";

import { flaskBase } from "./api";

/** Convert flaskBase() (http) into the matching ws/wss URL. */
function _wsBase(): string {
  const http = flaskBase();
  // Vite dev base is `http://localhost:5000`; production may be `https://...`
  if (http.startsWith("https://")) return "wss://" + http.slice(8);
  if (http.startsWith("http://")) return "ws://" + http.slice(7);
  // Relative URLs — fall back to the current origin
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}`;
  }
  return "ws://localhost:5000";
}

export interface CollabSession {
  doc: Y.Doc;
  provider: WebsocketProvider;
  /** Disconnect + free resources. Safe to call multiple times. */
  destroy: () => void;
}

/** True iff the room id is short alphanumeric/hyphenated — mirrors the
 *  backend's `_validate_room_id` so we fail fast on the client. */
export function isValidRoomId(roomId: string): boolean {
  if (!roomId || roomId.length > 64) return false;
  return /^[A-Za-z0-9_-]+$/.test(roomId);
}

/**
 * Open a collab session for ``roomId``. The returned doc + provider can be
 * passed straight to `new MonacoBinding(...)`.
 *
 * The y-websocket protocol prefixes the WS URL with `/<room>` itself — we
 * point it at `${wsBase}/api/collab` and Yjs appends the room.
 */
export function openCollabSession(roomId: string): CollabSession {
  if (!isValidRoomId(roomId)) {
    throw new Error(`invalid room id: ${roomId}`);
  }
  const doc = new Y.Doc();
  const provider = new WebsocketProvider(
    `${_wsBase()}/api/collab`,
    roomId,
    doc,
    { connect: true },
  );

  let destroyed = false;
  const destroy = () => {
    if (destroyed) return;
    destroyed = true;
    try { provider.destroy(); } catch { /* ignore */ }
    try { doc.destroy(); } catch { /* ignore */ }
  };

  return { doc, provider, destroy };
}
