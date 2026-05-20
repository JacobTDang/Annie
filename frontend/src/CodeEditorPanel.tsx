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
import { runJS, LANGUAGES, type SupportedLanguage } from "./lib/runJS";
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

function monacoLangFor(id: SupportedLanguage): string {
  return LANGUAGES.find((l) => l.id === id)?.monacoLanguage ?? "python";
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
  // Item #26 — language picker. Defaults to Python so existing UX is unchanged.
  const [language, setLanguage] = useState<SupportedLanguage>("python");

  // Sync editor when a new problem is rendered (starterCode prop changes).
  useEffect(() => {
    setCode(starterCode);
    setResult(null);
    setComparison(null);
  }, [starterCode]);

  const handleRun = useCallback(async () => {
    if (language === "python") {
      if (!pyodide) {
        // First click triggers lazy load; user clicks Run again once ready
        onPyodideLoad();
        return;
      }
      setRunning(true);
      const r = await runPython(pyodide, code);
      setResult(r);

      // Item #27 — if a reference solution was provided, run it now and
      // compare. Failures here are non-fatal: we just skip the diff. Only
      // valid when both reference and user code are Python.
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
      return;
    }

    if (language === "javascript") {
      setRunning(true);
      const r = await runJS(code);
      setResult(r);
      // Reference-diff isn't meaningful across languages; clear any stale one.
      setComparison(null);
      setRunning(false);
      return;
    }

    // C++ and other future languages — currently a "coming soon" placeholder.
  }, [pyodide, code, onPyodideLoad, referenceCode, language]);

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

  const activeLang = LANGUAGES.find((l) => l.id === language);
  const langUnavailable = activeLang && !activeLang.available;

  const buttonLabel =
    langUnavailable ? (activeLang?.unavailableReason ?? "Unavailable") :
    language === "python" && pyodideLoading ? "Loading Python…" :
    language === "python" && !pyodide ? "Load Python" :
    running ? "Running…" :
    "Run";

  const buttonDisabled =
    running ||
    (language === "python" && pyodideLoading) ||
    langUnavailable;

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-2">
        <div
          style={{
            fontSize: 11,
            fontWeight: 500,
            letterSpacing: "0.05em",
            color: C.textFaint,
            textTransform: "uppercase",
          }}
        >
          Try it yourself
        </div>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value as SupportedLanguage)}
          aria-label="Code language"
          style={{
            background: C.bg,
            color: C.text,
            border: `1px solid ${C.borderAlt}`,
            borderRadius: 4,
            fontSize: 11,
            padding: "3px 8px",
            cursor: "pointer",
          }}
        >
          {LANGUAGES.map((l) => (
            <option
              key={l.id}
              value={l.id}
              disabled={!l.available}
              title={l.unavailableReason}
            >
              {l.label}{!l.available ? " (soon)" : ""}
            </option>
          ))}
        </select>
      </div>

      <div
        className="rounded-md overflow-hidden"
        style={{ border: `1px solid ${C.borderAlt}` }}
      >
        <Editor
          height="280px"
          language={monacoLangFor(language)}
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
            tabSize: language === "python" ? 4 : 2,
            insertSpaces: true,
          }}
        />
      </div>

      <div className="mt-3 flex items-center gap-2">
        <motion.button
          onClick={handleRun}
          disabled={buttonDisabled}
          whileHover={buttonDisabled ? {} : { scale: 1.02 }}
          whileTap={buttonDisabled ? {} : { scale: 0.97 }}
          transition={{ duration: 0.15 }}
          className="px-4 py-2 rounded-md flex items-center gap-2"
          style={{
            background: buttonDisabled ? C.borderAlt : C.accent,
            color: "#fff",
            fontFamily: BODY,
            fontSize: 13,
            fontWeight: 500,
            cursor: buttonDisabled ? "not-allowed" : "pointer",
            opacity: buttonDisabled ? 0.7 : 1,
          }}
          title={langUnavailable ? activeLang?.unavailableReason : undefined}
        >
          {(running || (language === "python" && pyodideLoading)) ? (
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
