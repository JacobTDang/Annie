// DP Practice — one-click starters for the six DP scene types.
//
// Each card knows its scene + params and posts directly to
// /api/render-lesson. Status polls inline; the video player appears in
// the same page so the user doesn't lose context. SRS-aware badges
// pull from quizHistory to nudge the user toward weak topics.

import React, { useCallback, useMemo, useState } from "react";
import { Brain, Code, Loader2, Play, X } from "lucide-react";
import { C, SANS, BODY } from "../theme";
import { flaskBase, pollJob } from "../lib/api";
import { difficultyHintFor } from "../lib/quizHistory";
import {
  DP_PRACTICE_PROBLEMS,
  type DPPattern,
  type DPPracticeProblem,
} from "../data/dpPracticeProblems";

const PATTERN_LABELS: Record<DPPattern, string> = {
  knapsack_01: "Knapsack 0/1",
  lcs: "LCS",
  edit_distance: "Edit Distance",
  coin_change_2d: "Coin Change",
  lis: "LIS",
  dp_progression: "DP Progression",
};

const PATTERN_COLORS: Record<DPPattern, string> = {
  knapsack_01: "#3b82f6",
  lcs: "#10b981",
  edit_distance: "#f59e0b",
  coin_change_2d: "#8b5cf6",
  lis: "#06b6d4",
  dp_progression: "#ec4899",
};


type RenderState =
  | { kind: "idle" }
  | { kind: "rendering"; problem: DPPracticeProblem; jobId: string }
  | { kind: "ready"; problem: DPPracticeProblem; videoUrl: string }
  | { kind: "error"; message: string };


