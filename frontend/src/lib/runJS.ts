// Item #26 — Run user JavaScript in a sandboxed Web Worker.
//
// Workers run in a separate global scope with no access to the DOM, parent
// window, or our app state. Output is captured via a postMessage protocol so
// the host page can stream stdout/stderr exactly like Pyodide's RunResult.
//
// Worker code is injected as a Blob URL so the user code stays in-page (no
// network round-trip). Hard timeout cancels runaway loops via .terminate().

import type { RunResult } from "./runPython";

const DEFAULT_TIMEOUT_MS = 5_000;

function _workerSource(): string {
  // The worker captures console.{log,error,warn}, evals the user code, and
  // posts back {stdout, stderr, error} once done.
  // Newlines after each captured line so multi-print outputs render right.
  return `
    const stdout = [];
    const stderr = [];
    function fmt(args) {
      return args.map(a => {
        try { return typeof a === "string" ? a : JSON.stringify(a); }
        catch { return String(a); }
      }).join(" ");
    }
    self.console = {
      log:   (...args) => stdout.push(fmt(args)),
      info:  (...args) => stdout.push(fmt(args)),
      warn:  (...args) => stderr.push(fmt(args)),
      error: (...args) => stderr.push(fmt(args)),
      debug: (...args) => stdout.push(fmt(args)),
    };
    self.addEventListener("message", async (e) => {
      const code = e.data?.code ?? "";
      let error = null;
      try {
        // Wrap in an async IIFE so the user can use await at top level
        const fn = new Function(
          "return (async () => { " + code + "\\n })();"
        );
        await fn();
      } catch (err) {
        error = err instanceof Error ? (err.stack || err.message) : String(err);
      }
      self.postMessage({
        stdout: stdout.join("\\n"),
        stderr: stderr.join("\\n"),
        error,
      });
    });
  `;
}

/**
 * Execute the given JavaScript source in a sandboxed Web Worker and return a
 * RunResult shaped identically to runPython() so the panel can render it
 * uniformly.
 */
export function runJS(code: string,
                       timeoutMs: number = DEFAULT_TIMEOUT_MS): Promise<RunResult> {
  return new Promise((resolve) => {
    const start = performance.now();
    const blob = new Blob([_workerSource()], { type: "application/javascript" });
    const url = URL.createObjectURL(blob);
    const worker = new Worker(url);

    let done = false;
    const finish = (out: Omit<RunResult, "durationMs">) => {
      if (done) return;
      done = true;
      worker.terminate();
      URL.revokeObjectURL(url);
      resolve({ ...out, durationMs: Math.round(performance.now() - start) });
    };

    worker.onmessage = (e) => {
      const data = e.data || {};
      finish({
        stdout: typeof data.stdout === "string" ? data.stdout : "",
        stderr: typeof data.stderr === "string" ? data.stderr : "",
        error: typeof data.error === "string" || data.error === null
          ? data.error
          : String(data.error),
      });
    };

    worker.onerror = (evt) => {
      finish({
        stdout: "",
        stderr: "",
        error: evt.message || "worker error",
      });
    };

    // Hard timeout for runaway loops
    setTimeout(() => {
      finish({
        stdout: "",
        stderr: "",
        error: `Execution exceeded ${timeoutMs}ms — likely an infinite loop.`,
      });
    }, timeoutMs);

    worker.postMessage({ code });
  });
}

export type SupportedLanguage = "python" | "javascript" | "cpp";

/** Display labels + "coming soon" gating for the dropdown. */
export const LANGUAGES: Array<{
  id: SupportedLanguage;
  label: string;
  monacoLanguage: string;
  available: boolean;
  unavailableReason?: string;
}> = [
  { id: "python",     label: "Python",     monacoLanguage: "python",     available: true },
  { id: "javascript", label: "JavaScript", monacoLanguage: "javascript", available: true },
  // C++ runs via JSCPP — interprets a subset of C++14 (cout/cin, vectors,
  // strings, maps, classes, lambdas). Lazy-loaded so non-C++ users don't
  // pay the ~250 KB cost. Not a full toolchain — file IO, raw pointers
  // beyond simple use, and some STL corners aren't supported.
  { id: "cpp",        label: "C++",        monacoLanguage: "cpp",        available: true },
];
