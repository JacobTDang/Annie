// Web Worker entry for the C++ interpreter (runCpp.ts uses this via the
// Vite `?worker` import). Isolating JSCPP from the main thread is what
// lets the timeout actually kill runaway loops — without a worker, an
// `int main() { while(true); }` freezes the entire tab.
//
// Protocol:
//   main → worker:  { code: string, timeoutMs: number }
//   worker → main:  { stdout: string, stderr: string, error: string | null }
//
// On main-thread timeout: `worker.terminate()`. JSCPP can't intercept that,
// so any state it held dies with the worker — perfectly fine since we
// always create a fresh worker per run.

import * as JSCPPModule from "JSCPP";

const JSCPP: any = JSCPPModule;
const runFn: any = JSCPP.run ?? JSCPP.default?.run ?? JSCPP.default;

interface RunRequest {
  code: string;
  timeoutMs: number;
}

self.onmessage = (e: MessageEvent<RunRequest>) => {
  let stdout = "";
  let error: string | null = null;
  try {
    if (typeof runFn !== "function") {
      throw new Error("JSCPP.run export missing — package shape changed");
    }
    runFn(e.data.code, "", {
      stdio: { write: (s: string) => { stdout += s; } },
      debug: false,
      unsigned_overflow: "warn",
      maxTimeout: e.data.timeoutMs,
    });
  } catch (err) {
    error = err instanceof Error ? (err.stack || err.message) : String(err);
  }
  // Post a single completion message; the main thread terminates the
  // worker as soon as it arrives, so this fires at most once.
  (self as any).postMessage({ stdout, stderr: "", error });
};
