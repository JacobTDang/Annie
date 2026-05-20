// LeetCode-style code editor with browser-side Python execution.
//
// Sits below a rendered visualization on PasteProblemPage. Pre-filled with
// the parser's pseudocode wrapped in a runnable function stub. User edits,
// clicks Run, code executes via Pyodide in the browser tab. Output panel
// shows stdout / stderr / any exception traceback.

import React, { useState, useCallback, useEffect } from "react";
import Editor from "@monaco-editor/react";
import { motion } from "framer-motion";
import { Loader2, Play, RotateCcw, Trash2 } from "lucide-react";
import { runPython, RunResult } from "./lib/runPython";
import { compareSolutions, CompareResult } from "./lib/compareSolutions";
import { C, BODY } from "./theme";

const SUCCESS = "#10b981";
const ERROR_COL = "#ef4444";

interface Props {
  starterCode: string;
  pyodide: any | null;
  pyodideLoading: boolean;
  pyodideError: string | null;
  onPyodideLoad: () => void;
  // Item #27 — when set, the user's stdout is diffed against this reference
  // solution. The reference is run silently after the user's code.
  referenceCode?: string;
}

export const CodeEditorPanel: React.FC<Props> = ({
  starterCode,
  pyodide,
  pyodideLoading,
  pyodideError,
  onPyodideLoad,
  referenceCode,
}) => {
  const [code, setCode] = useState(starterCode);
  const [result, setResult] = useState<RunResult | null>(null);
  const [comparison, setComparison] = useState<CompareResult | null>(null);
  const [running, setRunning] = useState(false);

  // Sync editor when a new problem is rendered (starterCode prop changes).
  useEffect(() => {
    setCode(starterCode);
    setResult(null);
    setComparison(null);
  }, [starterCode]);

  const handleRun = useCallback(async () => {
    if (!pyodide) {
      // First click triggers lazy load; user clicks Run again once ready
      onPyodideLoad();
      return;
    }
    setRunning(true);
    const r = await runPython(pyodide, code);
    setResult(r);

    // Item #27 — if a reference solution was provided, run it now and
    // compare. Failures here are non-fatal: we just skip the diff.
    if (referenceCode && referenceCode.trim() && !r.error) {
      try {
        const cmp = await compareSolutions(pyodide, r, referenceCode);
        setComparison(cmp);
      } catch {
        setComparison(null);
      }
    } else {
      setComparison(null);
    }
    setRunning(false);
  }, [pyodide, code, onPyodideLoad, referenceCode]);

  const handleReset = useCallback(() => {
    setCode(starterCode);
    setResult(null);
    setComparison(null);
  }, [starterCode]);

  const handleClear = useCallback(() => {
    setCode("");
    setResult(null);
    setComparison(null);
  }, []);

  const buttonLabel =
    pyodideLoading ? "Loading Python…" :
    !pyodide ? "Load Python" :
    running ? "Running…" :
    "Run";

  return (
    <div className="mt-8">
      <div
        style={{
          fontSize: 11,
          fontWeight: 500,
          letterSpacing: "0.05em",
          color: C.textFaint,
          textTransform: "uppercase",
          marginBottom: 8,
        }}
      >
        Try it yourself
      </div>

      <div
        className="rounded-md overflow-hidden"
        style={{ border: `1px solid ${C.borderAlt}` }}
      >
        <Editor
          height="280px"
          language="python"
          value={code}
          onChange={(v) => setCode(v ?? "")}
          theme="vs-dark"
          options={{
            fontSize: 13,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            lineNumbers: "on",
            renderLineHighlight: "gutter",
            tabSize: 4,
            insertSpaces: true,
          }}
        />
      </div>

      <div className="mt-3 flex items-center gap-2">
        <motion.button
          onClick={handleRun}
          disabled={running || pyodideLoading}
          whileHover={running || pyodideLoading ? {} : { scale: 1.02 }}
          whileTap={running || pyodideLoading ? {} : { scale: 0.97 }}
          transition={{ duration: 0.15 }}
          className="px-4 py-2 rounded-md flex items-center gap-2"
          style={{
            background: running || pyodideLoading ? C.borderAlt : C.accent,
            color: "#fff",
            fontFamily: BODY,
            fontSize: 13,
            fontWeight: 500,
            cursor: running || pyodideLoading ? "not-allowed" : "pointer",
            opacity: running || pyodideLoading ? 0.7 : 1,
          }}
        >
          {(running || pyodideLoading) ? (
            <Loader2 size={14} className="animate-spin" strokeWidth={2} />
          ) : (
            <Play size={14} strokeWidth={2} />
          )}
          {buttonLabel}
        </motion.button>

        <button
          onClick={handleReset}
          disabled={running}
          className="px-3 py-2 rounded-md flex items-center gap-1.5"
          style={{
            background: "transparent",
            color: C.textMuted,
            border: `1px solid ${C.borderAlt}`,
            fontSize: 12,
            cursor: running ? "not-allowed" : "pointer",
            opacity: running ? 0.5 : 1,
          }}
        >
          <RotateCcw size={12} strokeWidth={2} />
          Reset to starter
        </button>

        <button
          onClick={handleClear}
          disabled={running}
          className="px-3 py-2 rounded-md flex items-center gap-1.5"
          style={{
            background: "transparent",
            color: C.textMuted,
            border: `1px solid ${C.borderAlt}`,
            fontSize: 12,
            cursor: running ? "not-allowed" : "pointer",
            opacity: running ? 0.5 : 1,
          }}
        >
          <Trash2 size={12} strokeWidth={2} />
          Clear
        </button>
      </div>

      {pyodideError && (
        <div
          className="mt-3 p-3 rounded-md"
          style={{
            background: "rgba(239, 68, 68, 0.10)",
            border: "1px solid rgba(239, 68, 68, 0.35)",
            color: "#fca5a5",
            fontSize: 12,
          }}
        >
          <strong style={{ color: "#fecaca" }}>Python failed to load:</strong>{" "}
          {pyodideError}. Check your internet connection and try again.
        </div>
      )}

      {result && (
        <div
          className="mt-3 rounded-md overflow-hidden"
          style={{
            background: "#0d1117",
            border: `1px solid ${C.borderAlt}`,
          }}
        >
          <div
            className="px-3 py-2"
            style={{
              borderBottom: `1px solid ${C.borderAlt}`,
              fontSize: 11,
              color: C.textFaint,
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            <span>
              {result.error ? (
                <span style={{ color: ERROR_COL }}>✗ Error</span>
              ) : (
                <span style={{ color: SUCCESS }}>✓ Ran successfully</span>
              )}
              {comparison && (
                <span
                  style={{
                    marginLeft: 12,
                    color: comparison.matches ? SUCCESS : "#fbbf24",
                  }}
                  title={
                    comparison.matches
                      ? "Output matches the reference solution"
                      : "Output differs from the reference solution"
                  }
                >
                  {comparison.matches
                    ? "✓ Matches reference"
                    : "✗ Differs from reference"}
                </span>
              )}
            </span>
            <span>{result.durationMs}ms</span>
          </div>
          <pre
            className="p-3 m-0 overflow-auto"
            style={{
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
              fontSize: 12,
              color: C.text,
              background: "transparent",
              maxHeight: 200,
            }}
          >
            {result.stdout && (
              <div>
                <span style={{ color: C.textFaint }}>stdout:</span>{"\n"}
                {result.stdout}
              </div>
            )}
            {result.stderr && (
              <div style={{ color: "#fbbf24", marginTop: 6 }}>
                <span style={{ color: C.textFaint }}>stderr:</span>{"\n"}
                {result.stderr}
              </div>
            )}
            {result.error && (
              <div style={{ color: "#fca5a5", marginTop: 6 }}>
                <span style={{ color: C.textFaint }}>traceback:</span>{"\n"}
                {result.error}
              </div>
            )}

            {!result.stdout && !result.stderr && !result.error && (
              <span style={{ color: C.textFaint }}>
                (no output — your code ran but didn't print anything)
              </span>
            )}
          </pre>
        </div>
      )}
    </div>
  );
};
