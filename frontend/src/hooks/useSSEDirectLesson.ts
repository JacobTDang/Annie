// React hook around streamDirectLesson — exposes live SSE state to a page.
//
// Pages call `start({ question })` and read `{ stage, narrative, scenesDone,
// jobId, error }`. The hook owns the AbortController so unmounting cancels.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  streamDirectLesson,
  type StreamDirectLessonOptions,
  type SSEStage,
} from "../lib/sseLesson";

export interface SSEDirectLessonState {
  /** Latest stage we've seen — null until the server emits the first event. */
  stage: SSEStage | null;
  narrative: any | null;
  scenesDone: Array<{ index: number; title: string }>;
  jobId: string | null;
  error: string | null;
  running: boolean;
}

const INITIAL: SSEDirectLessonState = {
  stage: null, narrative: null, scenesDone: [],
  jobId: null, error: null, running: false,
};

export function useSSEDirectLesson() {
  const [state, setState] = useState<SSEDirectLessonState>(INITIAL);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const start = useCallback(async (
    opts: Omit<StreamDirectLessonOptions, "signal" | "onEvent">,
  ) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ ...INITIAL, running: true });
    try {
      const result = await streamDirectLesson({
        ...opts,
        signal: controller.signal,
        onEvent: (evt) => {
          setState((prev) => {
            switch (evt.event) {
              case "stage":
                return { ...prev, stage: evt.data as SSEStage };
              case "narrative":
                return { ...prev, narrative: evt.data };
              case "scene_done":
                return { ...prev, scenesDone: [...prev.scenesDone, evt.data] };
              case "job_id":
                return { ...prev, jobId: String(evt.data) };
              case "error":
                return { ...prev, error: evt.data?.error || String(evt.data) };
              default:
                return prev;
            }
          });
        },
      });
      setState((prev) => ({ ...prev, running: false, jobId: result.jobId, error: result.error }));
      return result;
    } catch (err) {
      // Aborted streams don't surface as user-visible errors
      const msg = err instanceof Error ? err.message : String(err);
      if (controller.signal.aborted) {
        setState((prev) => ({ ...prev, running: false }));
        return null;
      }
      setState((prev) => ({ ...prev, running: false, error: msg }));
      return null;
    }
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setState((prev) => ({ ...prev, running: false }));
  }, []);

  return { ...state, start, cancel };
}
