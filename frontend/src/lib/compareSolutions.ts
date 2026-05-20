// Item #27 — Compare a user's solution output to a reference solution.
//
// Both sides are run via Pyodide in the browser; we compare their stdout
// after light normalization (trailing whitespace, blank lines) so trivial
// formatting differences don't trigger a false negative.

import { runPython, RunResult } from "./runPython";

export interface CompareResult {
  matches: boolean;
  userStdout: string;
  referenceStdout: string;
  referenceError: string | null;
  durationMs: number;
}

export function normalizeOutput(s: string): string {
  // Drop trailing whitespace per line + collapse multiple trailing newlines.
  return s
    .split("\n")
    .map(line => line.replace(/\s+$/g, ""))
    .join("\n")
    .replace(/\n+$/, "");
}

export function outputsMatch(a: string, b: string): boolean {
  return normalizeOutput(a) === normalizeOutput(b);
}

export async function compareSolutions(
  pyodide: any,
  userResult: RunResult,
  referenceCode: string,
): Promise<CompareResult> {
  const start = performance.now();
  let referenceStdout = "";
  let referenceError: string | null = null;

  if (referenceCode && referenceCode.trim()) {
    const ref = await runPython(pyodide, referenceCode);
    referenceStdout = ref.stdout;
    referenceError = ref.error;
  }

  const matches =
    !userResult.error &&
    !referenceError &&
    outputsMatch(userResult.stdout, referenceStdout);

  return {
    matches,
    userStdout: userResult.stdout,
    referenceStdout,
    referenceError,
    durationMs: Math.round(performance.now() - start),
  };
}
