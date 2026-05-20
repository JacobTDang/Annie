// Item #26 follow-up — run C++ in the browser via JSCPP in a Web Worker.
//
// Why a worker: JSCPP's `run()` is synchronous, so without isolating it
// on its own thread, a main-thread `setTimeout` never fires until run()
// returns — meaning an `int main() { while(true); }` freezes the tab.
// Worker + `worker.terminate()` actually kills runaway loops.
//
// We deliberately did NOT go with wasm-clang (the original "coming soon"
// plan): the 30 MB toolchain download is too expensive for a feature
// most users won't touch. JSCPP gets us 90% of LeetCode-style C++ for
// 1% of the bundle cost.

import type { RunResult } from "./runPython";
// Vite's `?worker` query produces a Worker constructor whose source is
// `./runCppWorker.ts`. The chunk is lazy-loaded — non-C++ users don't
// pay the JSCPP cost.
import RunCppWorker from "./runCppWorker?worker";

const DEFAULT_TIMEOUT_MS = 5_000;

/**
 * Interpret the given C++ source in a sandboxed Web Worker. Returns a
 * RunResult shaped like runPython/runJS so the editor panel renders
 * output uniformly.
 *
 * Hard timeout: terminates the worker — JSCPP can't intercept that, so
 * runaway loops are guaranteed to die.
 */
export function runCpp(
  code: string,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<RunResult> {
  return new Promise((resolve) => {
    const start = performance.now();
    const worker = new RunCppWorker();
    let done = false;

    const finish = (out: Omit<RunResult, "durationMs">) => {
      if (done) return;
      done = true;
      worker.terminate();
      resolve({ ...out, durationMs: Math.round(performance.now() - start) });
    };

    worker.onmessage = (e: MessageEvent) => {
      const data = e.data || {};
      finish({
        stdout: typeof data.stdout === "string" ? data.stdout : "",
        stderr: typeof data.stderr === "string" ? data.stderr : "",
        error:
          typeof data.error === "string" || data.error === null
            ? data.error
            : String(data.error),
      });
    };

    worker.onerror = (evt: ErrorEvent) => {
      finish({
        stdout: "",
        stderr: "",
        error: evt.message || "C++ worker error",
      });
    };

    // Hard timeout — actually kills the worker since terminate is sync.
    setTimeout(() => {
      finish({
        stdout: "",
        stderr: "",
        error: `Execution exceeded ${timeoutMs}ms — likely an infinite loop.`,
      });
    }, timeoutMs);

    worker.postMessage({ code, timeoutMs });
  });
}