export const DPPracticePage: React.FC = () => {
  const [filterPattern, setFilterPattern] = useState<DPPattern | null>(null);
  const [renderState, setRenderState] = useState<RenderState>({ kind: "idle" });
  const [solutionFor, setSolutionFor] = useState<DPPracticeProblem | null>(null);

  const filtered = useMemo(() => {
    if (!filterPattern) return DP_PRACTICE_PROBLEMS;
    return DP_PRACTICE_PROBLEMS.filter((p) => p.pattern === filterPattern);
  }, [filterPattern]);

  const patterns = useMemo(() => {
    const set = new Set<DPPattern>();
    for (const p of DP_PRACTICE_PROBLEMS) set.add(p.pattern);
    return Array.from(set);
  }, []);

  const handleRender = useCallback(async (problem: DPPracticeProblem) => {
    try {
      const res = await fetch(`${flaskBase()}/api/render-lesson`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ steps: problem.steps }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setRenderState({
          kind: "error",
          message: err.error || `render submit failed (${res.status})`,
        });
        return;
      }
      const { job_id } = await res.json();
      setRenderState({ kind: "rendering", problem, jobId: job_id });
      // Poll until done or error. pollJob takes (flaskUrl, jobId, topicId).
      const result = await pollJob(flaskBase(), job_id, problem.topicId);
      if (result.status === "ready" && result.videoUrl &&
          !result.videoUrl.startsWith("placeholder://")) {
        setRenderState({ kind: "ready", problem, videoUrl: result.videoUrl });
      } else {
        setRenderState({
          kind: "error",
          message: result.error || "render did not complete",
        });
      }
    } catch (err) {
      setRenderState({
        kind: "error",
        message: err instanceof Error ? err.message : String(err),
      });
    }
  }, []);

  return (
    <div
      className="h-full overflow-y-auto"
      style={{ background: C.bg, color: C.text, fontFamily: BODY }}
    >
      <div className="max-w-6xl mx-auto px-8 py-10">
        <header className="mb-8">
          <h1
            style={{
              fontFamily: SANS,
              fontSize: 32,
              fontWeight: 600,
              letterSpacing: "-0.02em",
              marginBottom: 8,
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <Brain size={26} strokeWidth={1.75} />
            DP Practice
          </h1>
          <p style={{ color: C.textMuted, fontSize: 14, lineHeight: 1.6 }}>
            One-click drills across the canonical DP patterns. Each card animates the
            full DP table — use the step controls on the result to walk through cell
            by cell.
          </p>
        </header>

        {/* Pattern chips */}
        <div className="flex flex-wrap gap-2 mb-6">
          <button
            onClick={() => setFilterPattern(null)}
            className="px-3 py-1.5 rounded-md"
            style={{
              fontSize: 12,
              color: filterPattern === null ? "#fff" : C.textMuted,
              background: filterPattern === null ? C.accent : "transparent",
              border: `1px solid ${filterPattern === null ? C.accent : C.borderAlt}`,
              cursor: "pointer",
            }}
          >
            All
          </button>
          {patterns.map((p) => (
            <button
              key={p}
              onClick={() => setFilterPattern(p)}
              className="px-3 py-1.5 rounded-md"
              style={{
                fontSize: 12,
                color: filterPattern === p ? "#fff" : C.textMuted,
                background: filterPattern === p ? PATTERN_COLORS[p] : "transparent",
                border: `1px solid ${filterPattern === p ? PATTERN_COLORS[p] : C.borderAlt}`,
                cursor: "pointer",
              }}
            >
              {PATTERN_LABELS[p]}
            </button>
          ))}
        </div>

        {/* Card grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {filtered.map((problem, idx) => {
            const hint = difficultyHintFor(problem.topicId);
            const badge = hint === "extend"
              ? { label: "Practice more", color: "#f59e0b" }
              : hint === "skip"
                ? { label: "Mastered", color: "#10b981" }
                : null;

            return (
              <div
                key={`${problem.pattern}-${idx}`}
                className="p-4 rounded-md"
                style={{
                  background: C.surface,
                  border: `1px solid ${C.borderAlt}`,
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                {/* Pattern badge + SRS chip */}
                <div className="flex items-center justify-between mb-2">
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 600,
                      letterSpacing: "0.05em",
                      textTransform: "uppercase",
                      color: PATTERN_COLORS[problem.pattern],
                    }}
                  >
                    {PATTERN_LABELS[problem.pattern]}
                  </span>
                  {badge && (
                    <span
                      style={{
                        fontSize: 10,
                        padding: "2px 8px",
                        borderRadius: 3,
                        background: `${badge.color}33`,
                        color: badge.color,
                      }}
                    >
                      {badge.label}
                    </span>
                  )}
                </div>

                <div
                  style={{
                    fontFamily: SANS,
                    fontSize: 14,
                    fontWeight: 600,
                    marginBottom: 6,
                  }}
                >
                  {problem.title}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: C.textMuted,
                    lineHeight: 1.45,
                    marginBottom: 12,
                    flex: 1,
                  }}
                >
                  {problem.description}
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => handleRender(problem)}
                    disabled={renderState.kind === "rendering"}
                    style={{
                      flex: 1,
                      padding: "6px 10px",
                      borderRadius: 4,
                      border: `1px solid ${C.borderAlt}`,
                      background: renderState.kind === "rendering" ? C.surface : C.bg,
                      color: C.text,
                      fontSize: 12,
                      cursor: renderState.kind === "rendering" ? "not-allowed" : "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 4,
                    }}
                  >
                    <Play size={12} strokeWidth={2} /> Render
                  </button>
                  <button
                    onClick={() => setSolutionFor(problem)}
                    aria-label="Show solution code"
                    style={{
                      padding: "6px 10px",
                      borderRadius: 4,
                      border: `1px solid ${C.borderAlt}`,
                      background: C.bg,
                      color: C.textMuted,
                      fontSize: 12,
                      cursor: "pointer",
                    }}
                  >
                    <Code size={12} strokeWidth={2} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Result area */}
        {renderState.kind === "rendering" && (
          <div
            className="p-4 rounded-md mb-4"
            style={{
              background: C.surface,
              border: `1px solid ${C.borderAlt}`,
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <Loader2 size={18} className="animate-spin" strokeWidth={2} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 500 }}>
                Rendering {renderState.problem.title}…
              </div>
              <div style={{ fontSize: 11, color: C.textFaint, marginTop: 2 }}>
                Job {renderState.jobId.slice(0, 8)} — typically 10-30 seconds.
              </div>
            </div>
          </div>
        )}

        {renderState.kind === "ready" && (
          <div
            className="p-4 rounded-md mb-4"
            style={{ background: C.surface, border: `1px solid ${C.borderAlt}` }}
          >
            <div className="flex items-center justify-between mb-3">
              <div style={{ fontFamily: SANS, fontSize: 14, fontWeight: 600 }}>
                {renderState.problem.title}
              </div>
              <button
                onClick={() => setRenderState({ kind: "idle" })}
                aria-label="Close player"
                style={{
                  background: "transparent",
                  border: "none",
                  color: C.textMuted,
                  cursor: "pointer",
                }}
              >
                <X size={16} strokeWidth={2} />
              </button>
            </div>
            <video
              src={renderState.videoUrl}
              controls
              autoPlay
              loop
              style={{ width: "100%", borderRadius: 4, background: "#000" }}
            />
          </div>
        )}

        {renderState.kind === "error" && (
          <div
            className="p-3 rounded-md mb-4"
            style={{
              background: "rgba(239, 68, 68, 0.10)",
              border: "1px solid rgba(239, 68, 68, 0.35)",
              color: "#fca5a5",
              fontSize: 13,
            }}
          >
            Render failed: {renderState.message}
          </div>
        )}

        {/* Solution drawer */}
        {solutionFor && (
          <div
            onClick={() => setSolutionFor(null)}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(0,0,0,0.7)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 24,
              zIndex: 50,
            }}
          >
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                width: "100%",
                maxWidth: 720,
                background: C.bg,
                border: `1px solid ${C.borderAlt}`,
                borderRadius: 8,
                padding: 20,
                maxHeight: "80vh",
                overflowY: "auto",
                position: "relative",
              }}
            >
              <button
                onClick={() => setSolutionFor(null)}
                aria-label="Close"
                style={{
                  position: "absolute",
                  top: 10,
                  right: 10,
                  background: "transparent",
                  border: "none",
                  color: C.textMuted,
                  cursor: "pointer",
                }}
              >
                <X size={18} strokeWidth={2} />
              </button>
              <div style={{ fontFamily: SANS, fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
                {solutionFor.title}
              </div>
              <div style={{ fontSize: 11, color: C.textFaint, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                Python
              </div>
              <pre
                style={{
                  background: "#0d1117",
                  padding: 12,
                  borderRadius: 4,
                  fontSize: 12,
                  color: C.text,
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                  overflow: "auto",
                  marginBottom: 16,
                }}
              >
                {solutionFor.starterCode.python}
              </pre>
              <div style={{ fontSize: 11, color: C.textFaint, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
                C++
              </div>
              <pre
                style={{
                  background: "#0d1117",
                  padding: 12,
                  borderRadius: 4,
                  fontSize: 12,
                  color: C.text,
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                  overflow: "auto",
                }}
              >
                {solutionFor.starterCode.cpp}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DPPracticePage;
