// PasteProblemPage — universal paste-to-render for math + DSA.
//
// Accepts text paste OR image upload (via /api/ocr). Routes through
// /api/parse-problem-v2 which classifies math vs DSA on the backend
// and returns a unified shape:
//   - DSA: includes pseudocode + step_lines (CodePanel)
//   - Math: includes steps (algebraic breakdown panel)

import React, { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2, Upload, Search, Mic, MicOff } from "lucide-react";
import {
  isVoiceInputSupported,
  createVoiceRecognizer,
  type VoiceRecognizer,
} from "../lib/voiceInput";
import { usePyodide } from "../usePyodide";
import { CodeEditorPanel } from "../CodeEditorPanel";
import { MathContent } from "../MathContent";
import { C, SANS, BODY, EASE } from "../theme";
import type { ParsedAlternative, ParsedProblem } from "../types";
import {
  flaskBase,
  pollJob,
  ocrFile,
  parseProblemV2,
  parseFollowUp,
  fetchLeetCodeProblem,
  pinVideo,
  useLiveProgress,
  useLiveStage,
} from "../lib/api";
import { StageTimeline } from "../components/StageTimeline";
import { saveVideoToLibrary } from "../lib/savedVideos";

type PasteState =
  | { kind: "idle" }
  | { kind: "ocr" }
  | { kind: "parsing" }
  | { kind: "rendering"; parsed: ParsedProblem; progress: number; topicId?: string }
  | { kind: "ready"; parsed: ParsedProblem; videoUrl: string; jobId?: string }
  | { kind: "error"; message: string };

// Conversational follow-up turn. After the initial render, the user can ask
// "now with [3,1,4]" / "show me with X instead" — each follow-up lives as a
// FollowUpTurn rendered below the original result panel.
// Side-by-side comparison: a single comparison kicks off two concurrent
// renders (primary + first alternative) and shows them in a 2-column grid.
// Synced playback: pressing play on either video plays both; pause on one
// pauses the other. Independent scrub allowed via the native controls.
type ComparisonState =
  | { kind: "rendering"; left: { parsed: ParsedProblem }; right: { parsed: ParsedProblem; alt: ParsedAlternative } }
  | { kind: "ready"; leftUrl: string; rightUrl: string;
      leftParsed: ParsedProblem; rightParsed: ParsedProblem;
      rightLabel: string }
  | { kind: "error"; message: string };

type FollowUpTurn =
  | { kind: "parsing"; text: string }
  | { kind: "rendering"; text: string; parsed: ParsedProblem }
  | { kind: "ready"; text: string; parsed: ParsedProblem; videoUrl: string }
  | { kind: "error"; text: string; message: string };

// Quiz mode: after a render, the user can test their understanding with
// 1-2 multiple choice questions generated from the prior parsed problem.
interface QuizQuestion {
  q: string;
  options: string[];
  correct: number;
  why: string;
}
type QuizState =
  | { kind: "loading" }
  | { kind: "ready"; questions: QuizQuestion[]; answers: (number | null)[]; submitted: boolean }
  | { kind: "error"; message: string };

