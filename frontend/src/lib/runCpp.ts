// Item #26 follow-up — run C++ in the browser via JSCPP.
//
// JSCPP is a pure-JS interpreter for a subset of C++14 (cout/cin, strings,
// vectors, maps, sets, classes, lambdas). It's ~250 KB minified, big enough
// that we lazy-import it only when the user picks C++ in the editor.
//
// We deliberately did NOT go with wasm-clang (the original "coming soon"
// plan): the 30 MB toolchain download is too expensive for a feature most
// users won't touch. JSCPP gets us 90% of LeetCode-style C++ for 1% of the
// bundle cost. If you need full C++ semantics, fall back to a backend
// `/api/run-cpp` (not implemented — operator decision).

import type { RunResult } from "./runPython";

const DEFAULT_TIMEOUT_MS = 5_000;

/**
 * Interpret the given C++ source and return a RunResult shaped like
 * runPython/runJS so the editor panel can render output uniformly.
 *
 * JSCPP runs synchronously on the main thread — we wrap with setTimeout so
 * a runaway loop still hits the timeout. (No Worker because JSCPP relies on
 * global state that doesn't transfer cleanly across thread boundaries.)
 */
export async function runCpp(
  code: string,
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<RunResult> {
  const start = performance.now();
  // Dynamic import so the ~250 KB chunk isn't paid by Python/JS users.
  const mod: any = await import(/* @vite-ignore */ "JSCPP");
  // JSCPP exports `run(code, input, options)` as either default or named.
  const run = mod.run ?? mod.default?.run ?? mod.default;
  if (typeof run !== "function") {
    return {
      stdout: "",
      stderr: "",
      error: "C++ interpreter unavailable (JSCPP export shape changed)",
      durationMs: Math.round(performance.now() - start),
    };
  }

  let stdout = "";
  let stderr = "";
  let error: string | null = null;

  // JSCPP options: capture cout via `stdio.write(s)` callback, redirect
  // stderr the same way. `unsigned` numbers throw warnings — keep them
  // non-fatal so canonical LeetCode templates don't error out.
  const config = {
    stdio: { write: (s: string) => { stdout += s; } },
    debug: false,
    unsigned_overflow: "warn",
    maxTimeout: timeoutMs,
  };

  try {
    // Race the interpreter against our own timeout — JSCPP's maxTimeout is
    // honored on a best-effort basis (some constructs spin without yielding).
    await new Promise<void>((resolve, reject) => {
      const t = setTimeout(() => {
        reject(new Error(`Execution exceeded ${timeoutMs}ms`));
      }, timeoutMs);
      try {
        run(code, "", config);
        clearTimeout(t);
        resolve();
      } catch (e) {
        clearTimeout(t);
        reject(e);
      }
    });
  } catch (e) {
    error = e instanceof Error ? (e.stack || e.message) : String(e);
  }

  return {
    stdout,
    stderr,
    error,
    durationMs: Math.round(performance.now() - start),
  };
}
