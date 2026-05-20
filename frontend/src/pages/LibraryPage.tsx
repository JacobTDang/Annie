// LibraryPage — grid of saved videos with thumbnails, inline player, delete.
//
// Videos are sourced from IndexedDB first (truly offline) and fall back to
// the backend server URL only if the local blob is missing. Pin/unpin to
// the backend is handled by the save/delete flows; the page itself just
// reads the localStorage metadata index.

import React, { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Trash2, Play, X, Wifi, WifiOff, BookmarkX, ThumbsUp, ThumbsDown, Download, FileText } from "lucide-react";
import { C, SANS, BODY, EASE } from "../theme";
import {
  savedVideos,
  type SavedVideo,
  playableUrl,
  removeVideoFromLibrary,
} from "../lib/savedVideos";
import { isDue, dueLabel } from "../lib/srs";
import { downloadVideo, downloadMarkdownLibrary } from "../lib/exportLibrary";
import { resetQuizHistory } from "../lib/quizHistory";
import {
  unpinVideo,
  fetchMySharesIfAuthed,
  type MyShareSummary,
} from "../lib/api";

export const LibraryPage: React.FC = () => {
  const [items, setItems] = useState<SavedVideo[]>(() => savedVideos.list());
  const [playing, setPlaying] = useState<{
    saved: SavedVideo;
    url: string;
    fromOffline: boolean;
    cleanup: () => void;
  } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [cloudShares, setCloudShares] = useState<MyShareSummary[]>([]);

  const refresh = useCallback(() => setItems(savedVideos.list()), []);

  // Cloud shares (Item #17 completion). Empty array when anonymous so the
  // section just doesn't render — no flicker, no error, no auth UI leakage.
  useEffect(() => {
    let cancelled = false;
    fetchMySharesIfAuthed().then((s) => {
      if (!cancelled) setCloudShares(s);
    });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    // Cleanup any in-flight object URL on unmount or video swap
    return () => { playing?.cleanup(); };
  }, [playing]);

  const handlePlay = async (saved: SavedVideo) => {
    if (playing) playing.cleanup();
    try {
      const resolved = await playableUrl(saved);
      setPlaying({ saved, ...resolved });
    } catch (err) {
      console.error("playable URL failed:", err);
    }
  };

  const handleClosePlayer = () => {
    if (playing) playing.cleanup();
    setPlaying(null);
  };

  const handleDownload = async (saved: SavedVideo) => {
    try {
      await downloadVideo(saved);
    } catch (err) {
      console.warn("download failed:", err);
    }
  };

  const handleExportAll = () => {
    downloadMarkdownLibrary(items);
  };

  const handleReview = (saved: SavedVideo, quality: number) => {
    // Item #28 — record SM-2 review; quality 5 = "knew it perfectly",
    // 1 = "couldn't remember". Persists immediately and refreshes the grid.
    savedVideos.recordReview(saved.id, quality);
    refresh();
  };

  const handleDelete = async (saved: SavedVideo) => {
    // Close player if it's currently showing this video
    if (playing?.saved.id === saved.id) handleClosePlayer();
    try {
      await removeVideoFromLibrary(saved.id);
    } catch (err) {
      console.warn("local delete failed:", err);
    }
    // Best-effort backend unpin
    try { await unpinVideo(saved.jobId); } catch { /* ignore */ }
    setConfirmDelete(null);
    refresh();
  };

  return (
    <div
      className="h-full overflow-y-auto"
      style={{ background: C.bg, color: C.text, fontFamily: BODY }}
    >
      <div className="max-w-5xl mx-auto px-8 py-10">
        <header className="mb-8">
          <h1
            style={{
              fontFamily: SANS,
              fontSize: 32,
              fontWeight: 600,
              letterSpacing: "-0.02em",
              marginBottom: 8,
            }}
          >
            Library
          </h1>
          <p style={{ color: C.textMuted, fontSize: 14, lineHeight: 1.6 }}>
            Your saved animations. They live on your device — available offline,
            even if the backend isn't running.
          </p>
          {cloudShares.length > 0 && (
            <div
              className="mt-4 p-3 rounded-md"
              style={{
                background: C.surface,
                border: `1px solid ${C.borderAlt}`,
              }}
            >
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 500,
                  letterSpacing: "0.05em",
                  textTransform: "uppercase",
                  color: C.textFaint,
                  marginBottom: 8,
                }}
              >
                Cloud shares · {cloudShares.length}
              </div>
              <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {cloudShares.map((s) => (
                  <li key={s.code} style={{ fontSize: 12, padding: "4px 0" }}>
                    <a
                      href={`/?share=${encodeURIComponent(s.code)}`}
                      style={{ color: C.text, textDecoration: "none" }}
                    >
                      {s.title}
                    </a>
                    {s.is_public && (
                      <span style={{ marginLeft: 8, color: C.textFaint }}>
                        · public
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {items.length > 0 && (
            <div className="mt-3 flex gap-2 flex-wrap">
              <button
                onClick={handleExportAll}
                aria-label="Export library as markdown"
                title="Download a markdown summary of every saved video"
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
                <FileText size={12} strokeWidth={2} />
                Export library as markdown
              </button>
              <button
                onClick={() => {
                  if (confirm("Reset all quiz history? This wipes per-topic accuracy stats.")) {
                    resetQuizHistory();
                  }
                }}
                aria-label="Reset quiz history"
                title="Wipe per-topic quiz accuracy data — useful when starting over"
                style={{
                  padding: "6px 12px",
                  borderRadius: 4,
                  border: `1px solid ${C.borderAlt}`,
                  background: "transparent",
                  color: C.textMuted,
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                Reset quiz history
              </button>
            </div>
          )}
        </header>

        {items.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4 }}
            className="text-center py-24"
          >
            <BookmarkX
              size={48}
              strokeWidth={1.2}
              color={C.textFaint}
              style={{ margin: "0 auto", marginBottom: 16 }}
            />
            <p style={{
              fontFamily: BODY,
              fontStyle: "italic",
              fontSize: 18,
              color: C.textFaint,
              marginBottom: 8,
            }}>
              Nothing saved yet.
            </p>
            <p style={{ fontSize: 13, color: C.textFaint }}>
              Render a problem and click "Save to Library" to keep it here.
            </p>
          </motion.div>
        ) : (
          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}
          >
            {items.map((it) => (
              <motion.div
                key={it.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, ease: EASE }}
                style={{
                  background: C.surface,
                  border: `1px solid ${C.borderAlt}`,
                  borderRadius: 8,
                  overflow: "hidden",
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                {/* Thumbnail */}
                <button
                  onClick={() => handlePlay(it)}
                  style={{
                    aspectRatio: "16 / 9",
                    background: "#0d1117",
                    border: "none",
                    cursor: "pointer",
                    padding: 0,
                    position: "relative",
                  }}
                >
                  {it.thumbnailDataUrl ? (
                    <img
                      src={it.thumbnailDataUrl}
                      alt={it.title}
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    />
                  ) : (
                    <div
                      style={{
                        height: "100%",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: C.textFaint,
                        fontSize: 13,
                      }}
                    >
                      No preview
                    </div>
                  )}
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      background: "rgba(0,0,0,0.0)",
                      transition: "background 0.18s ease",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "rgba(0,0,0,0.35)";
                      (e.currentTarget.firstChild as HTMLElement)?.style.setProperty("opacity", "1");
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "rgba(0,0,0,0.0)";
                      (e.currentTarget.firstChild as HTMLElement)?.style.setProperty("opacity", "0");
                    }}
                  >
                    <Play
                      size={48}
                      color="#fff"
                      strokeWidth={1.5}
                      fill="rgba(255,255,255,0.2)"
                      style={{ opacity: 0, transition: "opacity 0.18s ease" }}
                    />
                  </div>
                </button>

                {/* Card body */}
                <div style={{ padding: 12, flex: 1, display: "flex", flexDirection: "column" }}>
                  <div style={{
                    fontSize: 14,
                    fontWeight: 500,
                    color: C.text,
                    marginBottom: 4,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}>
                    {it.title || it.scene}
                  </div>
                  <div style={{
                    fontSize: 11,
                    color: C.textFaint,
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 10,
                  }}>
                    <span>{it.scene}</span>
                    <span>·</span>
                    <span>{relativeTime(it.savedAt)}</span>
                    {it.hasOfflineCopy ? (
                      <span title="Available offline" style={{ display: "inline-flex", alignItems: "center", gap: 3, color: C.ok }}>
                        <WifiOff size={11} strokeWidth={2} /> offline
                      </span>
                    ) : (
                      <span title="Server-only" style={{ display: "inline-flex", alignItems: "center", gap: 3, color: C.textFaint }}>
                        <Wifi size={11} strokeWidth={2} /> server
                      </span>
                    )}
                    {isDue(it.srs) && (
                      <span
                        title="Time to review — quiz yourself on this lesson"
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 3,
                          padding: "1px 6px",
                          borderRadius: 3,
                          background: "rgba(251, 191, 36, 0.18)",
                          color: "#fbbf24",
                          fontWeight: 500,
                        }}
                      >
                        Due now
                      </span>
                    )}
                    {!isDue(it.srs) && it.srs && (
                      <span
                        title={`Next review: ${new Date(it.srs.nextReviewAt).toLocaleString()}`}
                        style={{ color: C.textFaint }}
                      >
                        {dueLabel(it.srs)}
                      </span>
                    )}
                  </div>

                  <div style={{ marginTop: "auto", display: "flex", gap: 8 }}>
                    <button
                      onClick={() => handlePlay(it)}
                      style={{
                        flex: 1,
                        padding: "6px 10px",
                        borderRadius: 4,
                        border: `1px solid ${C.borderAlt}`,
                        background: C.bg,
                        color: C.text,
                        fontSize: 12,
                        cursor: "pointer",
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 4,
                      }}
                    >
                      <Play size={12} strokeWidth={2} /> Play
                    </button>
                    {isDue(it.srs) && (
                      <>
                        <button
                          onClick={() => handleReview(it, 1)}
                          aria-label="I forgot"
                          title="Mark as forgotten — schedule a soon review"
                          style={{
                            padding: "6px 10px",
                            borderRadius: 4,
                            border: `1px solid ${C.borderAlt}`,
                            background: C.bg,
                            color: "#fca5a5",
                            fontSize: 12,
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                          }}
                        >
                          <ThumbsDown size={12} strokeWidth={2} />
                        </button>
                        <button
                          onClick={() => handleReview(it, 5)}
                          aria-label="I knew it"
                          title="Knew it — push review further out"
                          style={{
                            padding: "6px 10px",
                            borderRadius: 4,
                            border: `1px solid ${C.borderAlt}`,
                            background: C.bg,
                            color: C.ok,
                            fontSize: 12,
                            cursor: "pointer",
                            display: "inline-flex",
                            alignItems: "center",
                          }}
                        >
                          <ThumbsUp size={12} strokeWidth={2} />
                        </button>
                      </>
                    )}
                    <button
                      onClick={() => handleDownload(it)}
                      aria-label="Download MP4"
                      title="Download as MP4"
                      style={{
                        padding: "6px 10px",
                        borderRadius: 4,
                        border: `1px solid ${C.borderAlt}`,
                        background: C.bg,
                        color: C.text,
                        fontSize: 12,
                        cursor: "pointer",
                        display: "inline-flex",
                        alignItems: "center",
                      }}
                    >
                      <Download size={12} strokeWidth={2} />
                    </button>
                    <button
                      onClick={() => setConfirmDelete(it.id)}
                      aria-label="Delete"
                      style={{
                        padding: "6px 10px",
                        borderRadius: 4,
                        border: `1px solid ${C.borderAlt}`,
                        background: C.bg,
                        color: "#fca5a5",
                        fontSize: 12,
                        cursor: "pointer",
                        display: "inline-flex",
                        alignItems: "center",
                      }}
                    >
                      <Trash2 size={12} strokeWidth={2} />
                    </button>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Inline player modal */}
        <AnimatePresence>
          {playing && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              style={{
                position: "fixed",
                inset: 0,
                background: "rgba(0,0,0,0.85)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: 40,
                zIndex: 50,
              }}
              onClick={handleClosePlayer}
            >
              <motion.div
                initial={{ scale: 0.95 }}
                animate={{ scale: 1 }}
                exit={{ scale: 0.95 }}
                transition={{ duration: 0.2, ease: EASE }}
                style={{
                  maxWidth: 960,
                  width: "100%",
                  background: C.bg,
                  borderRadius: 8,
                  padding: 20,
                  position: "relative",
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  onClick={handleClosePlayer}
                  aria-label="Close"
                  style={{
                    position: "absolute",
                    top: 10,
                    right: 10,
                    background: "transparent",
                    border: "none",
                    color: C.textFaint,
                    cursor: "pointer",
                  }}
                >
                  <X size={20} strokeWidth={2} />
                </button>
                <h3 style={{
                  fontFamily: SANS,
                  fontSize: 18,
                  fontWeight: 600,
                  color: C.text,
                  marginBottom: 4,
                  paddingRight: 32,
                }}>
                  {playing.saved.title || playing.saved.scene}
                </h3>
                <div style={{
                  fontSize: 11,
                  color: C.textFaint,
                  marginBottom: 12,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}>
                  {playing.fromOffline ? (
                    <><WifiOff size={11} strokeWidth={2} /> playing from your device</>
                  ) : (
                    <><Wifi size={11} strokeWidth={2} /> playing from server</>
                  )}
                </div>
                <video
                  src={playing.url}
                  autoPlay
                  controls
                  loop
                  style={{
                    width: "100%",
                    aspectRatio: "16 / 9",
                    borderRadius: 4,
                    background: "#0d1117",
                  }}
                />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Confirm delete modal */}
        <AnimatePresence>
          {confirmDelete && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              style={{
                position: "fixed",
                inset: 0,
                background: "rgba(0,0,0,0.7)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: 60,
              }}
              onClick={() => setConfirmDelete(null)}
            >
              <motion.div
                initial={{ scale: 0.95 }}
                animate={{ scale: 1 }}
                style={{
                  background: C.surface,
                  border: `1px solid ${C.borderAlt}`,
                  borderRadius: 8,
                  padding: 24,
                  maxWidth: 360,
                  textAlign: "center",
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <p style={{ fontSize: 14, marginBottom: 16 }}>
                  Remove this video from your library?
                </p>
                <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
                  <button
                    onClick={() => setConfirmDelete(null)}
                    style={{
                      padding: "8px 16px",
                      borderRadius: 4,
                      border: `1px solid ${C.borderAlt}`,
                      background: C.bg,
                      color: C.text,
                      fontSize: 13,
                      cursor: "pointer",
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      const target = items.find((v) => v.id === confirmDelete);
                      if (target) handleDelete(target);
                    }}
                    style={{
                      padding: "8px 16px",
                      borderRadius: 4,
                      border: "1px solid #ef4444",
                      background: "#ef4444",
                      color: "#fff",
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: "pointer",
                    }}
                  >
                    Delete
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

function relativeTime(ts: number): string {
  const secs = (Date.now() - ts) / 1000;
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return new Date(ts).toLocaleDateString();
}

export default LibraryPage;
