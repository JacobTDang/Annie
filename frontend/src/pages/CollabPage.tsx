// CollabPage — shared text editing in a room (Item #30).
//
// Lazy-loaded so the Yjs + Monaco bundle doesn't bloat the main chunk.
// Page lifecycle:
//   1. Read room id from the URL hash (or generate one for first visit)
//   2. Open a CollabSession against /api/collab/<room>
//   3. Bind Monaco to the shared Y.Text via MonacoBinding
//   4. On unmount, destroy session (drops the WS + frees the Y.Doc)

import React, { useEffect, useMemo, useRef, useState } from "react";
import Editor, { Monaco } from "@monaco-editor/react";
import type { editor as MonacoEditorNS } from "monaco-editor";
import { Users, Copy, Check } from "lucide-react";

import { C, SANS, BODY } from "../theme";
import {
  openCollabSession,
  isValidRoomId,
  type CollabSession,
} from "../lib/collab";

function _randomRoomId(): string {
  const alpha = "abcdefghijklmnopqrstuvwxyz0123456789";
  let out = "";
  for (let i = 0; i < 10; i++) {
    out += alpha[Math.floor(Math.random() * alpha.length)];
  }
  return out;
}

function _readRoomFromHash(): string {
  if (typeof window === "undefined") return "";
  const m = window.location.hash.match(/^#room=([A-Za-z0-9_-]{1,64})$/);
  return m ? m[1] : "";
}

export const CollabPage: React.FC = () => {
  const [roomId, setRoomId] = useState<string>(() => {
    const existing = _readRoomFromHash();
    return existing && isValidRoomId(existing) ? existing : "";
  });
  const [session, setSession] = useState<CollabSession | null>(null);
  const [status, setStatus] = useState<"disconnected" | "connecting" | "connected">("disconnected");
  const [peers, setPeers] = useState<number>(0);
  const [copied, setCopied] = useState(false);
  const editorRef = useRef<MonacoEditorNS.IStandaloneCodeEditor | null>(null);
  const bindingRef = useRef<any>(null);

  // Reflect room id changes back to the URL so refresh keeps the room
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (roomId) {
      window.location.hash = `#room=${roomId}`;
    }
  }, [roomId]);

  // Open + tear down the collab session whenever the room id changes
  useEffect(() => {
    if (!roomId || !isValidRoomId(roomId)) {
      setSession(null);
      setStatus("disconnected");
      return;
    }
    setStatus("connecting");
    const s = openCollabSession(roomId);
    setSession(s);

    const onStatus = (evt: any) => {
      if (evt.status === "connected") setStatus("connected");
      else if (evt.status === "connecting") setStatus("connecting");
      else setStatus("disconnected");
    };
    s.provider.on("status", onStatus);

    const updateAwareness = () => {
      // y-websocket exposes connected peers via the awareness map. Subtract
      // self (the local awareness state) so the count represents OTHER users.
      const states = s.provider.awareness.getStates();
      setPeers(Math.max(0, states.size - 1));
    };
    s.provider.awareness.on("change", updateAwareness);
    updateAwareness();

    return () => {
      s.provider.off("status", onStatus);
      s.provider.awareness.off("change", updateAwareness);
      bindingRef.current?.destroy?.();
      bindingRef.current = null;
      s.destroy();
    };
  }, [roomId]);

  // Bind Monaco to the shared Y.Text once both the editor and the session
  // are ready. The binding lib is lazy-imported so the Monaco-only chunks
  // don't pull it in.
  const handleMount = (editor: MonacoEditorNS.IStandaloneCodeEditor, _monaco: Monaco) => {
    editorRef.current = editor;
    void _maybeBind();
  };

  const _maybeBind = async () => {
    if (!editorRef.current || !session) return;
    if (bindingRef.current) return;
    // Capture the session reference at call time. If `session` changes
    // while we await the dynamic import (user switches rooms mid-load),
    // the resolved binding would otherwise wire Monaco to the OLD doc.
    // Post-review fix.
    const capturedSession = session;
    const { MonacoBinding } = await import("y-monaco");
    if (capturedSession !== session) return;     // session swapped — abort
    if (bindingRef.current) return;              // re-check after the await
    const yText = capturedSession.doc.getText("monaco");
    bindingRef.current = new MonacoBinding(
      yText,
      editorRef.current.getModel()!,
      new Set([editorRef.current]),
      capturedSession.provider.awareness,
    );
  };

  // Bind also fires when session arrives after the editor mounts
  useEffect(() => { void _maybeBind(); }, [session]);

  const handleCopyLink = async () => {
    if (typeof window === "undefined") return;
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard API blocked — degrade silently */
    }
  };

  const handleNewRoom = () => {
    let candidate = "";
    do { candidate = _randomRoomId(); }
    while (!isValidRoomId(candidate));
    setRoomId(candidate);
  };

  const statusColor = useMemo(() => ({
    connected: "#10b981",
    connecting: "#fbbf24",
    disconnected: "#fca5a5",
  } as const)[status], [status]);

  return (
    <div
      className="h-full overflow-y-auto"
      style={{ background: C.bg, color: C.text, fontFamily: BODY }}
    >
      <div className="max-w-5xl mx-auto px-8 py-10">
        <header className="mb-6">
          <h1
            style={{
              fontFamily: SANS,
              fontSize: 32,
              fontWeight: 600,
              letterSpacing: "-0.02em",
              marginBottom: 8,
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <Users size={26} strokeWidth={1.75} />
            Collab room
          </h1>
          <p style={{ color: C.textMuted, fontSize: 14, lineHeight: 1.6 }}>
            Share the URL — anyone with the link can edit the document live.
            Changes sync via Yjs CRDT so concurrent edits merge cleanly.
          </p>
        </header>

        {!roomId ? (
          <div
            className="p-6 rounded-md text-center"
            style={{
              background: C.surface,
              border: `1px solid ${C.borderAlt}`,
              maxWidth: 480,
              margin: "0 auto",
            }}
          >
            <div style={{ marginBottom: 14, color: C.textMuted, fontSize: 14 }}>
              No room id in the URL. Start a new room?
            </div>
            <button
              onClick={handleNewRoom}
              style={{
                padding: "8px 16px",
                borderRadius: 4,
                border: "none",
                background: C.accent,
                color: "#fff",
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              New room
            </button>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-3">
              <div style={{ fontSize: 12, color: C.textMuted, display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <span
                    aria-hidden
                    style={{
                      width: 8, height: 8, borderRadius: "50%",
                      background: statusColor,
                    }}
                  />
                  {status}
                </span>
                <span>Room: <code style={{ color: C.text }}>{roomId}</code></span>
                <span>{peers} other {peers === 1 ? "user" : "users"}</span>
              </div>
              <button
                onClick={handleCopyLink}
                aria-label="Copy room link"
                style={{
                  padding: "6px 12px",
                  borderRadius: 4,
                  border: `1px solid ${C.borderAlt}`,
                  background: "transparent",
                  color: C.text,
                  fontSize: 12,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                {copied ? <Check size={12} strokeWidth={2} /> : <Copy size={12} strokeWidth={2} />}
                {copied ? "Copied" : "Copy link"}
              </button>
            </div>

            <div
              className="rounded-md overflow-hidden"
              style={{ border: `1px solid ${C.borderAlt}` }}
            >
              <Editor
                height="600px"
                language="markdown"
                defaultValue=""
                onMount={handleMount}
                theme="vs-dark"
                options={{
                  fontSize: 13,
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                  lineNumbers: "on",
                  wordWrap: "on",
                  tabSize: 2,
                  insertSpaces: true,
                }}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default CollabPage;