// Build runnable Python starter code from a parsed problem. The user edits
// this in the Monaco editor, hits Run, and Pyodide executes it in-browser.
//
// Math problems → expose the expression as f(x) so the user can evaluate
// it at points and explore.
// DSA problems → wrap the parser's bespoke pseudocode in a `solve` function
// stub and call it with the literal example inputs from the parsed params.
function buildStarterCode(parsed: ParsedProblem): string {
  if (parsed.domain === "math") {
    const expr = (parsed.params.expression as string | undefined) || "x";
    // Translate sympy-style operators that Pyodide might not understand
    // out-of-the-box. ** stays the same; exp() / log() / etc. need math.
    const pythonized = expr
      .replace(/\bexp\(/g, "math.exp(")
      .replace(/\blog\(/g, "math.log(")
      .replace(/\bsqrt\(/g, "math.sqrt(")
      .replace(/\bsin\(/g, "math.sin(")
      .replace(/\bcos\(/g, "math.cos(")
      .replace(/\btan\(/g, "math.tan(")
      .replace(/\bpi\b/g, "math.pi")
      .replace(/\bE\b/g, "math.e");
    return (
      "# Try evaluating the expression at different points.\n" +
      "import math\n\n" +
      `def f(x):\n    return ${pythonized}\n\n` +
      "# Evaluate at a few points\n" +
      "for x in [0, 1, 2, 3]:\n" +
      "    print(f\"f({x}) = {f(x)}\")\n"
    );
  }

  // DSA path
  const arr =
    (parsed.params.array as any[] | undefined) ||
    (parsed.params.values as any[] | undefined) ||
    [];
  const target = parsed.params.target;
  const k = parsed.params.k;
  const pseudo = parsed.pseudocode || "    pass";
  // Indent every non-empty line of pseudocode by 4 spaces so it sits
  // inside the function body
  const indented = pseudo
    .split("\n")
    .map((l) => (l.trim() ? "    " + l : l))
    .join("\n");

  // Pick a function signature based on what the parser extracted
  const argParts: string[] = [];
  const callArgs: string[] = [];
  if (arr.length > 0) {
    argParts.push("nums");
    callArgs.push(`nums=${JSON.stringify(arr)}`);
  }
  if (target !== undefined && target !== null) {
    argParts.push("target");
    callArgs.push(`target=${target}`);
  }
  if (k !== undefined && k !== null) {
    argParts.push("k");
    callArgs.push(`k=${k}`);
  }
  if (argParts.length === 0) {
    argParts.push("nums");
    callArgs.push("nums=[]");
  }

  return (
    "# Edit this function — code runs in YOUR browser via Pyodide.\n" +
    "# The starter is the parser's pseudocode; modify it to your solution.\n\n" +
    `def solve(${argParts.join(", ")}):\n${indented}\n\n` +
    `result = solve(${callArgs.join(", ")})\n` +
    'print(f"result = {result}")\n'
  );
}

const FOLLOWUP_CHIPS: { label: string; text: string }[] = [
  { label: "Try different inputs", text: "Show me with a different example input" },
  { label: "Slower step-by-step", text: "Walk me through this step by step, slower" },
  { label: "Different approach", text: "Show me with a different algorithm or approach" },
  { label: "Compare brute force", text: "Visualize the brute force version too" },
];

const SAMPLE_PROBLEMS: { label: string; text: string }[] = [
  {
    label: "Two Sum (DSA)",
    text:
      "Given an array of integers nums = [2, 7, 11, 15] and an integer " +
      "target = 9, return indices of the two numbers such that they add up " +
      "to target. You may assume each input has exactly one solution, and " +
      "you may not use the same element twice.",
  },
  {
    label: "Trapping Rain Water (DSA)",
    text:
      "Given n non-negative integers heights = [0,1,0,2,1,0,1,3,2,1,2,1] " +
      "representing an elevation map where the width of each bar is 1, " +
      "compute how much water it can trap after raining.",
  },
  {
    label: "Definite Integral (Math)",
    text:
      "Compute the definite integral of x squared from 0 to 4 using a " +
      "Riemann sum with 8 midpoint rectangles.",
  },
  {
    label: "Find Limit (Math)",
    text: "Find the limit of sin(x) / x as x approaches 0.",
  },
  {
    label: "Tangent Line (Math)",
    text: "Find the derivative of x^3 at x = 2 and graph its tangent line.",
  },
];

interface PasteProblemPageProps {
  initialShare?: ParsedProblem | null;
  initialText?: string;   // pre-fill + auto-analyze (used by notes panel)
  embedded?: boolean;     // hide textarea/header, show results panel only
  onClose?: () => void;   // X button in embedded mode
}

const PasteProblemPage: React.FC<PasteProblemPageProps> = ({
  initialShare,
  initialText,
  embedded,
  onClose,
}) => {
  const [text, setText] = useState(initialText || "");
  const [state, setState] = useState<PasteState>({ kind: "idle" });

  // Item #33 — voice input via browser SpeechRecognition. The recognizer is
  // created lazily on first click so we don't request mic permission on page
  // load. Recognizer is held in a ref because it has no React state.
  const voiceSupported = isVoiceInputSupported();
  const voiceRecogRef = useRef<VoiceRecognizer | null>(null);
  const [listening, setListening] = useState(false);
  const [voiceError, setVoiceError] = useState<string | null>(null);

  const handleToggleVoice = useCallback(() => {
    if (!voiceSupported) return;
    if (voiceRecogRef.current?.isListening()) {
      voiceRecogRef.current.stop();
      return;
    }
    const rec = createVoiceRecognizer({
      onTranscript: (transcript, isFinal) => {
        if (!isFinal) return;  // only commit final chunks to avoid jitter
        setText(prev => {
          const sep = prev.length > 0 && !prev.endsWith(" ") ? " " : "";
          return prev + sep + transcript;
        });
      },
      onError: msg => {
        setVoiceError(msg);
        setListening(false);
      },
      onEnd: () => setListening(false),
    });
    if (!rec) return;
    voiceRecogRef.current = rec;
    setVoiceError(null);
    setListening(true);
    rec.start();
  }, [voiceSupported]);

  // Make sure we release the mic if the component unmounts mid-record.
  useEffect(() => {
    return () => { voiceRecogRef.current?.abort(); };
  }, []);
  const [followUps, setFollowUps] = useState<FollowUpTurn[]>([]);
  const [followUpInput, setFollowUpInput] = useState("");
  const [shareCode, setShareCode] = useState<string | null>(null);
  const [shareError, setShareError] = useState<string | null>(null);
  const [sharing, setSharing] = useState(false);
  // Generation counters: incremented at the start of each long-running async
  // handler. The handler captures the gen value, then on resolution checks
  // it's still current before writing state. Prevents stale responses from
  // clobbering newer ones when the user re-triggers mid-flight.
  const compareGen = useRef(0);
  const quizGen = useRef(0);
  const shareGen = useRef(0);
  const consumedShareRef = useRef<ParsedProblem | null>(null);
  const pyodide = usePyodide();   // lazy-loads on first Run click

  // Video playback control: speed + replay + scrub-by-chapter for lessons
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [playbackRate, setPlaybackRate] = useState(1);

  // Live stage + progress from the backend, keyed by the topicId stashed
  // in the rendering state. Refresh on every backend poll tick.
  const currentTopicId = state.kind === "rendering" ? (state.topicId ?? null) : null;
  const liveProgress = useLiveProgress(currentTopicId);
  const liveStage = useLiveStage(currentTopicId);

  // Save-to-library status: 'idle' | 'saving' | 'saved' | error message
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | string>("idle");

  // Side-by-side comparison state and refs (left/right videos with
  // synchronized play/pause).
  const [comparison, setComparison] = useState<ComparisonState | null>(null);
  const [quiz, setQuiz] = useState<QuizState | null>(null);
  const leftVideoRef = useRef<HTMLVideoElement | null>(null);
  const rightVideoRef = useRef<HTMLVideoElement | null>(null);

  // Sync video pair: when one video plays/pauses, mirror to the other.
  // Best-effort — drift accumulates if scrub differs but for educational
  // viewing it's fine.
  useEffect(() => {
    if (comparison?.kind !== "ready") return;
    const left = leftVideoRef.current;
    const right = rightVideoRef.current;
    if (!left || !right) return;

    const onLeftPlay = () => { right.play().catch(() => {}); };
    const onLeftPause = () => { right.pause(); };
    const onRightPlay = () => { left.play().catch(() => {}); };
    const onRightPause = () => { left.pause(); };

    left.addEventListener("play", onLeftPlay);
    left.addEventListener("pause", onLeftPause);
    right.addEventListener("play", onRightPlay);
    right.addEventListener("pause", onRightPause);
    return () => {
      left.removeEventListener("play", onLeftPlay);
      left.removeEventListener("pause", onLeftPause);
      right.removeEventListener("play", onRightPlay);
      right.removeEventListener("pause", onRightPause);
    };
  }, [comparison]);

  // Voice narration via the browser's built-in SpeechSynthesis. Reads
  // title + explanation + each step (math) or pseudocode summary (DSA).
  // No backend dep, no API key — works fully offline.
  const [narrating, setNarrating] = useState(false);
  const handleToggleNarrate = useCallback(() => {
    if (state.kind !== "ready") return;
    const synth = window.speechSynthesis;
    if (!synth) return;
    if (narrating) {
      synth.cancel();
      setNarrating(false);
      return;
    }
    const parsed = state.parsed;
    const lines: string[] = [];
    if (parsed.title) lines.push(parsed.title + ".");
    if (parsed.why_this_pattern) lines.push(parsed.why_this_pattern);
    if (parsed.explanation) lines.push(parsed.explanation);
    if (parsed.steps && parsed.steps.length) {
      parsed.steps.forEach((s, i) => lines.push(`Step ${i + 1}. ${s}`));
    }
    const text = lines.join(" ")
      .replace(/\$([^$]+)\$/g, "$1")    // strip $...$ delimiters, keep inner text
      .replace(/\\[a-zA-Z]+\s*/g, " ")  // strip LaTeX commands (\frac, \int, \sqrt…)
      .replace(/[{}^_]/g, " ")           // strip LaTeX structural chars
      .replace(/\s+/g, " ")
      .trim();
    if (!text) return;
    synth.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.0;
    utter.pitch = 1.0;
    utter.onend = () => setNarrating(false);
    utter.onerror = () => setNarrating(false);
    setNarrating(true);
    synth.speak(utter);
  }, [state, narrating]);

  // Cancel narration on unmount AND whenever the visible problem changes,
  // so a fresh paste/follow-up doesn't keep talking about the previous one.
  const parsedRef = state.kind === "ready" || state.kind === "rendering"
    ? state.parsed : null;
  useEffect(() => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setNarrating(false);
  }, [parsedRef]);
  useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  // Generate a shareable short code for the current parsed problem and
  // copy a https://.../r/<code> link to the user's clipboard.
  const handleShare = useCallback(async () => {
    if (state.kind !== "ready" || sharing) return;
    const myGen = ++shareGen.current;
    setSharing(true);
    setShareError(null);
    try {
      const res = await fetch(`${flaskBase()}/api/share`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parsed: state.parsed }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.error || `share failed (${res.status})`);
      }
      const { shareCode: code } = await res.json();
      if (myGen !== shareGen.current) return;
      setShareCode(code);
      const url = `${window.location.origin}/r/${code}`;
      try { await navigator.clipboard.writeText(url); } catch {}
    } catch (e) {
      if (myGen !== shareGen.current) return;
      setShareCode(null);
      setShareError(e instanceof Error ? e.message : "Share failed");
    } finally {
      if (myGen === shareGen.current) setSharing(false);
    }
  }, [state, sharing]);

  // Replay a share: take the parsed payload, re-render its scene, and skip
  // the parse step entirely. Triggered when App routes us here with
  // initialShare set (i.e. the URL was /r/<code>). consumedShareRef stops
  // the effect from re-firing if the user navigates away and back, since
  // App holds onto the prop for the session.
  useEffect(() => {
    if (!initialShare) return;
    if (consumedShareRef.current === initialShare) return;
    consumedShareRef.current = initialShare;
    let cancelled = false;
    (async () => {
      setState({ kind: "rendering", parsed: initialShare, progress: 0 });
      const flaskUrl = flaskBase();
      const isLesson = !!(initialShare.lesson_steps
                           && initialShare.lesson_steps.length >= 2);
      try {
        let renderRes: Response;
        if (isLesson) {
          renderRes = await fetch(`${flaskUrl}/api/render-lesson`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              steps: initialShare.lesson_steps!.map((s) => ({
                scene: s.scene,
                params: s.params,
                caption: s.caption || "",
              })),
            }),
          });
        } else {
          renderRes = await fetch(`${flaskUrl}/render`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              scene: initialShare.scene,
              params: {
                caption: initialShare.title,
                ...initialShare.params,
                ...(initialShare.pseudocode ? { pseudocode: initialShare.pseudocode } : {}),
                ...(initialShare.step_lines && Object.keys(initialShare.step_lines).length
                  ? { step_lines: initialShare.step_lines } : {}),
              },
            }),
          });
        }
        if (!renderRes.ok) {
          const detail = await renderRes.text().catch(() => "");
          if (!cancelled) {
            setState({ kind: "error", message: `Render failed (${renderRes.status}): ${detail.slice(0, 160)}` });
          }
          return;
        }
        const { job_id: jobId } = await renderRes.json();
        if (!jobId) {
          if (!cancelled) setState({ kind: "error", message: "Render returned no job_id" });
          return;
        }
        const result = await pollJob(flaskUrl, jobId, `share-${jobId}`);
        if (cancelled) return;
        if (result.status === "ready") {
          setState({ kind: "ready", parsed: initialShare, videoUrl: result.videoUrl });
        } else {
          setState({ kind: "error", message: result.error || "render failed" });
        }
      } catch (e) {
        if (!cancelled) {
          setState({ kind: "error",
                     message: e instanceof Error ? e.message : "Render failed" });
        }
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialShare]);

  const handleSaveToLibrary = useCallback(async () => {
    if (state.kind !== "ready") return;
    if (!state.jobId) {
      setSaveStatus("no job id available to pin");
      return;
    }
    setSaveStatus("saving");
    try {
      // 1. Pin on the backend so the file survives cleanup
      await pinVideo(state.jobId);
      // 2. Download + IndexedDB + metadata
      await saveVideoToLibrary({
        jobId: state.jobId,
        title: state.parsed.title || state.parsed.scene,
        scene: state.parsed.scene,
        domain: state.parsed.domain === "math" ? "math"
              : state.parsed.domain === "dsa" ? "dsa"
              : "unknown",
        serverUrl: state.videoUrl,
      });
      setSaveStatus("saved");
    } catch (e) {
      setSaveStatus(e instanceof Error ? e.message : "save failed");
    }
  }, [state]);

  // Reset save status when the underlying video changes
  useEffect(() => {
    if (state.kind === "ready") setSaveStatus("idle");
  }, [state.kind === "ready" ? state.videoUrl : null]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleStartQuiz = useCallback(async () => {
    if (state.kind !== "ready") return;
    const myGen = ++quizGen.current;
    setQuiz({ kind: "loading" });
    try {
      const res = await fetch(`${flaskBase()}/api/quiz`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prior: state.parsed }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.error || `quiz failed (${res.status})`);
      }
      const data = await res.json();
      const raw: QuizQuestion[] = data.questions || [];
      // Validate + sanitize: skip malformed entries, clamp `correct` index
      const questions: QuizQuestion[] = raw
        .filter(q => q && typeof q.q === "string"
                       && Array.isArray(q.options) && q.options.length >= 2)
        .map(q => ({
          ...q,
          correct: Math.max(0, Math.min(q.options.length - 1,
                                         typeof q.correct === "number" ? q.correct : 0)),
          why: typeof q.why === "string" ? q.why : "",
        }));
      if (questions.length === 0) {
        throw new Error("no valid questions returned");
      }
      if (myGen !== quizGen.current) return;
      setQuiz({
        kind: "ready",
        questions,
        answers: questions.map(() => null),
        submitted: false,
      });
    } catch (e) {
      if (myGen !== quizGen.current) return;
      setQuiz({
        kind: "error",
        message: e instanceof Error ? e.message : "quiz failed",
      });
    }
  }, [state]);

  const handleCompare = useCallback(async (alt: ParsedAlternative) => {
    if (state.kind !== "ready") return;
    const myGen = ++compareGen.current;
    setComparison({
      kind: "rendering",
      left: { parsed: state.parsed },
      right: { parsed: state.parsed, alt },
    });

    const flaskUrl = flaskBase();
    const renderOne = async (scene: string, params: any, label: string) => {
      const res = await fetch(`${flaskUrl}/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scene,
          params: { ...params, caption: label },
        }),
      });
      if (!res.ok) throw new Error(`Render failed (${res.status})`);
      const { job_id } = await res.json();
      const result = await pollJob(flaskUrl, job_id, `paste-cmp-${job_id}`);
      if (result.status !== "ready") {
        throw new Error(result.error || "render failed");
      }
      return result.videoUrl;
    };

    try {
      const [leftUrl, rightUrl] = await Promise.all([
        renderOne(state.parsed.scene,
                  { ...state.parsed.params,
                    ...(state.parsed.pseudocode ? { pseudocode: state.parsed.pseudocode } : {}),
                    ...(state.parsed.step_lines && Object.keys(state.parsed.step_lines).length
                      ? { step_lines: state.parsed.step_lines } : {}) },
                  state.parsed.title),
        renderOne(alt.scene, alt.params, alt.label),
      ]);
      if (myGen !== compareGen.current) return;
      setComparison({
        kind: "ready",
        leftUrl, rightUrl,
        leftParsed: state.parsed,
        rightParsed: { ...state.parsed, scene: alt.scene, params: alt.params, title: alt.label },
        rightLabel: alt.label,
      });
    } catch (e) {
      if (myGen !== compareGen.current) return;
      setComparison({
        kind: "error",
        message: e instanceof Error ? e.message : "Comparison failed",
      });
    }
  }, [state]);

  const setSpeed = useCallback((rate: number) => {
    setPlaybackRate(rate);
    if (videoRef.current) videoRef.current.playbackRate = rate;
  }, []);

  const replayVideo = useCallback(() => {
    if (videoRef.current) {
      videoRef.current.currentTime = 0;
      videoRef.current.play();
    }
  }, []);

  const scrubToChapter = useCallback((idx: number, totalChapters: number) => {
    if (!videoRef.current) return;
    const dur = videoRef.current.duration;
    if (!dur || !isFinite(dur)) return;
    // Even-split estimate — backend currently doesn't expose per-chapter
    // start times, so we assume scenes are roughly equal length
    videoRef.current.currentTime = (dur / totalChapters) * idx;
    videoRef.current.play();
  }, []);

  const isBusy = state.kind === "ocr" || state.kind === "parsing" || state.kind === "rendering";
  const isFollowingUp = followUps.some(
    (t) => t.kind === "parsing" || t.kind === "rendering"
  );

  // Submit a conversational follow-up. The "prior" we send is whatever's
  // currently visible — the latest ready turn, or the initial state.parsed.
  const handleFollowUp = useCallback(async (followUpText: string) => {
    const trimmed = followUpText.trim();
    if (!trimmed) return;

    // Use the latest ready turn's parsed result as the prior, falling back
    // to the initial state.parsed.
    const lastReady = [...followUps].reverse().find((t) => t.kind === "ready");
    const prior =
      lastReady && lastReady.kind === "ready"
        ? lastReady.parsed
        : state.kind === "ready" || state.kind === "rendering"
          ? state.parsed
          : null;
    if (!prior) return;  // nothing to follow up on

    setFollowUpInput("");
    const turnIdx = followUps.length;
    setFollowUps((prev) => [...prev, { kind: "parsing", text: trimmed }]);

    let parsed: ParsedProblem;
    try {
      parsed = await parseFollowUp(prior, trimmed);
    } catch (e) {
      setFollowUps((prev) => prev.map((t, i) =>
        i === turnIdx
          ? { kind: "error", text: trimmed, message: e instanceof Error ? e.message : "Couldn't parse follow-up" }
          : t,
      ));
      return;
    }

    setFollowUps((prev) => prev.map((t, i) =>
      i === turnIdx ? { kind: "rendering", text: trimmed, parsed } : t,
    ));

    const flaskUrl = flaskBase();
    try {
      let renderRes: Response;
      if (parsed.lesson_steps && parsed.lesson_steps.length >= 2) {
        renderRes = await fetch(`${flaskUrl}/api/render-lesson`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            steps: parsed.lesson_steps.map((s, i) => ({
              scene: s.scene,
              params: { ...s.params, caption: s.caption || `${parsed.title} (${i + 1}/${parsed.lesson_steps!.length})` },
              caption: s.caption,
            })),
          }),
        });
      } else {
        renderRes = await fetch(`${flaskUrl}/render`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            scene: parsed.scene,
            params: {
              caption: parsed.title,
              ...parsed.params,
              ...(parsed.pseudocode ? { pseudocode: parsed.pseudocode } : {}),
              ...(parsed.step_lines && Object.keys(parsed.step_lines).length
                ? { step_lines: parsed.step_lines }
                : {}),
            },
          }),
        });
      }
      if (!renderRes.ok) {
        const detail = await renderRes.text().catch(() => "");
        setFollowUps((prev) => prev.map((t, i) =>
          i === turnIdx
            ? { kind: "error", text: trimmed, message: `Render failed (${renderRes.status}): ${detail.slice(0, 160)}` }
            : t,
        ));
        return;
      }
      const { job_id: jobId } = await renderRes.json();
      const result = await pollJob(flaskUrl, jobId, `paste-fu-${jobId}`);
      if (result.status === "ready") {
        setFollowUps((prev) => prev.map((t, i) =>
          i === turnIdx ? { kind: "ready", text: trimmed, parsed, videoUrl: result.videoUrl } : t,
        ));
      } else {
        setFollowUps((prev) => prev.map((t, i) =>
          i === turnIdx
            ? { kind: "error", text: trimmed, message: result.error || "render failed" }
            : t,
        ));
      }
    } catch (e) {
      setFollowUps((prev) => prev.map((t, i) =>
        i === turnIdx
          ? { kind: "error", text: trimmed, message: e instanceof Error ? e.message : "Render failed" }
          : t,
      ));
    }
  }, [state, followUps]);

  // Click an alternative button → re-render with the alternative scene/params
  // Uses the SAME parsed object as a base so domain-specific panels stay
  // (steps for math, pseudocode for DSA). Only the scene + params + active
  // video changes.
  const handleAlternative = useCallback(async (alt: ParsedAlternative) => {
    if (state.kind !== "ready" && state.kind !== "rendering") return;
    const basePrior = state.parsed;
    const merged: ParsedProblem = {
      ...basePrior,
      scene: alt.scene,
      params: alt.params,
      title: `${basePrior.title} — ${alt.label}`,
    };
    setState({ kind: "rendering", parsed: merged, progress: 0 });
    const flaskUrl = flaskBase();
    try {
      const renderRes = await fetch(`${flaskUrl}/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scene: alt.scene,
          params: { caption: alt.label, ...alt.params },
        }),
      });
      if (!renderRes.ok) {
        const detail = await renderRes.text().catch(() => "");
        setState({ kind: "error",
                   message: `Render failed (${renderRes.status}): ${detail.slice(0, 160)}` });
        return;
      }
      const { job_id: jobId } = await renderRes.json();
      if (!jobId) {
        setState({ kind: "error", message: "Render returned no job_id" });
        return;
      }
      const result = await pollJob(flaskUrl, jobId, `paste-alt-${jobId}`);
      if (result.status === "ready") {
        setState({ kind: "ready", parsed: merged, videoUrl: result.videoUrl });
      } else {
        setState({ kind: "error", message: result.error || "render failed" });
      }
    } catch (e) {
      setState({ kind: "error",
                 message: e instanceof Error ? e.message : "Render failed" });
    }
  }, [state]);

  // Detect a LeetCode problem URL pasted into the textarea so we can offer
  // a 1-click "Fetch problem" button instead of forcing copy-paste of prose.
  const leetcodeUrlMatch = text.trim().match(
    /https?:\/\/(?:www\.)?leetcode\.com\/problems\/[a-z0-9-]+\/?/i,
  );

  const handleFetchUrl = useCallback(async () => {
    if (!leetcodeUrlMatch) return;
    setState({ kind: "ocr" });   // reuse the "fetching" spinner state
    try {
      const fetched = await fetchLeetCodeProblem(leetcodeUrlMatch[0]);
      setText(fetched.rawText + (fetched.sampleInput ? `\n\nExample: ${fetched.sampleInput}` : ""));
      setState({ kind: "idle" });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error
          ? `Couldn't fetch from LeetCode: ${err.message}`
          : "Fetch failed",
      });
    }
  }, [leetcodeUrlMatch]);

  // Image upload → OCR → fill textarea
  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";  // allow re-uploading the same file
    setState({ kind: "ocr" });
    try {
      const { text: ocrText } = await ocrFile(file);
      setText(ocrText);
      setState({ kind: "idle" });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : "OCR failed. Try pasting the text directly.",
      });
    }
  }, []);

  // Core render logic extracted so it can be called both from the button
  // (handleVisualize) and from the auto-run effect (initialText prop).
  const runVisualize = useCallback(async (rawText: string) => {
    const trimmed = rawText.trim();
    if (!trimmed) return;

    setState({ kind: "parsing" });
    setFollowUps([]);
    setComparison(null);
    setQuiz(null);
    setShareCode(null);
    setShareError(null);

    let parsed: ParsedProblem;
    try {
      parsed = await parseProblemV2(trimmed);
    } catch (e) {
      setState({
        kind: "error",
        message:
          e instanceof Error
            ? e.message
            : "Couldn't parse the problem. Try rephrasing or pasting the example input.",
      });
      return;
    }

    setState({ kind: "rendering", parsed, progress: 0 });

    const flaskUrl = flaskBase();
    try {
      let renderRes: Response;

      // If parser produced a multi-scene lesson, hit /api/render-lesson
      // (which calls submit_lesson under the hood — parallel render + ffmpeg
      // stitch into one stitched video). Otherwise single-scene /render.
      if (parsed.lesson_steps && parsed.lesson_steps.length >= 2) {
        renderRes = await fetch(`${flaskUrl}/api/render-lesson`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            steps: parsed.lesson_steps.map((s, i) => ({
              scene: s.scene,
              params: {
                ...s.params,
                caption: s.caption || `${parsed.title} (${i + 1}/${parsed.lesson_steps!.length})`,
              },
              caption: s.caption,
            })),
          }),
        });
      } else {
        renderRes = await fetch(`${flaskUrl}/render`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            scene: parsed.scene,
            params: {
              caption: parsed.title,
              ...parsed.params,
              ...(parsed.pseudocode ? { pseudocode: parsed.pseudocode } : {}),
              ...(parsed.step_lines && Object.keys(parsed.step_lines).length
                ? { step_lines: parsed.step_lines }
                : {}),
            },
          }),
        });
      }
      if (!renderRes.ok) {
        const detail = await renderRes.text().catch(() => "");
        setState({
          kind: "error",
          message: `Render failed (${renderRes.status}): ${detail.slice(0, 160)}`,
        });
        return;
      }
      const { job_id: jobId } = await renderRes.json();
      if (!jobId) {
        setState({ kind: "error", message: "Render returned no job_id" });
        return;
      }
      // Synthetic topicId so the live-progress map stays partitioned per paste.
      const topicId = `paste-${jobId}`;
      setState({ kind: "rendering", parsed, progress: 0, topicId });
      const result = await pollJob(flaskUrl, jobId, topicId);
      if (result.status === "ready") {
        setState({ kind: "ready", parsed, videoUrl: result.videoUrl, jobId });
      } else {
        setState({
          kind: "error",
          message: result.error || "render failed",
        });
      }
    } catch (e) {
      setState({
        kind: "error",
        message: e instanceof Error ? e.message : "Render failed",
      });
    }
  }, []); // stable — no closure over component state

  // Auto-run when mounted with initialText (from notes highlight panel).
  // The component is re-keyed by the parent when selection changes, so this
  // fires exactly once per highlighted selection.
  useEffect(() => {
    if (initialText?.trim()) {
      runVisualize(initialText);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleVisualize = useCallback(async () => {
    await runVisualize(text);
  }, [text, runVisualize]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      if (!isBusy) handleVisualize();
    }
  };

  const buttonLabel =
    state.kind === "ocr"
      ? "Reading image…"
      : state.kind === "parsing"
        ? "Detecting pattern…"
        : state.kind === "rendering"
          ? "Rendering…"
          : "Visualize";

  return (
    <div
      className="h-full overflow-y-auto"
      style={{ background: C.bg, color: C.text, fontFamily: BODY }}
    >
      <div className={embedded ? "px-6 py-6" : "max-w-3xl mx-auto px-8 py-10"}>
        {/* Embedded mode: compact header with close button */}
        {embedded ? (
          <div className="flex items-center justify-between mb-6">
            <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: "0.05em", color: C.textFaint, textTransform: "uppercase" }}>
              Analysis
            </div>
            {onClose && (
              <button
                onClick={onClose}
                style={{ color: C.textFaint, background: "transparent", border: "none", cursor: "pointer", fontSize: 18, lineHeight: 1 }}
                aria-label="Close analysis panel"
              >
                ×
              </button>
            )}
          </div>
        ) : (
          <header className="mb-8">
            <h1
              style={{
                fontFamily: SANS,
                fontSize: 32,
                fontWeight: 600,
                letterSpacing: "-0.02em",
                marginBottom: 8,
              }}
            >
              Paste a problem
            </h1>
            <p style={{ color: C.textMuted, fontSize: 14, lineHeight: 1.6 }}>
              Math (integrals, limits, derivatives) or DSA (LeetCode patterns) —
              paste the text or upload an image. We'll detect the topic, extract
              your example input, and render a walkthrough.
            </p>
          </header>
        )}

        {/* Textarea + controls — hidden in embedded mode (initialText auto-runs).
            Fragment needed because && requires a single JSX child. */}
        {!embedded && (
        <><div className="mb-3 flex items-center gap-2 flex-wrap">
          <label
            className="px-2.5 py-1 rounded cursor-pointer flex items-center gap-1.5"
            style={{
              fontSize: 12,
              color: C.text,
              border: `1px solid ${C.borderAlt}`,
              background: C.surface,
              opacity: isBusy ? 0.5 : 1,
              cursor: isBusy ? "not-allowed" : "pointer",
            }}
          >
            <Upload size={12} strokeWidth={2} />
            Upload image
            <input
              type="file"
              accept="image/*,application/pdf"
              onChange={handleFileUpload}
              disabled={isBusy}
              style={{ display: "none" }}
            />
          </label>
          <span style={{ fontSize: 12, color: C.textFaint, marginLeft: 4 }}>or try:</span>
          {SAMPLE_PROBLEMS.map((s) => (
            <motion.button
              key={s.label}
              onClick={() => setText(s.text)}
              disabled={isBusy}
              whileHover={isBusy ? {} : { background: C.surface }}
              whileTap={isBusy ? {} : { scale: 0.97 }}
              transition={{ duration: 0.15 }}
              className="px-2.5 py-1 rounded"
              style={{
                fontSize: 12,
                color: C.textMuted,
                border: `1px solid ${C.borderAlt}`,
                background: "transparent",
                opacity: isBusy ? 0.5 : 1,
                cursor: isBusy ? "not-allowed" : "pointer",
              }}
            >
              {s.label}
            </motion.button>
          ))}
        </div>

        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            if (state.kind === "error") setState({ kind: "idle" });
          }}
          onKeyDown={handleKeyDown}
          placeholder="Paste the full problem text including the example input (e.g. nums = [2,7,11,15], target = 9)..."
          rows={14}
          maxLength={4000}
          disabled={isBusy}
          spellCheck={false}
          className="w-full p-4 rounded-md outline-none resize-y"
          style={{
            background: C.surface,
            color: C.text,
            border: `1px solid ${C.borderAlt}`,
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
            fontSize: 13,
            lineHeight: 1.55,
            minHeight: 280,
          }}
        />

        <div className="mt-3 flex items-center justify-between">
          <span style={{ fontSize: 11, color: C.textFaint }}>
            {text.length} / 4000 — Cmd/Ctrl+Enter to visualize
          </span>
          <div className="flex items-center gap-2">
            {voiceSupported && (
              <motion.button
                onClick={handleToggleVoice}
                disabled={isBusy}
                whileHover={isBusy ? {} : { scale: 1.02 }}
                whileTap={isBusy ? {} : { scale: 0.97 }}
                transition={{ duration: 0.15 }}
                aria-label={listening ? "Stop recording" : "Voice input"}
                title={
                  voiceError
                    ? `Voice input failed: ${voiceError}`
                    : listening
                      ? "Recording — click to stop"
                      : "Record a voice prompt"
                }
                className="px-3 py-2 rounded-md flex items-center gap-1.5"
                style={{
                  background: listening ? "rgba(239, 68, 68, 0.15)" : "transparent",
                  color: listening ? "#fca5a5" : C.text,
                  border: `1px solid ${listening ? "rgba(239, 68, 68, 0.45)" : C.borderAlt}`,
                  fontFamily: BODY,
                  fontSize: 12,
                  cursor: isBusy ? "not-allowed" : "pointer",
                  opacity: isBusy ? 0.5 : 1,
                }}
              >
                {listening ? (
                  <MicOff size={12} strokeWidth={2} />
                ) : (
                  <Mic size={12} strokeWidth={2} />
                )}
                {listening ? "Listening…" : "Voice"}
              </motion.button>
            )}
            {leetcodeUrlMatch && (
              <motion.button
                onClick={handleFetchUrl}
                disabled={isBusy}
                whileHover={isBusy ? {} : { scale: 1.02 }}
                whileTap={isBusy ? {} : { scale: 0.97 }}
                transition={{ duration: 0.15 }}
                className="px-3 py-2 rounded-md flex items-center gap-1.5"
                style={{
                  background: "transparent",
                  color: C.text,
                  border: `1px solid ${C.borderAlt}`,
                  fontFamily: BODY,
                  fontSize: 12,
                  cursor: isBusy ? "not-allowed" : "pointer",
                  opacity: isBusy ? 0.5 : 1,
                }}
              >
                {state.kind === "ocr"
                  ? <Loader2 size={12} className="animate-spin" strokeWidth={2} />
                  : <Search size={12} strokeWidth={2} />}
                Fetch from LeetCode
              </motion.button>
            )}
            <motion.button
              onClick={handleVisualize}
              disabled={isBusy || !text.trim()}
              whileHover={isBusy || !text.trim() ? {} : { scale: 1.02 }}
              whileTap={isBusy || !text.trim() ? {} : { scale: 0.97 }}
              transition={{ duration: 0.15 }}
              className="px-4 py-2 rounded-md flex items-center gap-2"
              style={{
                background: text.trim() && !isBusy ? C.accent : C.borderAlt,
                color: "#ffffff",
                fontFamily: BODY,
                fontSize: 13,
                fontWeight: 500,
                cursor: isBusy || !text.trim() ? "not-allowed" : "pointer",
                opacity: isBusy || !text.trim() ? 0.7 : 1,
              }}
            >
              {isBusy && (
                <Loader2 size={14} className="animate-spin" strokeWidth={2} />
              )}
              {buttonLabel}
            </motion.button>
          </div>
        </div></>
        )}

        {/* Error banner */}
        <AnimatePresence>
          {state.kind === "error" && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2, ease: EASE }}
              className="mt-4 p-3 rounded-md"
              style={{
                background: "rgba(239, 68, 68, 0.10)",
                border: "1px solid rgba(239, 68, 68, 0.35)",
                color: "#fca5a5",
                fontSize: 13,
              }}
            >
              <strong style={{ color: "#fecaca" }}>Couldn't visualize.</strong>{" "}
              {state.message}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Result */}
        <AnimatePresence>
          {(state.kind === "rendering" || state.kind === "ready") && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25, ease: EASE }}
              className="mt-8"
            >
              <div className="mb-4">
                <h2
                  style={{
                    fontFamily: SANS,
                    fontSize: 22,
                    fontWeight: 600,
                    letterSpacing: "-0.01em",
                    marginBottom: 4,
                  }}
                >
                  {state.parsed.title}
                </h2>
                <code
                  style={{
                    fontSize: 12,
                    color: C.textFaint,
                    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                  }}
                >
                  scene: {state.parsed.scene}
                </code>
              </div>

              {/* Video container */}
              <div
                className="rounded-md overflow-hidden mb-6"
                style={{
                  background: "#0d1117",
                  border: `1px solid ${C.borderAlt}`,
                  aspectRatio: "16 / 9",
                }}
              >
                {state.kind === "ready" ? (
                  <motion.video
                    key="video"
                    ref={videoRef}
                    autoPlay
                    controls
                    loop
                    src={state.videoUrl}
                    className="w-full h-full object-contain"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.3 }}
                    onLoadedMetadata={() => {
                      if (videoRef.current) videoRef.current.playbackRate = playbackRate;
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center p-4">
                    <StageTimeline
                      stage={liveStage}
                      progress={liveProgress ?? 0}
                      hasAgentPlanning={false}
                    />
                  </div>
                )}
              </div>

              {/* Playback controls — speed dial + replay button */}
              {state.kind === "ready" && (
                <div className="mb-4 flex items-center gap-3 flex-wrap">
                  <div className="flex items-center gap-1">
                    <span style={{ fontSize: 11, color: C.textFaint, marginRight: 4 }}>
                      Speed:
                    </span>
                    {[0.5, 1, 1.5, 2].map((rate) => (
                      <button
                        key={rate}
                        onClick={() => setSpeed(rate)}
                        className="px-2 py-1 rounded"
                        style={{
                          fontSize: 11,
                          color: playbackRate === rate ? "#fff" : C.textMuted,
                          background: playbackRate === rate ? C.accent : "transparent",
                          border: `1px solid ${playbackRate === rate ? C.accent : C.borderAlt}`,
                          cursor: "pointer",
                          fontWeight: playbackRate === rate ? 600 : 400,
                        }}
                      >
                        {rate}×
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={replayVideo}
                    className="px-2.5 py-1 rounded flex items-center gap-1"
                    style={{
                      fontSize: 11,
                      color: C.textMuted,
                      background: "transparent",
                      border: `1px solid ${C.borderAlt}`,
                      cursor: "pointer",
                    }}
                  >
                    ↺ Replay
                  </button>
                </div>
              )}

              {/* Lesson chapters — clickable to scrub the video, visible only
                  for multi-scene lessons */}
              {state.parsed.lesson_steps && state.parsed.lesson_steps.length > 0 && (
                <div className="mb-4">
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
                    Lesson chapters (click to jump)
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {state.parsed.lesson_steps.map((s, i) => (
                      <button
                        key={i}
                        onClick={() => scrubToChapter(i, state.parsed.lesson_steps!.length)}
                        disabled={state.kind !== "ready"}
                        className="px-2.5 py-1 rounded text-left transition-colors"
                        style={{
                          fontSize: 12,
                          color: C.text,
                          background: C.surface,
                          border: `1px solid ${C.borderAlt}`,
                          maxWidth: 280,
                          cursor: state.kind === "ready" ? "pointer" : "default",
                          opacity: state.kind === "ready" ? 1 : 0.7,
                        }}
                        onMouseEnter={(e) => {
                          if (state.kind === "ready") e.currentTarget.style.borderColor = C.accent;
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.borderColor = C.borderAlt;
                        }}
                      >
                        <span style={{ color: C.textFaint, marginRight: 6, fontWeight: 600 }}>
                          {i + 1}
                        </span>
                        {s.caption || s.scene}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Alternative scenes — 1-click swap OR side-by-side compare */}
              {state.parsed.alternatives && state.parsed.alternatives.length > 0 && (
                <div className="mb-4">
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
                    Alternative views
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {state.parsed.alternatives.map((alt, i) => {
                      const busy = state.kind === "rendering" || comparison?.kind === "rendering";
                      return (
                        <div key={i} className="flex flex-col gap-1">
                          <motion.button
                            onClick={() => handleAlternative(alt)}
                            disabled={busy}
                            whileHover={busy ? {} : { scale: 1.02, background: C.surface }}
                            whileTap={busy ? {} : { scale: 0.97 }}
                            transition={{ duration: 0.15 }}
                            className="px-3 py-1.5 rounded-md flex flex-col items-start"
                            style={{
                              fontSize: 12,
                              color: C.text,
                              border: `1px solid ${C.borderAlt}`,
                              background: "transparent",
                              opacity: busy ? 0.5 : 1,
                              cursor: busy ? "not-allowed" : "pointer",
                              textAlign: "left",
                              maxWidth: 280,
                            }}
                            title={alt.why || ""}
                          >
                            <span style={{ fontWeight: 500 }}>→ {alt.label}</span>
                            {alt.why && (
                              <span style={{
                                fontSize: 10,
                                color: C.textFaint,
                                marginTop: 2,
                                lineHeight: 1.3,
                              }}>
                                {alt.why}
                              </span>
                            )}
                          </motion.button>
                          <button
                            onClick={() => handleCompare(alt)}
                            disabled={busy}
                            className="px-2.5 py-1 rounded text-xs"
                            style={{
                              fontSize: 11,
                              color: busy ? C.textFaint : C.accent,
                              background: "transparent",
                              border: `1px solid ${busy ? C.borderAlt : C.accent}`,
                              cursor: busy ? "not-allowed" : "pointer",
                              opacity: busy ? 0.5 : 1,
                            }}
                          >
                            ⇆ Compare side-by-side
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Side-by-side comparison panel */}
              {comparison && (
                <div className="mb-4">
                  <div
                    className="flex items-center justify-between mb-2"
                  >
                    <div style={{
                      fontSize: 11,
                      fontWeight: 500,
                      letterSpacing: "0.05em",
                      color: C.textFaint,
                      textTransform: "uppercase",
                    }}>
                      Side-by-side comparison
                    </div>
                    <button
                      onClick={() => setComparison(null)}
                      style={{
                        fontSize: 11,
                        color: C.textFaint,
                        background: "transparent",
                        border: "none",
                        cursor: "pointer",
                      }}
                    >
                      ✕ Close
                    </button>
                  </div>
                  {comparison.kind === "rendering" && (
                    <div className="flex items-center gap-2"
                         style={{ color: C.textMuted, fontSize: 13 }}>
                      <Loader2 size={14} className="animate-spin" strokeWidth={2} />
                      Rendering both scenes in parallel… ~25-40s
                    </div>
                  )}
                  {comparison.kind === "error" && (
                    <div className="p-3 rounded-md" style={{
                      background: "rgba(239, 68, 68, 0.10)",
                      border: "1px solid rgba(239, 68, 68, 0.35)",
                      color: "#fca5a5",
                      fontSize: 13,
                    }}>
                      {comparison.message}
                    </div>
                  )}
                  {comparison.kind === "ready" && (
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 4 }}>
                          {comparison.leftParsed.scene}
                        </div>
                        <div className="rounded-md overflow-hidden"
                             style={{ background: "#0d1117", border: `1px solid ${C.borderAlt}`, aspectRatio: "16/9" }}>
                          <video
                            ref={leftVideoRef}
                            autoPlay controls loop
                            src={comparison.leftUrl}
                            className="w-full h-full object-contain"
                          />
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: 12, color: C.textMuted, marginBottom: 4 }}>
                          {comparison.rightLabel}
                        </div>
                        <div className="rounded-md overflow-hidden"
                             style={{ background: "#0d1117", border: `1px solid ${C.borderAlt}`, aspectRatio: "16/9" }}>
                          <video
                            ref={rightVideoRef}
                            autoPlay controls loop
                            src={comparison.rightUrl}
                            className="w-full h-full object-contain"
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Quiz + Share buttons */}
              {!quiz && (
                <div className="mb-4 flex flex-wrap items-center gap-2">
                  <button
                    onClick={handleStartQuiz}
                    className="px-3 py-1.5 rounded text-xs"
                    style={{
                      fontSize: 12,
                      color: C.accent,
                      background: "transparent",
                      border: `1px solid ${C.accent}`,
                      cursor: "pointer",
                    }}
                  >
                    🧠 Test your understanding
                  </button>
                  <button
                    onClick={handleShare}
                    disabled={sharing}
                    className="px-3 py-1.5 rounded text-xs"
                    style={{
                      fontSize: 12,
                      color: C.text,
                      background: "transparent",
                      border: `1px solid ${C.borderAlt}`,
                      cursor: sharing ? "not-allowed" : "pointer",
                      opacity: sharing ? 0.5 : 1,
                    }}
                  >
                    {sharing ? "Generating link…" : "🔗 Share"}
                  </button>
                  <button
                    onClick={handleToggleNarrate}
                    className="px-3 py-1.5 rounded text-xs"
                    style={{
                      fontSize: 12,
                      color: narrating ? C.accent : C.text,
                      background: "transparent",
                      border: `1px solid ${narrating ? C.accent : C.borderAlt}`,
                      cursor: "pointer",
                    }}
                  >
                    {narrating ? "⏹ Stop narration" : "🔊 Narrate"}
                  </button>
                  <button
                    onClick={handleSaveToLibrary}
                    disabled={saveStatus === "saving" || saveStatus === "saved"}
                    className="px-3 py-1.5 rounded text-xs"
                    style={{
                      fontSize: 12,
                      color: saveStatus === "saved" ? C.ok : C.text,
                      background: "transparent",
                      border: `1px solid ${saveStatus === "saved" ? C.ok : C.borderAlt}`,
                      cursor: saveStatus === "saving" ? "not-allowed" : "pointer",
                      opacity: saveStatus === "saving" ? 0.5 : 1,
                    }}
                  >
                    {saveStatus === "saving" ? "Saving…"
                      : saveStatus === "saved" ? "✓ Saved"
                      : "💾 Save to Library"}
                  </button>
                  {typeof saveStatus === "string" &&
                   saveStatus !== "idle" &&
                   saveStatus !== "saving" &&
                   saveStatus !== "saved" && (
                    <span style={{ fontSize: 11, color: "#fca5a5" }}>{saveStatus}</span>
                  )}
                  {shareCode && (
                    <span
                      style={{
                        fontSize: 11,
                        color: C.textMuted,
                        fontFamily: "ui-monospace, SFMono-Regular, monospace",
                      }}
                    >
                      Link copied: /r/{shareCode}
                    </span>
                  )}
                  {shareError && (
                    <span
                      style={{
                        fontSize: 11,
                        color: "#fca5a5",
                      }}
                    >
                      {shareError}
                    </span>
                  )}
                </div>
              )}

              {quiz && (
                <div
                  className="p-4 rounded-md mb-4"
                  style={{
                    background: C.surface,
                    border: `1px solid ${C.borderAlt}`,
                  }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div style={{
                      fontSize: 11,
                      fontWeight: 500,
                      letterSpacing: "0.05em",
                      color: C.textFaint,
                      textTransform: "uppercase",
                    }}>
                      Comprehension check
                    </div>
                    <button
                      onClick={() => setQuiz(null)}
                      style={{
                        fontSize: 11,
                        color: C.textFaint,
                        background: "transparent",
                        border: "none",
                        cursor: "pointer",
                      }}
                    >
                      ✕ Close
                    </button>
                  </div>
                  {quiz.kind === "loading" && (
                    <div className="flex items-center gap-2"
                         style={{ color: C.textMuted, fontSize: 13 }}>
                      <Loader2 size={14} className="animate-spin" strokeWidth={2} />
                      Generating questions…
                    </div>
                  )}
                  {quiz.kind === "error" && (
                    <div className="p-3 rounded-md" style={{
                      background: "rgba(239, 68, 68, 0.10)",
                      border: "1px solid rgba(239, 68, 68, 0.35)",
                      color: "#fca5a5",
                      fontSize: 13,
                    }}>
                      {quiz.message}
                    </div>
                  )}
                  {quiz.kind === "ready" && (
                    <div className="space-y-4">
                      {quiz.questions.map((question, qi) => (
                        <div key={qi}>
                          <div style={{ fontSize: 13, color: C.text, fontWeight: 500, marginBottom: 8 }}>
                            {qi + 1}. {question.q}
                          </div>
                          <div className="flex flex-col gap-1.5">
                            {question.options.map((opt, oi) => {
                              const picked = quiz.answers[qi] === oi;
                              const isCorrect = oi === question.correct;
                              const showResult = quiz.submitted;
                              let bg = "transparent";
                              let bd = C.borderAlt;
                              let cl = C.text;
                              if (showResult && isCorrect) {
                                bg = "rgba(34, 197, 94, 0.12)";
                                bd = "rgba(34, 197, 94, 0.45)";
                                cl = "#86efac";
                              } else if (showResult && picked && !isCorrect) {
                                bg = "rgba(239, 68, 68, 0.12)";
                                bd = "rgba(239, 68, 68, 0.45)";
                                cl = "#fca5a5";
                              } else if (picked) {
                                bg = C.surface;
                                bd = C.accent;
                              }
                              return (
                                <button
                                  key={oi}
                                  disabled={quiz.submitted}
                                  onClick={() => {
                                    const next = [...quiz.answers];
                                    next[qi] = oi;
                                    setQuiz({ ...quiz, answers: next });
                                  }}
                                  className="px-3 py-2 rounded text-left"
                                  style={{
                                    fontSize: 12,
                                    color: cl,
                                    background: bg,
                                    border: `1px solid ${bd}`,
                                    cursor: quiz.submitted ? "default" : "pointer",
                                  }}
                                >
                                  <span style={{ marginRight: 8, opacity: 0.6 }}>
                                    {String.fromCharCode(65 + oi)}.
                                  </span>
                                  {opt}
                                </button>
                              );
                            })}
                          </div>
                          {quiz.submitted && (
                            <div
                              className="mt-2 p-2 rounded"
                              style={{
                                fontSize: 11,
                                color: C.textMuted,
                                background: "rgba(255,255,255,0.03)",
                                border: `1px solid ${C.borderAlt}`,
                                lineHeight: 1.5,
                              }}
                            >
                              <span style={{ color: C.textFaint, fontWeight: 500 }}>Why:</span>{" "}
                              {question.why}
                            </div>
                          )}
                        </div>
                      ))}
                      {!quiz.submitted ? (
                        <button
                          onClick={() => setQuiz({ ...quiz, submitted: true })}
                          disabled={quiz.answers.some(a => a === null)}
                          className="px-4 py-1.5 rounded text-sm"
                          style={{
                            fontSize: 12,
                            color: quiz.answers.some(a => a === null) ? C.textFaint : "#0d1117",
                            background: quiz.answers.some(a => a === null) ? "transparent" : C.accent,
                            border: `1px solid ${quiz.answers.some(a => a === null) ? C.borderAlt : C.accent}`,
                            cursor: quiz.answers.some(a => a === null) ? "not-allowed" : "pointer",
                          }}
                        >
                          Submit answers
                        </button>
                      ) : (
                        <div className="flex items-center gap-3">
                          <div style={{ fontSize: 13, color: C.text, fontWeight: 500 }}>
                            Score: {quiz.answers.filter((a, i) => a === quiz.questions[i].correct).length}
                            {" "}/ {quiz.questions.length}
                          </div>
                          <button
                            onClick={() => setQuiz({
                              ...quiz,
                              answers: quiz.questions.map(() => null),
                              submitted: false,
                            })}
                            style={{
                              fontSize: 11,
                              color: C.accent,
                              background: "transparent",
                              border: `1px solid ${C.accent}`,
                              padding: "4px 10px",
                              borderRadius: 4,
                              cursor: "pointer",
                            }}
                          >
                            Try again
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Math: solution steps panel (only for math problems) */}
              {state.parsed.domain === "math" && state.parsed.steps && state.parsed.steps.length > 0 && (
                <div
                  className="p-4 rounded-md mb-4"
                  style={{
                    background: C.surface,
                    border: `1px solid ${C.borderAlt}`,
                  }}
                >
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
                    Solution steps
                  </div>
                  <ol style={{ paddingLeft: 18 }}>
                    {state.parsed.steps.map((step, i) => (
                      <li
                        key={i}
                        style={{
                          fontSize: 14,
                          lineHeight: 1.7,
                          color: C.text,
                          marginBottom: 6,
                        }}
                      >
                        <MathContent text={step} />
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {/* Why this pattern wins */}
              {state.parsed.why_this_pattern && (
                <div
                  className="p-4 rounded-md mb-4"
                  style={{
                    background: C.surface,
                    border: `1px solid ${C.borderAlt}`,
                  }}
                >
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 500,
                      letterSpacing: "0.05em",
                      color: C.textFaint,
                      textTransform: "uppercase",
                      marginBottom: 6,
                    }}
                  >
                    {state.parsed.domain === "math" ? "Why this scene" : "Why this pattern wins"}
                  </div>
                  <p style={{ fontSize: 14, lineHeight: 1.6, color: C.text }}>
                    {state.parsed.why_this_pattern}
                  </p>
                </div>
              )}

              {/* Approach / explanation */}
              {state.parsed.explanation && (
                <div
                  className="p-4 rounded-md"
                  style={{
                    background: C.surface,
                    border: `1px solid ${C.borderAlt}`,
                  }}
                >
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 500,
                      letterSpacing: "0.05em",
                      color: C.textFaint,
                      textTransform: "uppercase",
                      marginBottom: 6,
                    }}
                  >
                    Approach
                  </div>
                  <p style={{ fontSize: 14, lineHeight: 1.6, color: C.text }}>
                    {state.parsed.explanation}
                  </p>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Code editor with Pyodide (browser-side Python) — visible once a
            render is ready so the starter code uses the parser's pseudocode
            and extracted inputs. */}
        {state.kind === "ready" && (
          <CodeEditorPanel
            starterCode={buildStarterCode(state.parsed)}
            pyodide={pyodide.pyodide}
            pyodideLoading={pyodide.loading}
            pyodideError={pyodide.error}
            onPyodideLoad={pyodide.load}
          />
        )}

        {/* Conversational follow-up: input bar + suggested chips, only
            visible after the initial render is ready or rendering. */}
        {(state.kind === "ready" || state.kind === "rendering") && (
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
              Ask a follow-up
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                value={followUpInput}
                onChange={(e) => setFollowUpInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !isFollowingUp) {
                    e.preventDefault();
                    handleFollowUp(followUpInput);
                  }
                }}
                disabled={isFollowingUp}
                placeholder="e.g. now with [3, 1, 4, 1, 5]"
                className="flex-1 px-3 py-2 rounded-md outline-none"
                style={{
                  background: C.surface,
                  color: C.text,
                  border: `1px solid ${C.borderAlt}`,
                  fontFamily: BODY,
                  fontSize: 13,
                }}
              />
              <motion.button
                onClick={() => handleFollowUp(followUpInput)}
                disabled={isFollowingUp || !followUpInput.trim()}
                whileHover={isFollowingUp ? {} : { scale: 1.02 }}
                whileTap={isFollowingUp ? {} : { scale: 0.97 }}
                transition={{ duration: 0.15 }}
                className="px-4 py-2 rounded-md flex items-center gap-2"
                style={{
                  background: !isFollowingUp && followUpInput.trim()
                    ? C.accent
                    : C.borderAlt,
                  color: "#ffffff",
                  fontFamily: BODY,
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: isFollowingUp || !followUpInput.trim()
                    ? "not-allowed" : "pointer",
                  opacity: isFollowingUp || !followUpInput.trim() ? 0.7 : 1,
                }}
              >
                {isFollowingUp && <Loader2 size={14} className="animate-spin" strokeWidth={2} />}
                Ask
              </motion.button>
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {FOLLOWUP_CHIPS.map((chip) => (
                <motion.button
                  key={chip.label}
                  onClick={() => handleFollowUp(chip.text)}
                  disabled={isFollowingUp}
                  whileHover={isFollowingUp ? {} : { background: C.surface }}
                  whileTap={isFollowingUp ? {} : { scale: 0.97 }}
                  transition={{ duration: 0.15 }}
                  className="px-2.5 py-1 rounded"
                  style={{
                    fontSize: 12,
                    color: C.textMuted,
                    border: `1px solid ${C.borderAlt}`,
                    background: "transparent",
                    opacity: isFollowingUp ? 0.5 : 1,
                    cursor: isFollowingUp ? "not-allowed" : "pointer",
                  }}
                >
                  {chip.label}
                </motion.button>
              ))}
            </div>
          </div>
        )}

        {/* Conversational thread: each follow-up turn renders below */}
        {followUps.map((turn, i) => (
          <div key={i} className="mt-8 pt-6"
               style={{ borderTop: `1px solid ${C.borderAlt}` }}>
            <div
              className="px-3 py-2 rounded-md mb-4 inline-block"
              style={{
                background: C.surface,
                border: `1px solid ${C.borderAlt}`,
                fontSize: 13,
                color: C.text,
              }}
            >
              <span style={{ color: C.textFaint, marginRight: 6, fontWeight: 600 }}>
                You:
              </span>
              {turn.text}
            </div>
            {turn.kind === "parsing" && (
              <div className="flex items-center gap-2"
                   style={{ color: C.textMuted, fontSize: 13 }}>
                <Loader2 size={14} className="animate-spin" strokeWidth={2} />
                Detecting pattern…
              </div>
            )}
            {turn.kind === "error" && (
              <div className="p-3 rounded-md"
                   style={{
                     background: "rgba(239, 68, 68, 0.10)",
                     border: "1px solid rgba(239, 68, 68, 0.35)",
                     color: "#fca5a5",
                     fontSize: 13,
                   }}>
                <strong style={{ color: "#fecaca" }}>Couldn't visualize.</strong> {turn.message}
              </div>
            )}
            {(turn.kind === "rendering" || turn.kind === "ready") && (
              <div>
                <h3 style={{
                  fontFamily: SANS,
                  fontSize: 18,
                  fontWeight: 600,
                  marginBottom: 8,
                }}>
                  {turn.parsed.title}
                </h3>
                <div
                  className="rounded-md overflow-hidden"
                  style={{
                    background: "#0d1117",
                    border: `1px solid ${C.borderAlt}`,
                    aspectRatio: "16 / 9",
                  }}
                >
                  {turn.kind === "ready" ? (
                    <motion.video
                      autoPlay controls loop
                      src={turn.videoUrl}
                      className="w-full h-full object-contain"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.3 }}
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <div className="flex flex-col items-center gap-2">
                        <Loader2 size={20} className="animate-spin"
                                 strokeWidth={1.5} color={C.textMuted} />
                        <span style={{ color: C.textMuted, fontSize: 12 }}>
                          Rendering…
                        </span>
                      </div>
                    </div>
                  )}
                </div>
                {/* Math: show steps for follow-up turn */}
                {turn.parsed.domain === "math" && turn.parsed.steps && turn.parsed.steps.length > 0 && (
                  <ol className="mt-3 pl-5"
                      style={{ fontSize: 13, color: C.text, lineHeight: 1.7 }}>
                    {turn.parsed.steps.map((s, j) => (
                      <li key={j} style={{ marginBottom: 4 }}>
                        <MathContent text={s} />
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default PasteProblemPage;
