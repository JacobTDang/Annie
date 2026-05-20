// Item #29 — Lesson playlists.
//
// A playlist is an ordered list of saved-video IDs (matching the SavedVideo
// records in savedVideos.ts). Persisted in localStorage under
// `lumen_playlists`. Order is preserved; duplicates within a playlist are
// allowed (a user might want to drill a tough lesson twice).

const STORAGE_KEY = "lumen_playlists";

export interface Playlist {
  id: string;                // uuid
  name: string;
  videoIds: string[];        // ordered — SavedVideo.id values
  createdAt: number;         // ms
  updatedAt: number;         // ms — bumped on any mutation
}

function _read(): Playlist[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function _write(list: Playlist[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // localStorage full — silently drop. Playlist persistence is best-effort.
  }
}

export const playlists = {
  list(): Playlist[] {
    return _read().sort((a, b) => b.updatedAt - a.updatedAt);
  },

  get(id: string): Playlist | undefined {
    return _read().find((p) => p.id === id);
  },

  create(name: string, videoIds: string[] = []): Playlist {
    const id = (typeof crypto !== "undefined" && crypto.randomUUID)
      ? crypto.randomUUID()
      : `pl-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const now = Date.now();
    const pl: Playlist = {
      id, name: name.trim() || "Untitled",
      videoIds: [...videoIds],
      createdAt: now, updatedAt: now,
    };
    const all = _read();
    all.unshift(pl);
    _write(all);
    return pl;
  },

  remove(id: string): void {
    _write(_read().filter((p) => p.id !== id));
  },

  rename(id: string, name: string): Playlist | undefined {
    const all = _read();
    const idx = all.findIndex((p) => p.id === id);
    if (idx === -1) return undefined;
    all[idx] = { ...all[idx], name: name.trim() || "Untitled", updatedAt: Date.now() };
    _write(all);
    return all[idx];
  },

  /** Append a video to a playlist (no dedupe). */
  appendVideo(playlistId: string, videoId: string): Playlist | undefined {
    const all = _read();
    const idx = all.findIndex((p) => p.id === playlistId);
    if (idx === -1) return undefined;
    all[idx] = {
      ...all[idx],
      videoIds: [...all[idx].videoIds, videoId],
      updatedAt: Date.now(),
    };
    _write(all);
    return all[idx];
  },

  /** Remove a single video from a playlist by index (handles dupes correctly). */
  removeAt(playlistId: string, index: number): Playlist | undefined {
    const all = _read();
    const idx = all.findIndex((p) => p.id === playlistId);
    if (idx === -1) return undefined;
    if (index < 0 || index >= all[idx].videoIds.length) return all[idx];
    const next = [...all[idx].videoIds];
    next.splice(index, 1);
    all[idx] = { ...all[idx], videoIds: next, updatedAt: Date.now() };
    _write(all);
    return all[idx];
  },

  /** Reorder by moving the video at ``from`` to ``to``. */
  reorder(playlistId: string, from: number, to: number): Playlist | undefined {
    const all = _read();
    const idx = all.findIndex((p) => p.id === playlistId);
    if (idx === -1) return undefined;
    const arr = [...all[idx].videoIds];
    if (from < 0 || from >= arr.length || to < 0 || to >= arr.length) return all[idx];
    const [item] = arr.splice(from, 1);
    arr.splice(to, 0, item);
    all[idx] = { ...all[idx], videoIds: arr, updatedAt: Date.now() };
    _write(all);
    return all[idx];
  },
};

/** Return the next video id in playback order, or null at end. */
export function nextInPlaylist(playlist: Playlist,
                                 currentVideoId: string): string | null {
  const i = playlist.videoIds.indexOf(currentVideoId);
  if (i === -1) return playlist.videoIds[0] ?? null;
  return playlist.videoIds[i + 1] ?? null;
}
