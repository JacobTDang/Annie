// PlaylistsPage — list playlists, build them from saved videos, play sequentially.
//
// Item #29. The page is intentionally small: list / create / delete + a
// modal that walks the playlist video-by-video. Auto-advance fires from the
// <video> onEnded handler.

import React, { useState, useCallback, useMemo, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Play, Plus, Trash2, X, SkipForward } from "lucide-react";
import { C, SANS, BODY, EASE } from "../theme";
import {
  playlists,
  type Playlist,
  nextInPlaylist,
} from "../lib/playlists";
import {
  savedVideos,
  type SavedVideo,
  playableUrl,
} from "../lib/savedVideos";

export const PlaylistsPage: React.FC = () => {
  const [items, setItems] = useState<Playlist[]>(() => playlists.list());
  const [allVideos, setAllVideos] = useState<SavedVideo[]>(() => savedVideos.list());
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [selectedVideoIds, setSelectedVideoIds] = useState<string[]>([]);
  const [playing, setPlaying] = useState<{
    playlist: Playlist;
    currentVideoId: string;
    url: string;
    cleanup: () => void;
  } | null>(null);

  const refresh = useCallback(() => {
    setItems(playlists.list());
    setAllVideos(savedVideos.list());
  }, []);

  const videoMap = useMemo(() => {
    const m: Record<string, SavedVideo> = {};
    for (const v of allVideos) m[v.id] = v;
    return m;
  }, [allVideos]);

  const handleCreate = useCallback(() => {
    if (!newName.trim() && selectedVideoIds.length === 0) return;
    playlists.create(newName, selectedVideoIds);
    setNewName("");
    setSelectedVideoIds([]);
    setCreating(false);
    refresh();
  }, [newName, selectedVideoIds, refresh]);

  const handleDelete = useCallback((id: string) => {
    playlists.remove(id);
    refresh();
  }, [refresh]);

  const handlePlay = useCallback(async (pl: Playlist) => {
    if (pl.videoIds.length === 0) return;
    const firstId = pl.videoIds[0];
    const saved = videoMap[firstId];
    if (!saved) return;
    if (playing) playing.cleanup();
    const resolved = await playableUrl(saved);
    setPlaying({
      playlist: pl,
      currentVideoId: firstId,
      url: resolved.url,
      cleanup: resolved.cleanup,
    });
  }, [videoMap, playing]);

  const handleVideoEnded = useCallback(async () => {
    if (!playing) return;
    const nextId = nextInPlaylist(playing.playlist, playing.currentVideoId);
    if (!nextId) {
      playing.cleanup();
      setPlaying(null);
      return;
    }
    const saved = videoMap[nextId];
    if (!saved) {
      playing.cleanup();
      setPlaying(null);
      return;
    }
    playing.cleanup();
    const resolved = await playableUrl(saved);
    setPlaying({
      playlist: playing.playlist,
      currentVideoId: nextId,
      url: resolved.url,
      cleanup: resolved.cleanup,
    });
  }, [playing, videoMap]);

  const handleClosePlayer = useCallback(() => {
    if (playing) playing.cleanup();
    setPlaying(null);
  }, [playing]);

  useEffect(() => {
    return () => { playing?.cleanup(); };
  }, [playing]);

  return (
    <div
      className="h-full overflow-y-auto"
      style={{ background: C.bg, color: C.text, fontFamily: BODY }}
    >
      <div className="max-w-5xl mx-auto px-8 py-10">
        <header className="mb-8 flex items-start justify-between">
          <div>
            <h1
              style={{
                fontFamily: SANS,
                fontSize: 32,
                fontWeight: 600,
                letterSpacing: "-0.02em",
                marginBottom: 8,
              }}
            >
              Playlists
            </h1>
            <p style={{ color: C.textMuted, fontSize: 14, lineHeight: 1.6 }}>
              Group saved animations into sequences. Auto-advance plays them
              back-to-back like a single lesson.
            </p>
          </div>
          <button
            onClick={() => setCreating(true)}
            style={{
              padding: "8px 14px",
              borderRadius: 4,
              border: `1px solid ${C.borderAlt}`,
              background: C.accent,
              color: "#fff",
              fontSize: 13,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <Plus size={14} strokeWidth={2} /> New playlist
          </button>
        </header>

        {items.length === 0 && !creating ? (
          <div style={{ color: C.textFaint, fontSize: 14 }}>
            No playlists yet. Click <em>New playlist</em> to make one from your
            saved videos.
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {items.map((pl) => (
              <div
                key={pl.id}
                className="rounded-md p-4"
                style={{
                  background: C.surface,
                  border: `1px solid ${C.borderAlt}`,
                }}
              >
                <div
                  style={{
                    fontFamily: SANS,
                    fontSize: 16,
                    fontWeight: 600,
                    marginBottom: 4,
                  }}
                >
                  {pl.name}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: C.textFaint,
                    marginBottom: 12,
                  }}
                >
                  {pl.videoIds.length} videos
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handlePlay(pl)}
                    disabled={pl.videoIds.length === 0}
                    style={{
                      flex: 1,
                      padding: "6px 10px",
                      borderRadius: 4,
                      border: `1px solid ${C.borderAlt}`,
                      background: pl.videoIds.length === 0 ? C.surface : C.bg,
                      color: pl.videoIds.length === 0 ? C.textFaint : C.text,
                      fontSize: 12,
                      cursor: pl.videoIds.length === 0 ? "not-allowed" : "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 4,
                    }}
                  >
                    <Play size={12} strokeWidth={2} /> Play all
                  </button>
                  <button
                    onClick={() => handleDelete(pl.id)}
                    aria-label="Delete playlist"
                    style={{
                      padding: "6px 10px",
                      borderRadius: 4,
                      border: `1px solid ${C.borderAlt}`,
                      background: C.bg,
                      color: "#fca5a5",
                      fontSize: 12,
                      cursor: "pointer",
                    }}
                  >
                    <Trash2 size={12} strokeWidth={2} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Create modal */}
        <AnimatePresence>
          {creating && (
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
                padding: 40,
                zIndex: 50,
              }}
              onClick={() => setCreating(false)}
            >
              <motion.div
                initial={{ scale: 0.95 }}
                animate={{ scale: 1 }}
                exit={{ scale: 0.95 }}
                transition={{ duration: 0.2, ease: EASE }}
                style={{
                  width: "100%",
                  maxWidth: 480,
                  background: C.bg,
                  border: `1px solid ${C.borderAlt}`,
                  borderRadius: 8,
                  padding: 24,
                }}
                onClick={(e) => e.stopPropagation()}
              >
                <h2 style={{ fontFamily: SANS, fontSize: 18, marginBottom: 16 }}>
                  New playlist
                </h2>
                <input
                  type="text"
                  placeholder="Playlist name"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  style={{
                    width: "100%",
                    padding: 10,
                    borderRadius: 4,
                    border: `1px solid ${C.borderAlt}`,
                    background: C.surface,
                    color: C.text,
                    fontSize: 14,
                    marginBottom: 12,
                  }}
                />
                <div style={{ fontSize: 11, color: C.textFaint, marginBottom: 6 }}>
                  Select videos
                </div>
                <div
                  style={{
                    maxHeight: 240,
                    overflowY: "auto",
                    border: `1px solid ${C.borderAlt}`,
                    borderRadius: 4,
                    padding: 8,
                    marginBottom: 16,
                  }}
                >
                  {allVideos.length === 0 ? (
                    <div style={{ fontSize: 12, color: C.textFaint }}>
                      Save some videos first.
                    </div>
                  ) : (
                    allVideos.map((v) => {
                      const selected = selectedVideoIds.includes(v.id);
                      return (
                        <label
                          key={v.id}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            padding: "4px 0",
                            fontSize: 12,
                            cursor: "pointer",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={(e) => {
                              setSelectedVideoIds((prev) =>
                                e.target.checked
                                  ? [...prev, v.id]
                                  : prev.filter((id) => id !== v.id)
                              );
                            }}
                          />
                          <span>{v.title}</span>
                        </label>
                      );
                    })
                  )}
                </div>
                <div className="flex gap-2 justify-end">
                  <button
                    onClick={() => setCreating(false)}
                    style={{
                      padding: "6px 14px",
                      borderRadius: 4,
                      border: `1px solid ${C.borderAlt}`,
                      background: "transparent",
                      color: C.text,
                      fontSize: 13,
                      cursor: "pointer",
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreate}
                    style={{
                      padding: "6px 14px",
                      borderRadius: 4,
                      border: "none",
                      background: C.accent,
                      color: "#fff",
                      fontSize: 13,
                      cursor: "pointer",
                    }}
                  >
                    Create
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Playing modal — auto-advances via onEnded */}
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
                zIndex: 60,
              }}
              onClick={handleClosePlayer}
            >
              <motion.div
                initial={{ scale: 0.95 }}
                animate={{ scale: 1 }}
                exit={{ scale: 0.95 }}
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
                    color: C.textMuted,
                    cursor: "pointer",
                  }}
                >
                  <X size={20} strokeWidth={2} />
                </button>
                <div
                  style={{
                    fontFamily: SANS,
                    fontSize: 16,
                    fontWeight: 600,
                    marginBottom: 8,
                  }}
                >
                  {videoMap[playing.currentVideoId]?.title ?? "Now playing"}
                </div>
                <div style={{ fontSize: 11, color: C.textFaint, marginBottom: 8 }}>
                  Playlist: {playing.playlist.name}
                </div>
                <video
                  src={playing.url}
                  autoPlay
                  controls
                  onEnded={handleVideoEnded}
                  style={{ width: "100%", borderRadius: 4, background: "#000" }}
                />
                <div className="flex items-center justify-end mt-3">
                  <button
                    onClick={handleVideoEnded}
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
                    <SkipForward size={12} strokeWidth={2} /> Next
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

export default PlaylistsPage;
