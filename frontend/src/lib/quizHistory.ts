// Item #34 — Per-topic quiz history → adaptive difficulty hints.
//
// When the user answers post-lesson quizzes, we record correctness per topic
// in localStorage. The next time the user asks for a lesson on that topic,
// we map their accuracy to a difficulty hint that the backend agent uses to
// extend hard topics + skip past mastered ones.
//
// Storage shape (localStorage["lumen_quiz_history"]):
//   { [topicId]: [{ correct: boolean, at: number }, ...] }
//
// Hints are simple and explicit so the LLM prompt can branch on them:
//   "extend"  — user struggles; spend longer on the invariant
//   "normal"  — default lesson length
//   "skip"    — user has mastered this; produce a fast recap, not a tutorial

const STORAGE_KEY = "lumen_quiz_history";
const MIN_ATTEMPTS = 3;  // need at least N attempts before we trust accuracy

export interface QuizAttempt {
  correct: boolean;
  at: number;
}

export type DifficultyHint = "extend" | "normal" | "skip";

function _read(): Record<string, QuizAttempt[]> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return typeof parsed === "object" && parsed ? parsed : {};
  } catch {
    return {};
  }
}

function _write(data: Record<string, QuizAttempt[]>): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  } catch {
    // localStorage full / private-mode — silently drop. Quiz history is
    // best-effort; we never want to crash a lesson flow over it.
  }
}

/** Record one quiz attempt for ``topicId``. */
export function recordAttempt(topicId: string, correct: boolean,
                                at: number = Date.now()): void {
  if (!topicId) return;
  const data = _read();
  const arr = data[topicId] ?? [];
  arr.push({ correct, at });
  // Cap history so localStorage doesn't grow without bound.
  data[topicId] = arr.slice(-50);
  _write(data);
}

/** Return the per-topic accuracy as a fraction in [0, 1], or null if too few attempts. */
export function accuracyForTopic(topicId: string): number | null {
  const data = _read();
  const arr = data[topicId] ?? [];
  if (arr.length < MIN_ATTEMPTS) return null;
  const correct = arr.filter(a => a.correct).length;
  return correct / arr.length;
}

/** Map accuracy → difficulty hint the backend can read. */
export function difficultyHintFor(topicId: string): DifficultyHint {
  const acc = accuracyForTopic(topicId);
  if (acc === null) return "normal";
  if (acc < 0.5) return "extend";
  if (acc >= 0.9) return "skip";
  return "normal";
}

/** Pure helper used by tests + the hint mapper. */
export function classifyAccuracy(acc: number | null): DifficultyHint {
  if (acc === null) return "normal";
  if (acc < 0.5) return "extend";
  if (acc >= 0.9) return "skip";
  return "normal";
}

/** Wipe all history. Used by the settings page "Reset quiz history" button. */
export function resetQuizHistory(): void {
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
}
