// Saved-video metadata persisted in localStorage.
//
// The actual MP4 bytes live in IndexedDB (see videoStore.ts). This module
// owns the metadata index (titles, ids, thumbnails, server URLs).

import { videoStore } from "./videoStore";
import { SrsState, initialSrsState, scheduleNext } from "./srs";

const STORAGE_KEY = "lumen_saved_videos";

export interface SavedVideo {
  id: string;                  // uuid, used as IndexedDB key too
  jobId: string;               // backend job id (for pin/unpin)
  title: string;
  scene: string;
  domain: "math" | "dsa" | "unknown";
  savedAt: number;             // ms timestamp
  serverUrl: string;           // absolute URL while backend is up
  thumbnailDataUrl?: string;   // first-frame snapshot (PNG data URL)
  hasOfflineCopy: boolean;     // true if also in IndexedDB
  // Item #28 — SM-2 spaced-repetition schedule. Optional for backwards
  // compatibility: older records get treated as "due now" until reviewed once.
  srs?: SrsState;
}

function _read(): SavedVideo[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function _write(items: SavedVideo[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    // localStorage quota — caller catches via savedVideos.add throwing
    throw new Error("localStorage write failed (quota?)");
  }
}

export const savedVideos = {
  list(): SavedVideo[] {
    return _read().sort((a, b) => b.savedAt - a.savedAt);
  },

  get(id: string): SavedVideo | undefined {
    return _read().find((v) => v.id === id);
  },

  add(item: SavedVideo): void {
    const items = _read();
    // Replace if id collision; otherwise prepend
    const existing = items.findIndex((v) => v.id === item.id);
    if (existing >= 0) items[existing] = item;
    else items.unshift(item);
    _write(items);
  },

  remove(id: string): void {
    _write(_read().filter((v) => v.id !== id));
  },

  /** Update offline-copy flag (e.g., after IndexedDB load succeeds/fails). */
  setOfflineFlag(id: string, hasOffline: boolean): void {
    const items = _read();
    const idx = items.findIndex((v) => v.id === id);
    if (idx === -1) return;
    items[idx] = { ...items[idx], hasOfflineCopy: hasOffline };
    _write(items);
  },

  /** Item #28 — record an SM-2 review (quality 0..5) and persist new schedule. */
  recordReview(id: string, quality: number, now: number = Date.now()): SrsState | undefined {
    const items = _read();
    const idx = items.findIndex((v) => v.id === id);
    if (idx === -1) return undefined;
    const prev = items[idx].srs ?? initialSrsState(now);
    const next = scheduleNext(prev, quality, now);
    items[idx] = { ...items[idx], srs: next };
    _write(items);
    return next;
  },
};

/**
 * Download a video by URL, generate a thumbnail from its first frame, and
 * store both the blob (IndexedDB) and metadata (localStorage). Returns the
 * SavedVideo record.
 */
export async function saveVideoToLibrary(
  args: {
    jobId: string;
    title: string;
    scene: string;
    domain: "math" | "dsa" | "unknown";
    serverUrl: string;
  },
): Promise<SavedVideo> {
  // 1. Download the MP4 as a Blob
  const res = await fetch(args.serverUrl);
  if (!res.ok) throw new Error(`failed to download video (HTTP ${res.status})`);
  const blob = await res.blob();

  // 2. Generate a thumbnail from the first frame
  let thumbnail: string | undefined;
  try {
    thumbnail = await generateThumbnail(blob);
  } catch {
    /* non-fatal */
  }

  // 3. Build the metadata record
  const id = crypto.randomUUID();
  const record: SavedVideo = {
    id,
    jobId: args.jobId,
    title: args.title,
    scene: args.scene,
    domain: args.domain,
    savedAt: Date.now(),
    serverUrl: args.serverUrl,
    thumbnailDataUrl: thumbnail,
    hasOfflineCopy: false,
  };

  // 4. Persist blob to IndexedDB
  try {
    await videoStore.put(id, blob);
    record.hasOfflineCopy = true;
  } catch (err) {
    console.warn("IndexedDB put failed — saving without offline copy:", err);
  }

  // 5. Persist metadata to localStorage
  savedVideos.add(record);
  return record;
}

/**
 * Remove a saved video: delete blob from IndexedDB and metadata from
 * localStorage. The caller is responsible for the backend unpin call.
 */
export async function removeVideoFromLibrary(id: string): Promise<void> {
  try {
    await videoStore.delete(id);
  } catch {
    /* non-fatal — proceed to localStorage cleanup */
  }
  savedVideos.remove(id);
}

/**
 * Resolve a playable URL for a saved video. Prefers the IndexedDB blob
 * (offline) and falls back to the backend server URL. Returns an object
 * URL the caller must `URL.revokeObjectURL()` when done.
 */
export async function playableUrl(saved: SavedVideo): Promise<{
  url: string;
  fromOffline: boolean;
  cleanup: () => void;
}> {
  if (saved.hasOfflineCopy) {
    try {
      const blob = await videoStore.get(saved.id);
      if (blob) {
        const url = URL.createObjectURL(blob);
        return { url, fromOffline: true, cleanup: () => URL.revokeObjectURL(url) };
      }
    } catch {
      /* fall through to server */
    }
  }
  return { url: saved.serverUrl, fromOffline: false, cleanup: () => {} };
}

/**
 * Render the first frame of a video blob to a 320×180 data URL.
 * Used for library thumbnails.
 */
async function generateThumbnail(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const video = document.createElement("video");
    video.src = url;
    video.muted = true;
    video.preload = "metadata";
    video.crossOrigin = "anonymous";

    const cleanup = () => URL.revokeObjectURL(url);

    video.onloadeddata = () => {
      try {
        // Seek slightly past 0 so we don't get a black first frame
        video.currentTime = Math.min(0.5, (video.duration || 1) * 0.05);
      } catch {
        // Some browsers don't allow seek without play()
      }
    };
    video.onseeked = () => {
      try {
        const canvas = document.createElement("canvas");
        canvas.width = 320;
        canvas.height = 180;
        const ctx = canvas.getContext("2d");
        if (!ctx) { cleanup(); reject(new Error("no 2d context")); return; }
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL("image/png");
        cleanup();
        resolve(dataUrl);
      } catch (e) {
        cleanup();
        reject(e);
      }
    };
    video.onerror = () => { cleanup(); reject(new Error("video load failed")); };
  });
}
