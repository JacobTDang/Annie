// Backend API client + live-progress map.
// All HTTP calls to the Flask backend funnel through here so retries,
// timeouts, and base-URL resolution stay in one place.

import { useEffect, useState } from "react";
import type { AnimResult, ParsedProblem } from "../types";
import { getAccessToken, isAuthEnabled } from "./auth";

export const flaskBase = (): string =>
  (import.meta.env.VITE_FLASK_URL as string | undefined) || "http://localhost:5000";

// ─────────────────────────────────────────────────────────────
// Auth header helper (Item #17 completion).
// Attaches Authorization: Bearer <jwt> when Supabase auth is configured AND
// the user is signed in. Anonymous traffic gets the unmodified headers — the
// backend treats both as valid.
// ─────────────────────────────────────────────────────────────
async function _authHeaders(extra: Record<string, string> = {}): Promise<Record<string, string>> {
  const base: Record<string, string> = { ...extra };
  if (!isAuthEnabled()) return base;
  try {
    const token = await getAccessToken();
    if (token) base["Authorization"] = `Bearer ${token}`;
  } catch {
    // Auth probe failed — proceed anonymously, same as before
  }
  return base;
}

// ─────────────────────────────────────────────────────────────
// Live progress: pollJob writes the latest backend-reported progress
// into a module-level Map keyed by topic id, so React components can
// read real numbers via useLiveProgress() during a render.
// ─────────────────────────────────────────────────────────────

const _liveProgress = new Map<string, number>();
const _liveStage = new Map<string, string>();
const _liveListeners = new Set<() => void>();
function _emitLive() { _liveListeners.forEach((cb) => cb()); }

export function setLiveProgress(topicId: string, value: number | null) {
  if (value === null) _liveProgress.delete(topicId);
  else _liveProgress.set(topicId, value);
  _emitLive();
}

export function setLiveStage(topicId: string, stage: string | null) {
  if (stage === null) _liveStage.delete(topicId);
  else _liveStage.set(topicId, stage);
  _emitLive();
}

export function useLiveProgress(topicId: string | null): number | null {
  const [, force] = useState(0);
  useEffect(() => {
    const cb = () => force((n) => n + 1);
    _liveListeners.add(cb);
    return () => { _liveListeners.delete(cb); };
  }, []);
  if (!topicId) return null;
  return _liveProgress.has(topicId) ? _liveProgress.get(topicId)! : null;
}

export function useLiveStage(topicId: string | null): string | null {
  const [, force] = useState(0);
  useEffect(() => {
    const cb = () => force((n) => n + 1);
    _liveListeners.add(cb);
    return () => { _liveListeners.delete(cb); };
  }, []);
  if (!topicId) return null;
  return _liveStage.has(topicId) ? _liveStage.get(topicId)! : null;
}

// ─────────────────────────────────────────────────────────────
// pollJob — the workhorse. Polls /status/<jobId> every 350ms until the
// backend reports done/error or the deadline passes (200s, slightly
// longer than the worker's 180s manim budget).
// ─────────────────────────────────────────────────────────────

export async function pollJob(
  flaskUrl: string,
  jobId: string,
  topicId: string,
): Promise<AnimResult> {
  const deadline = Date.now() + 200_000;
  let failStreak = 0;
  try {
    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 350));
      let statusRes: Response;
      try {
        statusRes = await fetch(`${flaskUrl}/status/${jobId}`);
      } catch {
        // Network error (backend down / offline)
        if (++failStreak >= 5) {
          return { videoUrl: `placeholder://${topicId}`, status: "error",
                   error: "Backend unreachable — is the Flask server running?" };
        }
        continue;
      }
      if (!statusRes.ok) {
        if (++failStreak >= 5) {
          return { videoUrl: `placeholder://${topicId}`, status: "error",
                   error: `Status check failed (HTTP ${statusRes.status})` };
        }
        continue;
      }
      failStreak = 0;
      const job = await statusRes.json();
      if (typeof job.progress === "number") {
        setLiveProgress(topicId, job.progress);
      }
      if (typeof job.stage === "string") {
        setLiveStage(topicId, job.stage);
      }
      if (job.status === "done" && job.url) {
        return { videoUrl: `${flaskUrl}${job.url}`, status: "ready" };
      }
      if (job.status === "error") {
        return {
          videoUrl: `placeholder://${topicId}`,
          status: "error",
          error: job.error || "render failed",
        };
      }
    }
    return {
      videoUrl: `placeholder://${topicId}`,
      status: "error",
      error: "render timed out after 200s",
    };
  } finally {
    setLiveProgress(topicId, null);
    setLiveStage(topicId, null);
  }
}

// ─────────────────────────────────────────────────────────────
// OCR — image / PDF → text via Gemini vision (fallback to mock if the
// backend is unreachable, e.g. GEMINI_API_KEY not configured).
// ─────────────────────────────────────────────────────────────

