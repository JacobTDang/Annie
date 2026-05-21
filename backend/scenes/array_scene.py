import json
import math
import os

import numpy as np

from manim import *


def _strip_dict_nulls(obj):
    """Drop None values from dict keys (recursively). See dsa_scene.py."""
    if isinstance(obj, dict):
        return {k: _strip_dict_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_dict_nulls(v) for v in obj]
    return obj


def _load_params() -> dict:
    job_id = os.environ.get("MANIM_JOB_ID")
    if job_id:
        temp_dir = os.environ.get("MANIM_TEMP_DIR", os.path.join("media", "temp"))
        params_path = os.path.join(temp_dir, f"{job_id}.json")
        if os.path.exists(params_path):
            with open(params_path) as f:
                return _strip_dict_nulls(json.load(f))
    return {}


class BubbleSortScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        params = _load_params()
        arr = list(params.get("array", [5, 3, 8, 1, 9, 2]))
        n = len(arr)

        cells = self._make_cells(arr)
        row = VGroup(*cells).arrange(RIGHT, buff=0.15).center()
        self.play(FadeIn(row))
        self.wait(0.3)

        for i in range(n):
            for j in range(n - i - 1):
                self.play(
                    cells[j][0].animate.set_fill(YELLOW, opacity=0.7),
                    cells[j + 1][0].animate.set_fill(YELLOW, opacity=0.7),
                    run_time=0.25,
                )

                if arr[j] > arr[j + 1]:
                    arr[j], arr[j + 1] = arr[j + 1], arr[j]
                    p1 = cells[j].get_center().copy()
                    p2 = cells[j + 1].get_center().copy()
                    self.play(
                        cells[j].animate.move_to(p2),
                        cells[j + 1].animate.move_to(p1),
                        run_time=0.4,
                    )
                    cells[j], cells[j + 1] = cells[j + 1], cells[j]

                self.play(
                    cells[j][0].animate.set_fill(BLUE_E, opacity=0.5),
                    cells[j + 1][0].animate.set_fill(BLUE_E, opacity=0.5),
                    run_time=0.2,
                )

            self.play(cells[n - i - 1][0].animate.set_fill(GREEN_E, opacity=0.7), run_time=0.2)

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)

    def _make_cells(self, arr: list) -> list:
        cells = []
        for val in arr:
            sq = Square(
                side_length=0.9,
                fill_color=BLUE_E,
                fill_opacity=0.5,
                stroke_color=WHITE,
                stroke_width=2,
            )
            lbl = Text(str(val), font_size=28, color=WHITE)
            cells.append(VGroup(sq, lbl))
        return cells


