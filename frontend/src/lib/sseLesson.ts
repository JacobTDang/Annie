// SSE consumer for /api/direct-lesson-stream (Item #11 completion).
//
// Wraps the EventSource-style protocol the backend emits so callers can
// react to staged progress (planning_narrative → building_scenes → queued)
// instead of polling /status. The backend uses POST + chunked text/event-
// stream rather than native EventSource (which is GET-only), so this uses
// fetch + a streaming reader.
//
// Event shape (text/event-stream):
//   event: stage      data: planning_narrative
//   event: narrative  data: <NarrativePlan JSON>
//   event: stage      data: building_scenes
//   event: scene_done data: {"index": N, "title": "..."}    (one per scene)
//   event: stage      data: queued
//   event: job_id     data: <lesson_id>
//   event: done       data: {}
//   event: error      data: {"error": "..."}
//
// The frontend caller still needs to poll /status/<job_id> for the actual
// render — the SSE only covers the agent-planning phase.

import { flaskBase } from "./api";

export type SSEStage =
  | "planning_narrative"
  | "building_scenes"
  | "queued"
  | "done"
  | "error";

export interface SSEEvent {
  event: string;
  /** Parsed payload — JSON.parse'd when possible, else the raw string. */
  data: any;
}

export interface StreamDirectLessonOptions {
  question: string;
  style?: string;
  target_minutes?: number;
  difficulty_hint?: string;
  /** Abort signal — closes the stream when triggered. */
  signal?: AbortSignal;
  /** Called for every parsed event (low-level). */
  onEvent?: (evt: SSEEvent) => void;
}

export interface StreamDirectLessonResult {
  jobId: string | null;
  narrative: any | null;
  scenesDone: Array<{ index: number; title: string }>;
  error: string | null;
}

/**
 * Stream a Lesson Director run end-to-end. Resolves once the server emits
 * either `done` or `error`. Callers attach to ``onEvent`` for live updates.
 *
 * Throws on network failure / non-2xx HTTP status. Recoverable errors
 * (server-side agent failures) resolve with ``error`` set on the result.
 */
export async function streamDirectLesson(
  opts: StreamDirectLessonOptions,
): Promise<StreamDirectLessonResult> {
  const body: Record<string, any> = { question: opts.question };
  if (opts.style) body.style = opts.style;
  if (opts.target_minutes !== undefined) body.target_minutes = opts.target_minutes;
  if (opts.difficulty_hint) body.difficulty_hint = opts.difficulty_hint;

  const res = await fetch(`${flaskBase()}/api/direct-lesson-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: opts.signal,
  });
  if (!res.ok) {
    throw new Error(`SSE handshake failed: HTTP ${res.status}`);
  }
  if (!res.body) {
    throw new Error("SSE response has no body");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  const result: StreamDirectLessonResult = {
    jobId: null, narrative: null, scenesDone: [], error: null,
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line ("\n\n")
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const evt = _parseFrame(frame);
      if (!evt) continue;

      opts.onEvent?.(evt);

      // Update the aggregate result
      switch (evt.event) {
        case "narrative":  result.narrative = evt.data; break;
        case "scene_done": result.scenesDone.push(evt.data); break;
        case "job_id":     result.jobId = String(evt.data); break;
        case "error":      result.error = evt.data?.error || String(evt.data); break;
        case "done":       return result;
      }
    }
  }
  return result;
}

/** Parse a single SSE frame (multi-line "event:" / "data:" pairs). */
export function _parseFrame(frame: string): SSEEvent | null {
  let event = "message";
  let dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (dataLines.length === 0) return null;
  const dataStr = dataLines.join("\n");
  let data: any;
  try {
    data = JSON.parse(dataStr);
  } catch {
    data = dataStr;
  }
  return { event, data };
}
