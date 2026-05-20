// Item #28 — SuperMemo SM-2 spaced repetition algorithm for saved videos.
//
// Original SM-2 (Wozniak 1990): https://www.supermemo.com/en/blog/application-of-a-computer-to-improve-the-results-obtained-in-working-with-the-supermemo-method
//
// Quality scale (0-5):
//   0  — total blackout
//   1  — incorrect, but felt familiar on the answer
//   2  — incorrect, but the correct answer felt obvious
//   3  — correct with serious difficulty
//   4  — correct after hesitation
//   5  — perfect recall
//
// Quality < 3 resets the schedule; quality >= 3 expands it.

export interface SrsState {
  /** Number of consecutive successful reviews (resets on a fail). */
  repetitions: number;
  /** Days until the next review. */
  intervalDays: number;
  /** Multiplier on the interval — grows on success, shrinks on failure. */
  easeFactor: number;
  /** ms-since-epoch the card was last reviewed. */
  lastReviewedAt: number;
  /** ms-since-epoch the card is next due. */
  nextReviewAt: number;
}

/** Sensible defaults for a card that has never been reviewed (due immediately). */
export function initialSrsState(now: number = Date.now()): SrsState {
  return {
    repetitions: 0,
    intervalDays: 0,
    easeFactor: 2.5,
    lastReviewedAt: 0,
    nextReviewAt: now,
  };
}

const MS_PER_DAY = 24 * 60 * 60 * 1000;

/**
 * Apply one SM-2 review and return the new state. Pure function — caller
 * persists the result.
 *
 * @param prev    previous state (or `initialSrsState()` for a new card)
 * @param quality 0..5 (see header). Out-of-range values are clamped.
 * @param now     ms-since-epoch (defaults to Date.now() — pass an explicit
 *                value in tests for determinism)
 */
export function scheduleNext(
  prev: SrsState,
  quality: number,
  now: number = Date.now(),
): SrsState {
  const q = Math.max(0, Math.min(5, Math.round(quality)));

  // 1. Update ease factor (SM-2 formula)
  let easeFactor = prev.easeFactor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02));
  if (easeFactor < 1.3) easeFactor = 1.3;

  // 2. Decide reps + interval
  let repetitions: number;
  let intervalDays: number;
  if (q < 3) {
    // Failure: restart from the beginning
    repetitions = 0;
    intervalDays = 1;
  } else {
    repetitions = prev.repetitions + 1;
    if (repetitions === 1) {
      intervalDays = 1;
    } else if (repetitions === 2) {
      intervalDays = 6;
    } else {
      intervalDays = Math.round(prev.intervalDays * easeFactor);
    }
  }

  return {
    repetitions,
    intervalDays,
    easeFactor,
    lastReviewedAt: now,
    nextReviewAt: now + intervalDays * MS_PER_DAY,
  };
}

/** True when the card is at or past its next-review time. */
export function isDue(state: SrsState | undefined, now: number = Date.now()): boolean {
  if (!state) return true;  // missing schedule = treat as due
  return state.nextReviewAt <= now;
}

/** Human-readable "due in 2d" / "due now" / "due in 3h" string. */
export function dueLabel(state: SrsState | undefined, now: number = Date.now()): string {
  if (!state || state.nextReviewAt <= now) return "Due now";
  const ms = state.nextReviewAt - now;
  const hours = Math.round(ms / (60 * 60 * 1000));
  if (hours < 24) return `Due in ${hours}h`;
  const days = Math.round(ms / MS_PER_DAY);
  return `Due in ${days}d`;
}