class MergeSortScene(Scene):
    """Visual merge sort: progressive splits via vertical dividers, then
    bottom-up merges with a 'lift, sort, drop' animation per pair."""

    def construct(self):
        self.camera.background_color = "#0d1117"
        params = _load_params()
        arr = list(params.get("array", [5, 2, 8, 1, 9, 3, 7, 4]))
        caption = params.get("caption", "")

        # Constrain to 2-8 elements. Any size in this range works — no
        # power-of-two requirement (the recursion tree just becomes uneven
        # for non-powers-of-two, which is fine and educationally accurate).
        n = len(arr)
        if n < 2:
            arr = [5, 2, 8, 1, 9, 3, 7, 4]
            n = 8
        if n > 8:
            arr = arr[:8]
            n = 8

        title = Text("Merge Sort — divide & merge", font_size=28).to_edge(UP, buff=0.4)
        self.play(FadeIn(title))

        cells = self._make_cells(arr)
        row = VGroup(*cells).arrange(RIGHT, buff=0.1).center()
        self.play(FadeIn(row))
        self.wait(0.3)

        # Build the recursion tree as a list of levels of (start, end) ranges.
        # Level 0 is the whole array; each subsequent level splits every
        # non-trivial range into two halves at the midpoint. Singleton ranges
        # carry through unchanged.
        levels: list[list[tuple[int, int]]] = [[(0, n)]]
        while any(e - s > 1 for s, e in levels[-1]):
            nxt: list[tuple[int, int]] = []
            for s, e in levels[-1]:
                if e - s <= 1:
                    nxt.append((s, e))
                else:
                    m = (s + e) // 2
                    nxt.append((s, m))
                    nxt.append((m, e))
            levels.append(nxt)

        # ── Phase 1: progressive splits with vertical dividers ──────────
        #
        # At each split level L, the new dividers are at the midpoints of
        # every parent range from level L-1 that got split. dividers_by_level
        # is indexed by L-1 so we can fade out exactly the dividers
        # introduced when a given pair of children gets merged back.
        dividers_by_level: list[list[Line]] = []
        for L in range(1, len(levels)):
            new_div: list[Line] = []
            parents = [pr for pr in levels[L - 1] if pr[1] - pr[0] > 1]
            for s, e in parents:
                m = (s + e) // 2
                left  = cells[m - 1].get_right()
                right = cells[m].get_left()
                mid_x = (left[0] + right[0]) / 2
                line = Line(
                    start=[mid_x, cells[m].get_top()[1] + 0.2, 0],
                    end  =[mid_x, cells[m].get_bottom()[1] - 0.2, 0],
                    color=YELLOW,
                    stroke_width=4 if L == 1 else 2,
                )
                new_div.append(line)
            if new_div:
                self.play(*[Create(d) for d in new_div], run_time=0.4)
                self.wait(0.15)
            dividers_by_level.append(new_div)

        self.wait(0.3)

        # ── Phase 2: bottom-up merges ───────────────────────────────────
        #
        # Reverse the split tree: walk levels from deepest to shallowest;
        # for every parent range that had two children, merge them and fade
        # the corresponding divider.
        for L in range(len(levels) - 1, 0, -1):
            divs_at_level = dividers_by_level[L - 1]
            parents = [pr for pr in levels[L - 1] if pr[1] - pr[0] > 1]

            for ps, pe in parents:
                pm = (ps + pe) // 2
                ls, le = ps, pm
                rs, re = pm, pe
                left_cells  = cells[ls:le]
                right_cells = cells[rs:re]

                # Highlight the two halves being merged
                self.play(
                    *[c[0].animate.set_fill(YELLOW_E, opacity=0.7) for c in left_cells],
                    *[c[0].animate.set_fill(ORANGE,   opacity=0.7) for c in right_cells],
                    run_time=0.3,
                )

                # Stable two-finger merge
                lvals = arr[ls:le]
                rvals = arr[rs:re]
                merged_src: list[tuple[str, int]] = []
                i = j = 0
                while i < len(lvals) and j < len(rvals):
                    if lvals[i] <= rvals[j]:
                        merged_src.append(("L", i)); i += 1
                    else:
                        merged_src.append(("R", j)); j += 1
                while i < len(lvals): merged_src.append(("L", i)); i += 1
                while j < len(rvals): merged_src.append(("R", j)); j += 1

                slot_positions = [cells[k].get_center().copy() for k in range(ps, pe)]
                new_order = [
                    cells[ls + idx] if src == "L" else cells[rs + idx]
                    for src, idx in merged_src
                ]

                # Lift, swap, drop — the lift makes overlapping moves readable
                lift = 0.6
                self.play(
                    *[c.animate.shift(UP * lift) for c in left_cells + right_cells],
                    run_time=0.25,
                )
                horiz_anims = []
                for k, c in enumerate(new_order):
                    target = [slot_positions[k][0], c.get_center()[1], 0]
                    if abs(c.get_center()[0] - target[0]) > 0.01:
                        horiz_anims.append(c.animate.move_to(target))
                if horiz_anims:
                    self.play(*horiz_anims, run_time=0.55)
                self.play(
                    *[c.animate.move_to(slot_positions[k]) for k, c in enumerate(new_order)],
                    run_time=0.25,
                )

                # Commit state
                cells[ps:pe] = new_order
                arr[ps:pe] = [lvals[idx] if src == "L" else rvals[idx]
                              for src, idx in merged_src]

                # Reset the merged range to the neutral fill
                self.play(
                    *[c[0].animate.set_fill(BLUE_E, opacity=0.5) for c in cells[ps:pe]],
                    run_time=0.2,
                )

            if divs_at_level:
                self.play(*[FadeOut(d) for d in divs_at_level], run_time=0.3)

        # Final flourish: sorted = green
        self.play(
            *[c[0].animate.set_fill(GREEN_E, opacity=0.7) for c in cells],
            run_time=0.5,
        )

        if caption:
            cap = Text(caption, font_size=20, color=GRAY_B).to_edge(DOWN, buff=0.4)
            self.play(FadeIn(cap))

        self.wait(1)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)

    def _make_cells(self, arr: list) -> list:
        cells = []
        for val in arr:
            sq = Square(
                side_length=0.85,
                fill_color=BLUE_E,
                fill_opacity=0.5,
                stroke_color=WHITE,
                stroke_width=2,
            )
            lbl = Text(str(val), font_size=26, color=WHITE)
            cells.append(VGroup(sq, lbl))
        return cells