export async function ocrFile(file: File): Promise<{ text: string }> {
  const flaskUrl = flaskBase();
  const fd = new FormData();
  fd.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${flaskUrl}/api/ocr`, { method: "POST", body: fd });
  } catch {
    // Network error — backend unreachable. Fall back to mock so the UI
    // still works without a running server.
    console.warn("OCR: backend unreachable, returning mock text");
    return {
      text: `[Mock OCR — backend unreachable]\n\nFind the volume of the solid generated by revolving y = x², y = 0, x = 2 about the y-axis.\n\n(Start the Flask server and set GEMINI_API_KEY in backend/.env.)`,
    };
  }
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`OCR failed (HTTP ${res.status}): ${detail.slice(0, 200)}`);
  }
  const data = await res.json();
  if (typeof data.text !== "string") throw new Error("OCR: missing text field in response");
  return { text: data.text };
}

// ─────────────────────────────────────────────────────────────
// Universal parser — classifies math vs DSA on the backend and routes
// to the matching parser. Used by paste page + inline note animate.
// ─────────────────────────────────────────────────────────────

export async function parseProblemV2(rawText: string): Promise<ParsedProblem> {
  const res = await fetch(`${flaskBase()}/api/parse-problem-v2`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rawText }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail || err.error || `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return res.json();
}

// ─────────────────────────────────────────────────────────────
// Fetch a LeetCode problem statement by URL via the backend's GraphQL
// proxy. Lets the user paste a leetcode.com URL instead of prose.
// ─────────────────────────────────────────────────────────────

export async function fetchLeetCodeProblem(
  url: string,
): Promise<{ title: string; rawText: string; sampleInput: string; difficulty: string }> {
  const res = await fetch(`${flaskBase()}/api/fetch-leetcode`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─────────────────────────────────────────────────────────────
// Conversational follow-up parser — sends the prior parsed result so
// the model can apply the user's tweak ("now with [3,1,4]" / "show me
// with X instead" / "explain step 3 slower") without re-pasting.
// ─────────────────────────────────────────────────────────────

export async function parseFollowUp(
  prior: ParsedProblem,
  followUp: string,
): Promise<ParsedProblem> {
  const res = await fetch(`${flaskBase()}/api/parse-followup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prior, followUp }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = err.detail || err.error || `HTTP ${res.status}`;
    throw new Error(detail);
  }
  return res.json();
}

// ─────────────────────────────────────────────────────────────
// Video pinning — protect a rendered video from server-side cleanup
// when the user saves it to their library.
// ─────────────────────────────────────────────────────────────

export async function pinVideo(jobId: string): Promise<{ url: string }> {
  const headers = await _authHeaders({ "Content-Type": "application/json" });
  const res = await fetch(`${flaskBase()}/api/pin`, {
    method: "POST",
    headers,
    body: JSON.stringify({ jobId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `pin failed (HTTP ${res.status})`);
  }
  return res.json();
}

export async function unpinVideo(jobId: string): Promise<void> {
  const headers = await _authHeaders();
  const res = await fetch(`${flaskBase()}/api/pin/${encodeURIComponent(jobId)}`, {
    method: "DELETE",
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `unpin failed (HTTP ${res.status})`);
  }
}

// ─────────────────────────────────────────────────────────────
// Cloud share helpers (Item #17 completion)
// ─────────────────────────────────────────────────────────────

export interface MyShareSummary {
  code: string;
  title: string;
  scene: string | null;
  domain: string | null;
  is_public: boolean;
  created_at: number | null;
}

/** List shares owned by the authenticated user. Returns [] when anonymous /
 *  auth disabled / token rejected so callers can render an empty section. */
export async function fetchMySharesIfAuthed(): Promise<MyShareSummary[]> {
  if (!isAuthEnabled()) return [];
  const headers = await _authHeaders();
  if (!headers["Authorization"]) return [];   // not signed in
  try {
    const res = await fetch(`${flaskBase()}/api/share/mine`, { headers });
    if (!res.ok) return [];
    const body = await res.json();
    return Array.isArray(body?.shares) ? body.shares : [];
  } catch {
    return [];
  }
}

/** POST one quiz answer to the backend. No-op for anonymous traffic — the
 *  frontend already records to localStorage via quizHistory.recordAttempt. */
export async function postQuizAttempt(
  scene: string, correct: boolean, questionIndex: number,
): Promise<void> {
  if (!isAuthEnabled()) return;
  const headers = await _authHeaders({ "Content-Type": "application/json" });
  if (!headers["Authorization"]) return;
  try {
    await fetch(`${flaskBase()}/api/quiz-attempt`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        scene, correct, question_index: questionIndex,
      }),
    });
  } catch {
    // Non-fatal — localStorage copy still records the attempt
  }
}
