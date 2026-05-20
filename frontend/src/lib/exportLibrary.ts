// Item #36 — Export saved videos.
//
// MP4: trivial — the MP4 blob lives in IndexedDB (videoStore). We resolve it
// the same way the player does, then trigger a hidden <a download>.
//
// PDF: react-pdf is ~500 KB and overkill for a library summary. Instead we
// emit a markdown report listing each video; users can paste this into Notion
// / Obsidian / convert to PDF themselves. The trade-off favors bundle size
// over click-to-PDF — switch to react-pdf later if the audience demands it.

import { videoStore } from "./videoStore";
import type { SavedVideo } from "./savedVideos";

/** Trigger a hidden <a download> for the given Blob + suggested filename. */
function _saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();
  // Defer revoke + remove so Chrome has a tick to start the download.
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 200);
}

/** Build a filesystem-friendly name from a lesson title. */
export function safeFilename(title: string, ext: string): string {
  const cleaned = (title || "lumen-video")
    .toLowerCase()
    .replace(/[^a-z0-9-_]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
  return `${cleaned || "lumen"}.${ext}`;
}

/**
 * Download a saved video as an MP4. Prefers the IndexedDB blob (true offline);
 * falls back to fetching the server URL if the local copy is gone.
 */
export async function downloadVideo(saved: SavedVideo): Promise<void> {
  let blob: Blob | undefined;
  if (saved.hasOfflineCopy) {
    try { blob = await videoStore.get(saved.id); }
    catch { /* fall through to server */ }
  }
  if (!blob) {
    const res = await fetch(saved.serverUrl);
    if (!res.ok) throw new Error(`download failed (HTTP ${res.status})`);
    blob = await res.blob();
  }
  _saveBlob(blob, safeFilename(saved.title, "mp4"));
}

/** Format a UNIX-ms timestamp as YYYY-MM-DD for the markdown report. */
function _isoDate(ms: number): string {
  if (!ms) return "—";
  return new Date(ms).toISOString().slice(0, 10);
}

/**
 * Build a Markdown report of the user's library. Pure function — used by
 * tests and by downloadMarkdownLibrary().
 */
export function exportLibraryAsMarkdown(items: SavedVideo[],
                                          now: number = Date.now()): string {
  const lines: string[] = [];
  lines.push("# Lumen — Saved Library");
  lines.push("");
  lines.push(`Generated: ${_isoDate(now)}`);
  lines.push(`Total videos: ${items.length}`);
  lines.push("");
  if (items.length === 0) {
    lines.push("_(library is empty — save a video first)_");
    return lines.join("\n");
  }

  // Sort newest-first so the report mirrors the page
  const sorted = [...items].sort((a, b) => b.savedAt - a.savedAt);

  for (const v of sorted) {
    lines.push(`## ${v.title || "(untitled)"}`);
    lines.push("");
    lines.push(`- **Scene:** \`${v.scene}\``);
    lines.push(`- **Domain:** ${v.domain}`);
    lines.push(`- **Saved:** ${_isoDate(v.savedAt)}`);
    lines.push(`- **Offline copy:** ${v.hasOfflineCopy ? "yes" : "no"}`);
    if (v.srs) {
      lines.push(`- **SRS reps:** ${v.srs.repetitions} ` +
                  `(ease ${v.srs.easeFactor.toFixed(2)}, ` +
                  `next due ${_isoDate(v.srs.nextReviewAt)})`);
    }
    lines.push(`- **Server URL:** ${v.serverUrl}`);
    lines.push("");
  }
  return lines.join("\n");
}

/** Download the library report as `lumen-library.md`. */
export function downloadMarkdownLibrary(items: SavedVideo[]): void {
  const md = exportLibraryAsMarkdown(items);
  const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
  _saveBlob(blob, "lumen-library.md");
}