class QuickSortScene(Scene):
    """Visual quick sort using Lomuto partition. Pivot = last element of
    the active subarray; pointers i (boundary of <pivot region) and j
    (current scan position) are shown explicitly. Recurses on left and
    right halves; finalized pivots go green."""

    PIVOT_COLOR  = "#A855F7"   # purple
    LESS_COLOR   = "#3B82F6"   # blue (already-classified-as-less)
    NEUTRAL      = BLUE_E
    SCAN_COLOR   = YELLOW
    SORTED_COLOR = GREEN_E

    def construct(self):
        self.camera.background_color = "#0d1117"
        params = _load_params()
        arr = list(params.get("array", [3, 7, 1, 5, 9, 2, 8, 4]))
        caption = params.get("caption", "")

        # Constrain to 2-8 elements — keeps the per-step animation count
        # bounded so the whole render fits in ~25 seconds.
        n = len(arr)
        if n < 2:
            arr = [3, 7, 1, 5, 9, 2, 8, 4]; n = 8
        if n > 8:
            arr = arr[:8]; n = 8

        title = Text("Quick Sort — partition around pivot", font_size=28).to_edge(UP, buff=0.4)
        self.play(FadeIn(title))

        cells = self._make_cells(arr)
        row = VGroup(*cells).arrange(RIGHT, buff=0.15).center()
        self.play(FadeIn(row))
        self.wait(0.3)

        sorted_idxs: set[int] = set()
        self._quicksort(arr, cells, 0, n - 1, sorted_idxs)

        # Catch any cells we never touched (shouldn't happen, but be safe)
        leftover = [cells[k] for k in range(n) if k not in sorted_idxs]
        if leftover:
            self.play(*[c[0].animate.set_fill(self.SORTED_COLOR, opacity=0.7) for c in leftover],
                      run_time=0.3)

        if caption:
            cap = Text(caption, font_size=20, color=GRAY_B).to_edge(DOWN, buff=0.4)
            self.play(FadeIn(cap))

        self.wait(1)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)

    # ---- recursive partition driver -------------------------------------

    def _quicksort(self, arr, cells, lo, hi, sorted_idxs):
        if lo > hi:
            return
        if lo == hi:
            if lo not in sorted_idxs:
                self.play(cells[lo][0].animate.set_fill(self.SORTED_COLOR, opacity=0.7),
                          run_time=0.2)
                sorted_idxs.add(lo)
            return

        # Highlight the pivot (last element of the active range)
        pivot_val = arr[hi]
        self.play(cells[hi][0].animate.set_fill(self.PIVOT_COLOR, opacity=0.85),
                  run_time=0.3)

        # j-pointer label rides above the scan; i-pointer label rides below
        # the boundary of the <pivot region. i starts as "lo - 1" (empty),
        # so we don't materialize its label until i first becomes valid.
        j_label = Text("j", font_size=20, color=self.SCAN_COLOR)\
            .next_to(cells[lo], UP, buff=0.15)
        self.play(FadeIn(j_label))
        i_label: Text | None = None

        i = lo - 1
        for j in range(lo, hi):
            if j > lo:
                self.play(j_label.animate.next_to(cells[j], UP, buff=0.15), run_time=0.18)

            self.play(cells[j][0].animate.set_fill(self.SCAN_COLOR, opacity=0.6),
                      run_time=0.15)

            if arr[j] < pivot_val:
                i += 1
                if i_label is None:
                    i_label = Text("i", font_size=20, color=ORANGE)\
                        .next_to(cells[i], DOWN, buff=0.15)
                    self.play(FadeIn(i_label), run_time=0.18)
                else:
                    self.play(i_label.animate.next_to(cells[i], DOWN, buff=0.15),
                              run_time=0.18)

                if i != j:
                    pos_i = cells[i].get_center().copy()
                    pos_j = cells[j].get_center().copy()
                    # Lift i then arc them past each other so they don't clip
                    self.play(
                        cells[i].animate.shift(UP * 0.5),
                        cells[j].animate.shift(DOWN * 0.5),
                        run_time=0.18,
                    )
                    self.play(
                        cells[i].animate.move_to([pos_j[0], pos_i[1] + 0.5, 0]),
                        cells[j].animate.move_to([pos_i[0], pos_j[1] - 0.5, 0]),
                        run_time=0.3,
                    )
                    self.play(
                        cells[i].animate.move_to(pos_j),
                        cells[j].animate.move_to(pos_i),
                        run_time=0.18,
                    )
                    cells[i], cells[j] = cells[j], cells[i]
                    arr[i], arr[j] = arr[j], arr[i]

                self.play(cells[i][0].animate.set_fill(self.LESS_COLOR, opacity=0.5),
                          run_time=0.13)
            else:
                # ≥ pivot — return to neutral so the scan reads cleanly
                self.play(cells[j][0].animate.set_fill(self.NEUTRAL, opacity=0.5),
                          run_time=0.13)

        # Place pivot in its final slot: swap cells[i+1] with cells[hi]
        i += 1
        if i != hi:
            pos_i = cells[i].get_center().copy()
            pos_p = cells[hi].get_center().copy()
            self.play(
                cells[i].animate.move_to(pos_p),
                cells[hi].animate.move_to(pos_i),
                run_time=0.4,
            )
            cells[i], cells[hi] = cells[hi], cells[i]
            arr[i], arr[hi] = arr[hi], arr[i]

        # Pivot is now at index i — finalize it
        finalize = [cells[i][0].animate.set_fill(self.SORTED_COLOR, opacity=0.75),
                    FadeOut(j_label)]
        if i_label is not None:
            finalize.append(FadeOut(i_label))
        self.play(*finalize, run_time=0.3)
        sorted_idxs.add(i)

        # Reset any cells in the active range that aren't sorted yet
        reset = [cells[k] for k in range(lo, hi + 1) if k not in sorted_idxs]
        if reset:
            self.play(*[c[0].animate.set_fill(self.NEUTRAL, opacity=0.5) for c in reset],
                      run_time=0.18)

        # Recurse on the two halves
        self._quicksort(arr, cells, lo, i - 1, sorted_idxs)
        self._quicksort(arr, cells, i + 1, hi, sorted_idxs)

    def _make_cells(self, arr):
        cells = []
        for val in arr:
            sq = Square(side_length=0.85, fill_color=BLUE_E, fill_opacity=0.5,
                        stroke_color=WHITE, stroke_width=2)
            lbl = Text(str(val), font_size=26, color=WHITE)
            cells.append(VGroup(sq, lbl))
        return cells
