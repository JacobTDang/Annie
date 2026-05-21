"""
Reusable visual primitives for DSA scenes.

Each primitive is a small self-contained class that builds Manim mobjects.
Primitives DO NOT call `self.play(...)` — they return mobjects that the
calling scene composes into animations. This makes them reusable, testable,
and easy to combine.

Shared color palette (use these consistently across all DSA scenes):
    DEFAULT_CELL = "#1a3a5c"    deep blue, unexamined cells
    HILITE       = YELLOW        currently being examined
    KEEP         = GREEN         matched / kept / answer
    REJECT       = RED           briefly, then faded back to default
    PTR_L        = GREEN
    PTR_R        = RED
    PTR_M        = YELLOW
    PTR_SLOW     = BLUE
    PTR_FAST     = ORANGE
"""
import json
import math
import os

from manim import *

# ---------------------------------------------------------------------------
# Shared palette
# ---------------------------------------------------------------------------
DEFAULT_CELL = "#1a3a5c"
HILITE       = YELLOW
KEEP         = GREEN
REJECT       = RED
PANEL_BG     = "#0d1117"

PTR_COLORS = {
    "L":     GREEN,
    "R":     RED,
    "M":     YELLOW,
    "slow":  BLUE,
    "fast":  ORANGE,
    "i":     YELLOW,
    "j":     "#8b5cf6",  # purple
}


# ---------------------------------------------------------------------------
# Shared helpers (parameter loading / title card / caption / result box)
# Re-implemented here so primitives module is self-contained.
# ---------------------------------------------------------------------------

def _strip_dict_nulls(obj):
    """Drop None values from dict keys recursively. Agents occasionally
    emit explicit ``null`` in JSON params, which breaks downstream code
    like ``int(p.get("n", 8))`` (the `.get` returns None, not the
    default). Stripping at the boundary makes defaults work as written.
    List elements keep their None entries so list shapes stay intact."""
    if isinstance(obj, dict):
        return {k: _strip_dict_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_dict_nulls(v) for v in obj]
    return obj


def load_params() -> dict:
    job_id = os.environ.get("MANIM_JOB_ID")
    if job_id:
        temp_dir = os.environ.get("MANIM_TEMP_DIR", os.path.join("media", "temp"))
        path = os.path.join(temp_dir, f"{job_id}.json")
        if os.path.exists(path):
            with open(path) as f:
                return _strip_dict_nulls(json.load(f))
    return {}


# ---------------------------------------------------------------------------
# Chapter recorder — semantic step markers for the video player
# ---------------------------------------------------------------------------

class ChapterRecorder:
    """Records (time_s, label) markers as a scene animates.

    DSA scene classes mix this in and call ``self.mark_chapter("…")`` at
    semantic boundaries — e.g. each DP cell fill. After ``construct()``
    finishes, ``flush_chapters()`` writes the list to the path in the
    ``LUMEN_CHAPTERS_OUT`` env var (set by the worker per render).

    Missing env var, write failures, or import errors all degrade
    silently — the underlying scene still completes normally.
    """

    def mark_chapter(self, label: str) -> None:
        if not hasattr(self, "_chapters"):
            self._chapters: list = []
        # Manim exposes the scene clock at self.renderer.time. Default to
        # 0.0 if the renderer isn't attached yet (very early calls).
        renderer = getattr(self, "renderer", None)
        t = getattr(renderer, "time", 0.0) if renderer else 0.0
        try:
            t = float(t)
        except (TypeError, ValueError):
            t = 0.0
        self._chapters.append({"t": t, "label": str(label)})

    def flush_chapters(self) -> None:
        out = os.environ.get("LUMEN_CHAPTERS_OUT")
        if not out:
            return
        chapters = getattr(self, "_chapters", None)
        if not chapters:
            return
        try:
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(chapters, fh)
        except OSError:
            # Never break the render over a chapter-write failure
            pass


def show_title_card(scene, text: str):
    import textwrap as _tw
    wrapped = _tw.fill(text, width=52)
    n = len(text)
    size = 28 if n < 45 else (24 if n < 70 else 20)
    card = Text(wrapped, font_size=size, color=WHITE, line_spacing=1.2)
    if card.width > 12.5:
        card.scale(12.5 / card.width)
    card.center()
    scene.play(FadeIn(card), run_time=0.35)
    scene.wait(1.4)
    scene.play(FadeOut(card), run_time=0.35)


def caption_strip(text: str) -> VGroup:
    """White-on-dark subtitle strip pinned at the bottom."""
    import textwrap as _tw
    wrapped = _tw.fill(text, width=72)
    bg  = Rectangle(width=14.5, height=0.65, fill_color=BLACK,
                    fill_opacity=0.82, stroke_width=0).to_edge(DOWN, buff=0)
    txt = Text(wrapped, font_size=21, color=WHITE).to_edge(DOWN, buff=0.13)
    if txt.width > 13.5:
        txt.scale(13.5 / txt.width)
    return VGroup(bg, txt)


def result_box(text: str, font_size: int = 28, use_text: bool = True) -> VGroup:
    """Boxed result label. Pass use_text=False for MathTex content."""
    if use_text:
        label = Text(text, font_size=font_size, color=WHITE)
    else:
        label = MathTex(text, font_size=font_size)
    box = SurroundingRectangle(
        label, color=WHITE, fill_color=BLACK,
        fill_opacity=0.75, buff=0.18, corner_radius=0.1,
    )
    return VGroup(box, label)


def action_text(msg: str, font_size: int = 22) -> VGroup:
    """Bottom-anchored action log line on a thin dark strip.

    Sits clearly above the caption_strip (which is pinned at the bottom edge
    with bg height 0.65) so their backgrounds do not overlap.
    """
    txt = Text(msg, font_size=font_size, color=WHITE)
    if txt.width > 13.0:
        txt.scale(13.0 / txt.width)
    bg = Rectangle(
        width=max(txt.width + 0.6, 4),
        height=txt.height + 0.25,
        fill_color=BLACK, fill_opacity=0.7, stroke_width=0,
    )
    grp = VGroup(bg, txt).to_edge(DOWN, buff=0.95)
    return grp


# ---------------------------------------------------------------------------
# Primitive 1 — ArrayStrip
# ---------------------------------------------------------------------------

class ArrayStrip:
    """
    A horizontal row of cells (Square + Text). Adaptive size based on length.

    Construction:
        strip = ArrayStrip([1, 3, 5, 7], position=UP*0.5)

    Properties:
        .cells       — list[VGroup(square, text)]
        .vgroup      — the whole row as a VGroup
        .indices     — VGroup of small index labels below cells

    Methods (all return mobjects suitable for self.play(...)):
        .anim_set_fill(i, color, opacity=0.7)
        .anim_set_value(i, new_value)
        .flash(i, color=YELLOW, scale=1.2)
        .cell_top(i)    -> point
        .cell_bottom(i) -> point
        .cell_center(i) -> point
    """

    def __init__(self, values: list, position=ORIGIN,
                 cell_size: float = None, with_indices: bool = True):
        self.values = list(values)
        n = len(values)

        if cell_size is None:
            cell_size = (1.0 if n <= 4 else
                         0.85 if n <= 7 else
                         0.70 if n <= 10 else
                         max(0.50, 9.0 / n))
        self.cell_size = cell_size
        font = max(16, int(24 * cell_size))

        self.cells = []
        for v in values:
            sq = Square(side_length=cell_size,
                        fill_color=DEFAULT_CELL, fill_opacity=0.70,
                        stroke_color=WHITE, stroke_width=2)
            lbl = Text(str(v), font_size=font, color=WHITE)
            cell = VGroup(sq, lbl)
            self.cells.append(cell)

        self.vgroup = VGroup(*self.cells).arrange(RIGHT, buff=0.10).move_to(position)

        self.indices = VGroup()
        if with_indices:
            for i, c in enumerate(self.cells):
                ix = Text(str(i), font_size=max(13, int(15 * cell_size)),
                          color=GRAY).next_to(c, DOWN, buff=0.05)
                self.indices.add(ix)

    def anim_set_fill(self, i: int, color, opacity: float = 0.75):
        return self.cells[i][0].animate.set_fill(color, opacity=opacity)

    def anim_set_value(self, i: int, new_value):
        new_lbl = Text(str(new_value),
                       font_size=max(16, int(24 * self.cell_size)),
                       color=WHITE).move_to(self.cells[i][1].get_center())
        return Transform(self.cells[i][1], new_lbl)

    def flash(self, i: int, color=YELLOW, scale: float = 1.2):
        return Indicate(self.cells[i][0], color=color, scale_factor=scale)

    def cell_top(self, i: int):
        return self.cells[i].get_top()

    def cell_bottom(self, i: int):
        return self.cells[i].get_bottom()

    def cell_center(self, i: int):
        return self.cells[i].get_center()

    def set_default(self, i: int):
        """Synchronously reset a cell's fill (no animation)."""
        self.cells[i][0].set_fill(DEFAULT_CELL, opacity=0.70)


# ---------------------------------------------------------------------------
# Primitive 2 — Pointer
# ---------------------------------------------------------------------------

class Pointer:
    """
    A labeled colored arrow pointing UP at cells (placed below).

    Pointer("L", color=GREEN, role="below")  -> arrow points up at cell from below
    Pointer("M", color=YELLOW, role="below_lower")  -> placed lower (for L/M/R stacks)

    Methods:
        .place_below(strip, idx, extra_down=0)
        .anim_move_to(strip, idx, extra_down=0)
        .vgroup       -> the mobject
    """

    def __init__(self, label: str, color=YELLOW, label_size: int = 16):
        self.label = label
        self.color = color
        self._arrow = Arrow(DOWN * 0.45, ORIGIN, color=color, buff=0,
                            max_tip_length_to_length_ratio=0.40, stroke_width=2.5)
        self._lbl = Text(label, font_size=label_size, color=color, weight=BOLD)
        self._lbl.next_to(self._arrow.get_start(), DOWN, buff=0.04)
        self.vgroup = VGroup(self._arrow, self._lbl)

    def place_below(self, strip: ArrayStrip, idx: int, extra_down: float = 0.0):
        target = strip.cell_bottom(idx) + DOWN * (0.30 + extra_down)
        self.vgroup.move_to(target)
        return self

    def anim_move_to(self, strip: ArrayStrip, idx: int, extra_down: float = 0.0):
        target = strip.cell_bottom(idx) + DOWN * (0.30 + extra_down)
        return self.vgroup.animate.move_to(target)


# ---------------------------------------------------------------------------
# Primitive 3 — HighlightZone
# ---------------------------------------------------------------------------

class HighlightZone:
    """
    A SurroundingRectangle around contiguous cells of an ArrayStrip.
    Used for sliding windows.

    Methods:
        .wrap(strip, start, end, color=YELLOW)  -> the rectangle
        .anim_to(strip, start, end)             -> transform animation
    """

    def __init__(self, strip: ArrayStrip, start: int, end: int,
                 color=YELLOW, stroke_width: float = 2.5):
        self.strip = strip
        self.color = color
        self.stroke_width = stroke_width
        self._rect = self._build(start, end)

    @property
    def rect(self):
        return self._rect

    def _build(self, start: int, end: int):
        return SurroundingRectangle(
            VGroup(*self.strip.cells[start:end + 1]),
            color=self.color, buff=0.08, corner_radius=0.06,
            stroke_width=self.stroke_width,
        )

    def anim_to(self, start: int, end: int):
        new_rect = self._build(start, end)
        return Transform(self._rect, new_rect)


# ---------------------------------------------------------------------------
# Primitive 4 — HashMapPanel
# ---------------------------------------------------------------------------

class HashMapPanel:
    """
    Sidebar showing key:value entries that update over time.

    Constructor pins it to a corner; entries appear as rows.
    Auto-clamps width to avoid screen overflow.

    Methods (return list of animations to play together):
        .anim_set(k, v) -> list of Animations to update display
        .anim_delete(k) -> list of Animations
        .anim_flash(k)  -> Indicate animation on a key
        .vgroup         -> the whole panel
    """

    def __init__(self, anchor=UR, title: str = "HashMap",
                 max_rows: int = 8):
        self.anchor = anchor
        self.title_text = title
        self.max_rows = max_rows
        self._entries = {}      # key -> VGroup(key_text, sep, val_text)
        self._title = Text(title, font_size=20, color=YELLOW, weight=BOLD)
        self._bg    = Rectangle(width=2.6, height=0.7,
                                 fill_color=PANEL_BG, fill_opacity=0.92,
                                 stroke_color=GRAY, stroke_width=1.2)
        self._bg.surround(self._title, buff=0.18)
        self.vgroup = VGroup(self._bg, self._title)
        self.vgroup.to_corner(anchor, buff=0.3)

    def _make_row(self, k, v):
        k_txt = Text(str(k), font_size=18, color=WHITE)
        sep   = Text(":", font_size=18, color=GRAY)
        v_txt = Text(str(v), font_size=18, color=GREEN)
        row = VGroup(k_txt, sep, v_txt).arrange(RIGHT, buff=0.12)
        return row, k_txt, v_txt

    def _rebuild_layout(self):
        """Recompute panel layout: title on top, rows beneath."""
        rows = list(self._entries.values())
        if not rows:
            content = self._title
        else:
            stacked = VGroup(self._title, *rows).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
            content = stacked
        # Build new bg around content
        new_bg = Rectangle(
            width=max(content.width + 0.4, 2.6),
            height=content.height + 0.4,
            fill_color=PANEL_BG, fill_opacity=0.92,
            stroke_color=GRAY, stroke_width=1.2,
        ).move_to(content.get_center())
        return new_bg, content

    def anim_set(self, key, value):
        """Add or update key. Returns animations."""
        anims = []
        if key in self._entries:
            row = self._entries[key]
            new_v = Text(str(value), font_size=18, color=GREEN).move_to(row[2].get_center())
            anims.append(Transform(row[2], new_v))
        else:
            row, _, _ = self._make_row(key, value)
            self._entries[key] = row
            anims.append(FadeIn(row, shift=LEFT * 0.2))
        # Re-anchor entire panel after changes
        self._reanchor()
        return anims

    def _reanchor(self):
        """Rebuild background to fit new content and pin to corner."""
        rows = list(self._entries.values())
        if rows:
            content = VGroup(self._title, *rows).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
        else:
            content = self._title

        new_bg = Rectangle(
            width=max(content.width + 0.4, 2.6),
            height=content.height + 0.4,
            fill_color=PANEL_BG, fill_opacity=0.92,
            stroke_color=GRAY, stroke_width=1.2,
        )
        # Position: corner-anchored
        new_grp = VGroup(new_bg, content)
        new_grp.to_corner(self.anchor, buff=0.3)

        # Mutate existing bg & vgroup to match
        self._bg.become(new_bg)
        self.vgroup.move_to(new_grp.get_center())

    def anim_delete(self, key):
        if key not in self._entries:
            return []
        row = self._entries.pop(key)
        anim = FadeOut(row, shift=RIGHT * 0.2)
        self._reanchor()
        return [anim]

    def anim_flash(self, key, color=YELLOW):
        if key not in self._entries:
            return []
        return [Indicate(self._entries[key], color=color, scale_factor=1.15)]


# ---------------------------------------------------------------------------
# Primitive 5 — StatePanel
# ---------------------------------------------------------------------------

class StatePanel:
    """
    Sidebar for variable values (like a debugger watch).

    Methods:
        .anim_set(name, val, color=WHITE)  -> animations
        .vgroup                              -> the panel
    """

    def __init__(self, anchor=UL, title: str = "State"):
        self.anchor = anchor
        self.title_text = title
        self._entries = {}
        self._title = Text(title, font_size=20, color=YELLOW, weight=BOLD)
        self._bg = Rectangle(width=2.4, height=0.7,
                              fill_color=PANEL_BG, fill_opacity=0.92,
                              stroke_color=GRAY, stroke_width=1.2)
        self._bg.surround(self._title, buff=0.18)
        self.vgroup = VGroup(self._bg, self._title)
        self.vgroup.to_corner(anchor, buff=0.3)

    def _make_row(self, name, val, color):
        n_txt = Text(f"{name} =", font_size=18, color=GRAY)
        v_txt = Text(str(val), font_size=18, color=color, weight=BOLD)
        row = VGroup(n_txt, v_txt).arrange(RIGHT, buff=0.10)
        return row, v_txt

    def _reanchor(self):
        rows = list(self._entries.values())
        if rows:
            content = VGroup(self._title, *[r[0] for r in rows]).arrange(
                DOWN, aligned_edge=LEFT, buff=0.10)
        else:
            content = self._title
        new_bg = Rectangle(
            width=max(content.width + 0.4, 2.4),
            height=content.height + 0.4,
            fill_color=PANEL_BG, fill_opacity=0.92,
            stroke_color=GRAY, stroke_width=1.2,
        )
        new_grp = VGroup(new_bg, content)
        new_grp.to_corner(self.anchor, buff=0.3)
        self._bg.become(new_bg)
        self.vgroup.move_to(new_grp.get_center())

    def anim_set(self, name: str, val, color=WHITE):
        anims = []
        if name in self._entries:
            old_row, old_v = self._entries[name]
            new_v = Text(str(val), font_size=18, color=color, weight=BOLD)
            new_v.move_to(old_v.get_center())
            anims.append(Transform(old_v, new_v))
        else:
            row, v_txt = self._make_row(name, val, color)
            self._entries[name] = (row, v_txt)
            anims.append(FadeIn(row, shift=LEFT * 0.2))
        self._reanchor()
        return anims


# ---------------------------------------------------------------------------
# Primitive 6 — ComparisonMarker
# ---------------------------------------------------------------------------

class ComparisonMarker:
    """
    A symbol shown between two cells indicating a comparison result.
    Usage:
        marker = ComparisonMarker.between(strip, i, j, "==", color=GREEN)
        scene.play(FadeIn(marker.vgroup))

    Symbols supported: "==", "!=", "<", ">", "<=", ">=", "+", "->"
    """

    def __init__(self, vgroup):
        self.vgroup = vgroup

    @classmethod
    def between(cls, strip: ArrayStrip, i: int, j: int,
                symbol: str = "==", color=YELLOW):
        center_i = strip.cell_center(i)
        center_j = strip.cell_center(j)
        midpoint = (center_i + center_j) / 2 + UP * (strip.cell_size + 0.3)

        sym_text = symbol.replace("==", "=").replace("!=", "≠").replace(
            "<=", "≤").replace(">=", "≥").replace("->", "→")
        txt = Text(sym_text, font_size=28, color=color, weight=BOLD)
        bg = Circle(radius=0.25, color=color, fill_color=BLACK,
                     fill_opacity=0.9, stroke_width=2)
        grp = VGroup(bg, txt).move_to(midpoint)
        return cls(grp)


# ---------------------------------------------------------------------------
# Primitive 7 — StackWidget
# ---------------------------------------------------------------------------

class StackWidget:
    """
    Vertical stack of values. Items pushed at the top.

    Methods:
        .anim_push(val, color=BLUE_D)  -> tuple (item_mob, animations_list)
        .anim_pop()                    -> animations list (item flies up + fades)
        .top_value()
        .vgroup                        -> container + items
    """

    def __init__(self, position=ORIGIN, max_visible: int = 7,
                 cell_w: float = 1.4, cell_h: float = 0.55,
                 title: str = "Stack"):
        self.position = position
        self.max_visible = max_visible
        self.cell_w = cell_w
        self.cell_h = cell_h
        self._items = []  # list of (value, vgroup)
        self._container = Rectangle(
            width=cell_w + 0.18, height=max_visible * cell_h + 0.18,
            color=WHITE, stroke_width=2, fill_opacity=0,
        ).move_to(position)
        self._title = Text(title, font_size=18, color=GRAY).next_to(
            self._container, UP, buff=0.15)
        self.vgroup = VGroup(self._container, self._title)

    def _slot_y(self, idx: int) -> float:
        """Y-coord for stack slot idx (0 = bottom)."""
        return self._container.get_bottom()[1] + self.cell_h / 2 + 0.08 + idx * self.cell_h

    def _make_item(self, val, color=BLUE_D):
        rect = Rectangle(width=self.cell_w - 0.08, height=self.cell_h - 0.06,
                          fill_color=color, fill_opacity=0.78,
                          stroke_color=WHITE, stroke_width=1.3)
        lbl = Text(str(val), font_size=18, color=WHITE)
        return VGroup(rect, lbl)

    def anim_push(self, val, color=BLUE_D):
        item = self._make_item(val, color)
        target_y = self._slot_y(len(self._items))
        target_x = self._container.get_center()[0]
        # Item starts above the container, slides into slot
        item.move_to(np.array([target_x, target_y + 2.5, 0]))
        anim = item.animate.move_to(np.array([target_x, target_y, 0]))
        self._items.append((val, item))
        return item, [anim]

    def anim_pop(self):
        if not self._items:
            return None, []
        val, item = self._items.pop()
        # Item flies up and fades
        return val, [
            item.animate.shift(UP * 1.5 + RIGHT * 1.0),
            FadeOut(item),
        ]

    def top_value(self):
        return self._items[-1][0] if self._items else None


# ---------------------------------------------------------------------------
# Primitive 8 — DependencyArc
# ---------------------------------------------------------------------------

class DependencyArc:
    """
    Curved arrow between two cells (used for DP scenes to show dp[i] depends on dp[j]).
    """

    @staticmethod
    def above(strip: ArrayStrip, dep_idx: int, target_idx: int,
              color=TEAL, angle=-PI / 3, stroke_width: float = 2):
        return CurvedArrow(
            strip.cell_top(dep_idx) + UP * 0.05,
            strip.cell_top(target_idx) + UP * 0.05,
            color=color, angle=angle, stroke_width=stroke_width,
        )


# ---------------------------------------------------------------------------
# Primitive 9 — GridPanel  (2D matrix of cells)
# ---------------------------------------------------------------------------

class GridPanel:
    """2D grid of cells. cells[r][c] is a VGroup(square, label).

    Methods:
        .anim_set_fill(r, c, color, opacity)
        .anim_set_value(r, c, new_value)
        .flash(r, c, color, scale)
        .cell_center(r, c) -> point
    """

    def __init__(self, values, position=ORIGIN, cell_size: float = None,
                 with_indices: bool = True):
        rows = len(values)
        cols = len(values[0]) if rows else 0
        if cell_size is None:
            longest = max(rows, cols, 1)
            cell_size = 0.85 if longest <= 5 else (0.65 if longest <= 7 else 0.50)
        self.cell_size = cell_size
        self.rows, self.cols = rows, cols
        font = max(14, int(22 * cell_size))

        self.cells = []
        rows_g = []
        for r in range(rows):
            row = []
            for c in range(cols):
                sq = Square(side_length=cell_size,
                            fill_color=DEFAULT_CELL, fill_opacity=0.70,
                            stroke_color=WHITE, stroke_width=2)
                lbl = Text(str(values[r][c]), font_size=font, color=WHITE)
                row.append(VGroup(sq, lbl))
            rg = VGroup(*row).arrange(RIGHT, buff=0.06)
            rows_g.append(rg)
            self.cells.append(row)
        self.vgroup = VGroup(*rows_g).arrange(DOWN, buff=0.06).move_to(position)

        self.row_idx = VGroup()
        self.col_idx = VGroup()
        if with_indices and rows and cols:
            for r in range(rows):
                ix = Text(str(r), font_size=max(11, int(13 * cell_size)),
                          color=GRAY).next_to(self.cells[r][0], LEFT, buff=0.10)
                self.row_idx.add(ix)
            for c in range(cols):
                ix = Text(str(c), font_size=max(11, int(13 * cell_size)),
                          color=GRAY).next_to(self.cells[0][c], UP, buff=0.10)
                self.col_idx.add(ix)

    def anim_set_fill(self, r: int, c: int, color, opacity: float = 0.75):
        return self.cells[r][c][0].animate.set_fill(color, opacity=opacity)

    def anim_set_value(self, r: int, c: int, new_value):
        font = max(14, int(22 * self.cell_size))
        new_lbl = Text(str(new_value), font_size=font, color=WHITE).move_to(
            self.cells[r][c][1].get_center())
        return Transform(self.cells[r][c][1], new_lbl)

    def flash(self, r: int, c: int, color=YELLOW, scale: float = 1.18):
        return Indicate(self.cells[r][c][0], color=color, scale_factor=scale)

    def cell_center(self, r: int, c: int):
        return self.cells[r][c].get_center()

    # Edge anchors — used by GridArrow + dependency arcs so the arrowhead
    # lands on a cell's perimeter instead of overlapping its number text.
    def cell_top(self, r: int, c: int):
        return self.cells[r][c][0].get_top()

    def cell_bottom(self, r: int, c: int):
        return self.cells[r][c][0].get_bottom()

    def cell_left(self, r: int, c: int):
        return self.cells[r][c][0].get_left()

    def cell_right(self, r: int, c: int):
        return self.cells[r][c][0].get_right()

    def cell_edge(self, r: int, c: int, side: str):
        """Side-of-cell anchor by name. Accepts 'top', 'bottom', 'left',
        'right', 'center'. Unknown side falls back to center."""
        return {
            "top":    self.cell_top,
            "bottom": self.cell_bottom,
            "left":   self.cell_left,
            "right":  self.cell_right,
            "center": self.cell_center,
        }.get(side, self.cell_center)(r, c)


# ---------------------------------------------------------------------------
# Primitive 9b — GridArrow (curved dependency arrow between two grid cells)
# ---------------------------------------------------------------------------

class GridArrow:
    """Curved arrow between two cells of the same ``GridPanel``.

    Used by the 2D DP scenes to show ``dp[r][c]`` depending on
    ``dp[r-1][c]`` (vertical) / ``dp[r][c-1]`` (horizontal) /
    ``dp[r-1][c-1]`` (diagonal). The arrow auto-chooses edge anchors
    based on the relative position of the cells so the arrowhead lands
    on the perimeter rather than the cell text.

    Returns a Manim ``CurvedArrow``. Color + label optional.
    """

    @staticmethod
    def between(grid: "GridPanel", from_rc, to_rc,
                color=TEAL, stroke_width: float = 2, label: str | None = None):
        from_r, from_c = from_rc
        to_r, to_c = to_rc

        # Pick edge anchors based on relative position. Vertical arrows
        # leave the bottom of the source and enter the top of the target
        # (or vice versa); diagonal arrows use corners.
        if from_r < to_r and from_c == to_c:
            start = grid.cell_bottom(from_r, from_c)
            end   = grid.cell_top(to_r, to_c)
        elif from_r > to_r and from_c == to_c:
            start = grid.cell_top(from_r, from_c)
            end   = grid.cell_bottom(to_r, to_c)
        elif from_r == to_r and from_c < to_c:
            start = grid.cell_right(from_r, from_c)
            end   = grid.cell_left(to_r, to_c)
        elif from_r == to_r and from_c > to_c:
            start = grid.cell_left(from_r, from_c)
            end   = grid.cell_right(to_r, to_c)
        else:
            # Diagonal — use corners
            start = grid.cell_center(from_r, from_c)
            end   = grid.cell_center(to_r, to_c)

        # Small curve so adjacent-cell arrows don't draw through the
        # cell content. Diagonal arrows use a smaller angle.
        angle = -PI / 6 if (from_r == to_r or from_c == to_c) else -PI / 8
        arrow = CurvedArrow(start, end, color=color, angle=angle,
                            stroke_width=stroke_width)
        if label:
            txt = Text(str(label), font_size=max(10, int(11 * grid.cell_size)),
                       color=color).next_to(arrow.point_from_proportion(0.5),
                                              UP, buff=0.04)
            return VGroup(arrow, txt)
        return arrow


# ---------------------------------------------------------------------------
# Primitive 10 — BinaryTreePanel  (complete binary tree)
# ---------------------------------------------------------------------------

class BinaryTreePanel:
    """Complete-binary-tree layout. Node at index i has children 2i+1, 2i+2.

    Methods:
        .anim_set_value(i, new_value)
        .anim_set_fill(i, color, opacity)
        .flash(i, color, scale)
        .node_pos(i) -> point
        .edge_between(parent_i, child_i) -> Line
    """

    def __init__(self, values, position=ORIGIN, node_radius: float = 0.32,
                 level_gap: float = 0.95):
        self.values = list(values)
        n = len(self.values)
        self.n = n
        self.node_radius = node_radius
        self.level_gap = level_gap

        if n == 0:
            self.nodes = []
            self.edges = []
            self.vgroup = VGroup()
            return

        import math
        levels = int(math.floor(math.log2(n))) + 1
        positions = []
        font = max(14, int(20 * (node_radius / 0.32)))
        max_level_w = 2 ** (levels - 1)
        spread = max(4.5, 0.6 * max_level_w)

        self.nodes = []
        for i in range(n):
            level = int(math.floor(math.log2(i + 1)))
            count_at_level = 2 ** level
            idx_in_level = i - (count_at_level - 1)
            x = -spread / 2 + (spread / max(count_at_level, 1)) * (idx_in_level + 0.5)
            y = -level * level_gap
            positions.append((x, y))
            circle = Circle(radius=node_radius, color=WHITE, stroke_width=2,
                            fill_color=DEFAULT_CELL, fill_opacity=0.7)
            lbl = Text(str(self.values[i]), font_size=font, color=WHITE)
            node = VGroup(circle, lbl).move_to([x, y, 0])
            self.nodes.append(node)

        self.edges = []
        edge_objs = []
        for i in range(n):
            for child in (2 * i + 1, 2 * i + 2):
                if child < n:
                    e = Line(self.nodes[i].get_bottom(),
                             self.nodes[child].get_top(),
                             color=GRAY, stroke_width=2)
                    self.edges.append((i, child, e))
                    edge_objs.append(e)

        self.vgroup = VGroup(*edge_objs, *self.nodes).move_to(position)

    def anim_set_value(self, i: int, new_value):
        font = max(14, int(20 * (self.node_radius / 0.32)))
        new_lbl = Text(str(new_value), font_size=font, color=WHITE).move_to(
            self.nodes[i][1].get_center())
        return Transform(self.nodes[i][1], new_lbl)

    def anim_set_fill(self, i: int, color, opacity: float = 0.75):
        return self.nodes[i][0].animate.set_fill(color, opacity=opacity)

    def flash(self, i: int, color=YELLOW, scale: float = 1.25):
        return Indicate(self.nodes[i][0], color=color, scale_factor=scale)

    def node_pos(self, i: int):
        return self.nodes[i].get_center()


# ---------------------------------------------------------------------------
# Primitive 11 — RecursionTree  (dynamically growing tree)
# ---------------------------------------------------------------------------

class RecursionTree:
    """A tree that grows as DFS recurses.

    The scene calls .anim_spawn_child(parent_id, label) to grow the tree, and
    .anim_fade_subtree(node_id) to abandon a branch.

    Layout: simple breadth-aware spreading at each call to spawn — children of
    a parent share that parent's allocated x-range.
    """

    def __init__(self, root_label: str = "[]", position=ORIGIN,
                 width: float = 10.0, level_gap: float = 0.95,
                 node_radius: float = 0.30):
        self.width = width
        self.level_gap = level_gap
        self.node_radius = node_radius
        self.center = position

        self.nodes = {}    # id -> VGroup(circle, text)
        self.edges = {}    # (parent_id, child_id) -> Line
        self.parent = {0: None}
        self.children = {0: []}
        self.depth = {0: 0}
        self.x_span = {0: (-width / 2, width / 2)}
        self.next_id = 1

        font = max(13, int(18 * (node_radius / 0.30)))
        self.root = self._make_node(root_label, font, 0, 0)
        self.nodes[0] = self.root
        self.vgroup = VGroup(self.root)

    def _make_node(self, label, font, x, y):
        c = Circle(radius=self.node_radius, color=WHITE, stroke_width=2,
                   fill_color=DEFAULT_CELL, fill_opacity=0.7)
        t = Text(str(label), font_size=font, color=WHITE)
        if t.width > 2 * self.node_radius - 0.05:
            t.scale((2 * self.node_radius - 0.05) / max(t.width, 0.001))
        return VGroup(c, t).move_to([x + self.center[0], y + self.center[1], 0])

    def anim_spawn_child(self, parent_id: int, label: str):
        """Spawn a child node under parent_id. Returns (new_id, [animations])."""
        nid = self.next_id
        self.next_id += 1
        d = self.depth[parent_id] + 1
        self.depth[nid] = d
        self.parent[nid] = parent_id
        self.children[nid] = []
        self.children[parent_id].append(nid)

        # Distribute parent's x-span among its known children
        kids = self.children[parent_id]
        x_lo, x_hi = self.x_span[parent_id]
        slot_w = (x_hi - x_lo) / max(len(kids), 1)
        for k_idx, k in enumerate(kids):
            self.x_span[k] = (x_lo + k_idx * slot_w, x_lo + (k_idx + 1) * slot_w)
        # Recompute existing kid positions too (so they don't bunch as new ones spawn)
        moves = []
        font = max(13, int(18 * (self.node_radius / 0.30)))
        for k in kids:
            kx = (self.x_span[k][0] + self.x_span[k][1]) / 2
            ky = -self.depth[k] * self.level_gap
            target_pt = [kx + self.center[0], ky + self.center[1], 0]
            if k in self.nodes:
                moves.append(self.nodes[k].animate.move_to(target_pt))
            else:
                self.nodes[k] = self._make_node(label, font, kx, ky)
                moves.append(FadeIn(self.nodes[k], scale=0.5))
                self.vgroup.add(self.nodes[k])
                edge = Line(self.nodes[parent_id].get_bottom(),
                            self.nodes[k].get_top(),
                            color=GRAY, stroke_width=2)
                self.edges[(parent_id, k)] = edge
                self.vgroup.add(edge)
                moves.append(Create(edge))
        return nid, moves

    def anim_fade_subtree(self, node_id: int):
        """Fade out a node and all its descendants."""
        anims = []
        stack = [node_id]
        while stack:
            n = stack.pop()
            if n in self.nodes:
                anims.append(FadeOut(self.nodes[n]))
            for k in self.children.get(n, []):
                stack.append(k)
                if (n, k) in self.edges:
                    anims.append(FadeOut(self.edges[(n, k)]))
        return anims


# ---------------------------------------------------------------------------
# Primitive 12 — IntervalBars  (number line with horizontal bars)
# ---------------------------------------------------------------------------

class IntervalBars:
    """Number line + horizontal bars for each interval [start, end].

    Methods:
        .bars[i]            — Rectangle for interval i
        .anim_set_color(i, color)
        .anim_merge(i, j)   — extend bar i to cover j, fade j out
        .x_for(value)       — point on number line
    """

    def __init__(self, intervals, position=ORIGIN, axis_width: float = 10.0,
                 axis_height: float = 0.0, padding: float = 1.0):
        self.intervals = [list(iv) for iv in intervals]
        if not self.intervals:
            self.x_min, self.x_max = 0, 1
        else:
            self.x_min = min(iv[0] for iv in self.intervals) - padding
            self.x_max = max(iv[1] for iv in self.intervals) + padding
        self.axis_width = axis_width

        self.axis = NumberLine(
            x_range=[self.x_min, self.x_max, max(1, (self.x_max - self.x_min) // 10 or 1)],
            length=axis_width,
            include_numbers=True,
            font_size=18,
            color=GRAY,
        )

        self.bars = []
        bar_h = 0.32
        offset_per = 0.42
        for i, (s, e) in enumerate(self.intervals):
            x_s = self.axis.n2p(s)[0]
            x_e = self.axis.n2p(e)[0]
            w = max(x_e - x_s, 0.05)
            color = [BLUE, TEAL, PURPLE, ORANGE][i % 4]
            rect = Rectangle(width=w, height=bar_h, color=color,
                             fill_color=color, fill_opacity=0.55, stroke_width=2)
            rect.move_to([(x_s + x_e) / 2, (i % 3 + 1) * offset_per, 0])
            self.bars.append(rect)

        self.vgroup = VGroup(self.axis, *self.bars).move_to(position)

    def anim_set_color(self, i: int, color):
        return self.bars[i].animate.set_color(color).set_fill(color, opacity=0.7)

    def anim_merge(self, i: int, j: int, new_end: float):
        """Extend bar i to span up to new_end, fade out bar j."""
        x_s = self.bars[i].get_left()[0]
        x_e = self.axis.n2p(new_end)[0]
        new_w = max(x_e - x_s, 0.05)
        new_rect = Rectangle(width=new_w, height=self.bars[i].height,
                             color=GREEN, fill_color=GREEN, fill_opacity=0.7,
                             stroke_width=2)
        new_rect.move_to([(x_s + x_e) / 2, self.bars[i].get_center()[1], 0])
        return [Transform(self.bars[i], new_rect), FadeOut(self.bars[j])]

    def x_for(self, value):
        return self.axis.n2p(value)


# ---------------------------------------------------------------------------
# Primitive 13 — DoublyLinkedListPanel
# ---------------------------------------------------------------------------

class DoublyLinkedListPanel:
    """Horizontal cells with prev/next arrows + head/tail markers.

    Internal state mirrors a real DLL: keys hashable -> {key, val, prev, next}.

    Methods:
        .anim_add_to_head(key, val)        -> animations
        .anim_remove(key)                   -> animations
        .anim_move_to_head(key)             -> animations
        .anim_flash(key, color)             -> animations
    """

    def __init__(self, position=ORIGIN, cell_w: float = 1.1, cell_h: float = 0.7,
                 max_visible: int = 5):
        self.position = position
        self.cell_w = cell_w
        self.cell_h = cell_h
        self.max_visible = max_visible

        self._order = []          # list of keys, head -> tail
        self._cells = {}          # key -> VGroup(rect, label)
        self.vgroup = VGroup()

        self.head_lbl = Text("head", font_size=14, color=GREEN_C)
        self.tail_lbl = Text("tail", font_size=14, color=RED_C)
        self.vgroup.add(self.head_lbl, self.tail_lbl)
        self._reposition_labels()

    def _make_cell(self, key, val):
        rect = Rectangle(width=self.cell_w, height=self.cell_h,
                         color=WHITE, stroke_width=2,
                         fill_color=DEFAULT_CELL, fill_opacity=0.7)
        txt = Text(f"{key}:{val}", font_size=16, color=WHITE)
        if txt.width > self.cell_w - 0.15:
            txt.scale((self.cell_w - 0.15) / max(txt.width, 0.001))
        return VGroup(rect, txt)

    def _layout_x(self, idx: int) -> float:
        spacing = self.cell_w + 0.30
        n = len(self._order)
        first_x = self.position[0] - (n - 1) * spacing / 2
        return first_x + idx * spacing

    def _reposition_labels(self):
        if self._order:
            head_cell = self._cells[self._order[0]]
            self.head_lbl.next_to(head_cell, UP, buff=0.18)
            tail_cell = self._cells[self._order[-1]]
            self.tail_lbl.next_to(tail_cell, DOWN, buff=0.18)
        else:
            self.head_lbl.move_to(self.position + UP * 0.6)
            self.tail_lbl.move_to(self.position + DOWN * 0.6)

    def _layout_anims(self):
        anims = []
        for idx, k in enumerate(self._order):
            target = [self._layout_x(idx), self.position[1], 0]
            anims.append(self._cells[k].animate.move_to(target))
        return anims

    def anim_add_to_head(self, key, val):
        cell = self._make_cell(key, val)
        cell.move_to(self.position + LEFT * 5)  # off-screen entry from left
        self._cells[key] = cell
        self._order.insert(0, key)
        self.vgroup.add(cell)
        anims = [FadeIn(cell)] + self._layout_anims()
        self._reposition_labels()
        return anims

    def anim_remove(self, key):
        if key not in self._cells:
            return []
        cell = self._cells.pop(key)
        self._order.remove(key)
        self.vgroup.remove(cell)
        anims = [FadeOut(cell)] + self._layout_anims()
        self._reposition_labels()
        return anims

    def anim_move_to_head(self, key):
        if key not in self._cells or self._order[0] == key:
            return []
        self._order.remove(key)
        self._order.insert(0, key)
        anims = self._layout_anims()
        self._reposition_labels()
        return anims

    def anim_flash(self, key, color=YELLOW):
        if key not in self._cells:
            return []
        return [Indicate(self._cells[key][0], color=color, scale_factor=1.2)]

    def order(self) -> list:
        return list(self._order)


# ---------------------------------------------------------------------------
# Primitive 14 — GraphPanel
# ---------------------------------------------------------------------------

class GraphPanel:
    """Nodes at fixed positions + edges with optional weight labels.

    edges format: list of [u, v] or [u, v, w] (weighted).

    Methods:
        .anim_set_node_color(i, color, opacity)
        .anim_flash_edge(u, v, color)
        .anim_set_node_value(i, new_value)
        .node_pos(i) -> point
    """

    def __init__(self, num_nodes: int, edges: list, position=ORIGIN,
                 radius: float = 2.4, node_radius: float = 0.32, directed: bool = False):
        import math
        self.num_nodes = num_nodes
        self.directed = directed
        self.node_radius = node_radius

        self.nodes = []
        font = max(14, int(20 * (node_radius / 0.32)))
        for i in range(num_nodes):
            angle = 2 * PI * i / max(num_nodes, 1) - PI / 2
            x = radius * math.cos(angle) + position[0]
            y = radius * math.sin(angle) + position[1]
            c = Circle(radius=node_radius, color=WHITE, stroke_width=2,
                       fill_color=DEFAULT_CELL, fill_opacity=0.7)
            lbl = Text(str(i), font_size=font, color=WHITE)
            self.nodes.append(VGroup(c, lbl).move_to([x, y, 0]))

        self.edges = {}        # (u, v) -> Line
        self.weight_lbls = {}  # (u, v) -> Text
        edge_objs = []
        for e in edges:
            if len(e) >= 3:
                u, v, w = e[0], e[1], e[2]
            else:
                u, v, w = e[0], e[1], None
            line = Line(self.nodes[u].get_center(), self.nodes[v].get_center(),
                        color=GRAY, stroke_width=2)
            # Trim line to circle borders
            line = self._trim_to_circle(line, self.nodes[u], self.nodes[v])
            self.edges[(u, v)] = line
            edge_objs.append(line)
            if w is not None:
                wlbl = Text(str(w), font_size=14, color=YELLOW).move_to(line.get_center())
                self.weight_lbls[(u, v)] = wlbl
                edge_objs.append(wlbl)

        self.vgroup = VGroup(*edge_objs, *self.nodes)

    def _trim_to_circle(self, line, src, dst):
        a = src.get_center()
        b = dst.get_center()
        import math
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1
        ux, uy = dx / L, dy / L
        a2 = [a[0] + ux * self.node_radius, a[1] + uy * self.node_radius, 0]
        b2 = [b[0] - ux * self.node_radius, b[1] - uy * self.node_radius, 0]
        return Line(a2, b2, color=GRAY, stroke_width=2)

    def anim_set_node_color(self, i: int, color, opacity: float = 0.85):
        return self.nodes[i][0].animate.set_fill(color, opacity=opacity)

    def anim_flash_edge(self, u: int, v: int, color=YELLOW):
        e = self.edges.get((u, v)) or self.edges.get((v, u))
        if e is None:
            return None
        return Indicate(e, color=color, scale_factor=1.0)

    def anim_set_node_value(self, i: int, new_value):
        font = max(14, int(20 * (self.node_radius / 0.32)))
        new_lbl = Text(str(new_value), font_size=font, color=WHITE).move_to(
            self.nodes[i][1].get_center())
        return Transform(self.nodes[i][1], new_lbl)

    def node_pos(self, i: int):
        return self.nodes[i].get_center()


# ---------------------------------------------------------------------------
# Primitive 15 — CodePanel
# ---------------------------------------------------------------------------

class CodePanel:
    """
    Pseudocode panel with per-line highlighting. Wraps `manim.Code` with
    sensible defaults for our scene layout.

    Construction:
        code = CodePanel('''
            for i in range(n):
                if seen[v - target]:
                    return seen[v - target]
                seen[v] = i
        ''', language="python", anchor=UL)

    Attributes:
        .vgroup       — the whole panel (Code mobject is a Group of bg + lines)
        .code         — the underlying manim.Code object
        .line_count   — number of code lines after dedent

    Methods (all return Animations the calling Scene wraps in self.play(...)):
        .anim_highlight(line_idx, color=YELLOW) — dim others, highlight one
        .anim_dim_all()                          — reset every line to GRAY
    """

    _DIM_COLOR = "#a8b0bd"   # bright enough to read; was #666b75 (too dim)
    _DEFAULT_HILITE = YELLOW

    def __init__(self, code_string: str, language: str = "python",
                 anchor=None, font_size: int = 18, max_width: float = 4.5,
                 buff: float = 0.3):
        import textwrap
        # Strip leading blank lines + common indentation so callers can pass
        # nicely-indented multi-line strings without leaking whitespace.
        cleaned = textwrap.dedent(code_string).strip("\n")
        if not cleaned.strip():
            cleaned = "# (empty)"

        self.code = Code(
            code_string=cleaned,
            language=language,
            add_line_numbers=False,
            background="rectangle",
            background_config={
                "fill_color": PANEL_BG,
                "fill_opacity": 0.9,
                "stroke_color": "#3a4a5c",
                "stroke_width": 1,
                "buff": 0.22,
                "corner_radius": 0.12,
            },
            paragraph_config={
                "font_size": font_size,
                "font": "Monospace",
                "line_spacing": 0.5,
                "disable_ligatures": True,
            },
        )
        self.line_count = len(self.code.code_lines)

        # Scale down if the rendered panel is wider than the budget.
        if self.code.width > max_width:
            self.code.scale(max_width / self.code.width)

        # Public-facing handle is the Code mobject (which itself is a Group of
        # background + paragraph). Callers FadeIn/FadeOut .vgroup.
        self.vgroup = self.code

        if anchor is not None:
            self.vgroup.to_corner(anchor, buff=buff)

    def _line(self, i: int):
        """Safe per-line accessor; returns None if out of range."""
        if 0 <= i < self.line_count:
            return self.code.code_lines[i]
        return None

    def anim_highlight(self, line_idx: int, color=None):
        """Dim every line to gray, then set the target line to `color`.

        Returns an AnimationGroup the caller wraps in self.play(...).
        Out-of-range line_idx returns a no-op AnimationGroup.
        """
        color = color or self._DEFAULT_HILITE
        anims = []
        for j in range(self.line_count):
            line = self.code.code_lines[j]
            target_color = color if j == line_idx else self._DIM_COLOR
            anims.append(line.animate.set_color(target_color))
        return AnimationGroup(*anims, lag_ratio=0.0)

    def anim_dim_all(self):
        """Reset every line to the dim color."""
        anims = [
            self.code.code_lines[j].animate.set_color(self._DIM_COLOR)
            for j in range(self.line_count)
        ]
        return AnimationGroup(*anims, lag_ratio=0.0)


# ---------------------------------------------------------------------------
# Primitive 16 — ComplexityBadge
# ---------------------------------------------------------------------------

class ComplexityBadge:
    """
    Small pill showing 'T: O(n) · S: O(1)' next to the scene title.
    Static — never animated, just FadeIn at scene start.

    Construction:
        badge = ComplexityBadge(time="O(n log n)", space="O(1)")
        badge.vgroup.next_to(title, RIGHT, buff=0.4)
    """

    def __init__(self, time: str, space: str, font_size: int = 16):
        time_label  = Text("T:", font_size=font_size, color=GRAY, weight=BOLD)
        time_value  = Text(time, font_size=font_size, color=BLUE, weight=BOLD)
        sep         = Text("·", font_size=font_size, color=GRAY)
        space_label = Text("S:", font_size=font_size, color=GRAY, weight=BOLD)
        space_value = Text(space, font_size=font_size, color=GREEN, weight=BOLD)

        row = VGroup(time_label, time_value, sep, space_label, space_value).arrange(
            RIGHT, buff=0.12)
        bg = SurroundingRectangle(
            row, color="#3a4a5c", fill_color=PANEL_BG,
            fill_opacity=0.85, buff=0.15, corner_radius=0.1, stroke_width=1,
        )
        self.vgroup = VGroup(bg, row)
        self.time = time
        self.space = space


# ---------------------------------------------------------------------------
# Primitive 17 — InvariantOverlay
# ---------------------------------------------------------------------------

class InvariantOverlay:
    """
    Small italic annotation pinned above the active strip, explaining the
    invariant the algorithm maintains. Never moves — a "north star" for
    the viewer.

    Construction:
        inv = InvariantOverlay("Stack stays decreasing", anchor_to=strip.vgroup)
    """

    def __init__(self, text: str, anchor_to=None, font_size: int = 18):
        self.text = text
        # Italic for "this is a meta-comment, not part of the data"
        self.label = Text(text, font_size=font_size, color="#a6b0c0",
                          slant=ITALIC)
        if anchor_to is not None:
            self.label.next_to(anchor_to, UP, buff=0.25)
        self.vgroup = self.label


# ---------------------------------------------------------------------------
# Primitive 18 — BruteForceComparison
# ---------------------------------------------------------------------------

class BruteForceComparison:
    """
    Two-row comparison strip shown at scene end alongside result_box.
    Brute force row appears red-strikethrough, optimal row appears green.

    Construction:
        cmp = BruteForceComparison(
            brute=("Nested loops", "O(n²)"),
            optimal=("Hashmap lookup", "O(n)"),
        )

    Defaults to anchoring above the result_box at DOWN buff=2.6.
    """

    def __init__(self, brute: tuple, optimal: tuple,
                 font_size: int = 16, anchor_below: bool = True):
        brute_desc, brute_complex = brute
        opt_desc, opt_complex = optimal

        # Row 1: brute force (red, strikethrough on complexity)
        x_mark      = Text("×", font_size=font_size + 2, color=REJECT, weight=BOLD)
        brute_label = Text(f"Brute: {brute_desc}", font_size=font_size, color="#a6b0c0")
        brute_cx    = Text(brute_complex, font_size=font_size, color=REJECT, weight=BOLD)
        # Strikethrough line through the complexity
        strike = Line(
            brute_cx.get_left() + LEFT * 0.05,
            brute_cx.get_right() + RIGHT * 0.05,
            stroke_width=1.5, color=REJECT,
        ).move_to(brute_cx.get_center())
        brute_row = VGroup(x_mark, brute_label, brute_cx, strike).arrange(RIGHT, buff=0.18)

        # Row 2: optimal (green, check mark)
        check     = Text("✓", font_size=font_size + 2, color=KEEP, weight=BOLD)
        opt_label = Text(f"This:  {opt_desc}", font_size=font_size, color="#a6b0c0")
        opt_cx    = Text(opt_complex, font_size=font_size, color=KEEP, weight=BOLD)
        opt_row = VGroup(check, opt_label, opt_cx).arrange(RIGHT, buff=0.18)

        rows = VGroup(brute_row, opt_row).arrange(DOWN, buff=0.12, aligned_edge=LEFT)
        bg = SurroundingRectangle(
            rows, color="#3a4a5c", fill_color=PANEL_BG,
            fill_opacity=0.88, buff=0.2, corner_radius=0.12, stroke_width=1,
        )
        self.vgroup = VGroup(bg, rows)
        # By default, anchor above the result_box (which sits at DOWN buff=1.75)
        if anchor_below:
            self.vgroup.to_edge(DOWN, buff=2.6)


# ---------------------------------------------------------------------------
# Primitive 19 — BinaryRegister
# ---------------------------------------------------------------------------

class BinaryRegister:
    """
    A row of 0/1 cells representing the bits of an integer.
    Bit index 0 (LSB) is the rightmost cell, bit index n-1 (MSB) is leftmost.

    Construction:
        reg = BinaryRegister(value=0b10110, num_bits=8, label="x")
        reg.vgroup.move_to(UP * 0.5)

    Attributes:
        .value      — current integer value
        .bits       — list[int] of 0/1, MSB to LSB
        .cells      — list[VGroup(square, text)] from MSB to LSB
        .vgroup     — full VGroup including label + cells + bit indices
        .label_mob  — the label Text mobject (None if no label given)

    Methods:
        .anim_set_bit(bit_idx, new_bit)             — bit_idx is 0=LSB convention
        .anim_xor_with(other_reg, target_reg)        — populates target = self ^ other
        .flash(bit_idx, color=YELLOW)
        .cell_for(bit_idx)                          — returns the cell for that bit
    """

    _ON_COLOR  = "#3b82f6"   # blue when bit is 1
    _OFF_COLOR = DEFAULT_CELL

    def __init__(self, value: int, num_bits: int = 8, label: str = "",
                 position=ORIGIN, cell_size: float = 0.7):
        self.num_bits = num_bits
        self.value = int(value) & ((1 << num_bits) - 1)
        self.bits = [(self.value >> (num_bits - 1 - i)) & 1 for i in range(num_bits)]
        self.label = label
        self.cell_size = cell_size

        # Build cells MSB→LSB (left to right on screen)
        self.cells = []
        for i, bit in enumerate(self.bits):
            sq = Square(side_length=cell_size, stroke_color=WHITE, stroke_width=1.5,
                        fill_color=(self._ON_COLOR if bit else self._OFF_COLOR),
                        fill_opacity=(0.85 if bit else 0.5))
            txt = Text(str(bit), font_size=int(28 * cell_size / 0.7), color=WHITE,
                       weight=BOLD)
            txt.move_to(sq.get_center())
            cell = VGroup(sq, txt)
            self.cells.append(cell)

        cells_row = VGroup(*self.cells).arrange(RIGHT, buff=0.05)

        # Bit index labels below each cell (LSB rightmost = bit 0)
        self.indices = VGroup()
        for i in range(num_bits):
            bit_idx = num_bits - 1 - i  # leftmost = MSB = (n-1), rightmost = 0
            lbl = Text(str(bit_idx), font_size=int(14 * cell_size / 0.7), color=GRAY)
            lbl.next_to(self.cells[i], DOWN, buff=0.08)
            self.indices.add(lbl)

        self.label_mob = None
        if label:
            self.label_mob = Text(f"{label} =", font_size=int(22 * cell_size / 0.7),
                                  color=WHITE, weight=BOLD)
            self.label_mob.next_to(cells_row, LEFT, buff=0.25)
            self.vgroup = VGroup(self.label_mob, cells_row, self.indices)
        else:
            self.vgroup = VGroup(cells_row, self.indices)

        self.vgroup.move_to(position)

    def cell_for(self, bit_idx: int):
        """bit_idx uses LSB=0 convention; returns the cell mobject."""
        if not (0 <= bit_idx < self.num_bits):
            return None
        # cells list is MSB→LSB; convert
        return self.cells[self.num_bits - 1 - bit_idx]

    def _list_index(self, bit_idx: int) -> int:
        return self.num_bits - 1 - bit_idx

    def anim_set_bit(self, bit_idx: int, new_bit: int):
        """Flip the cell at bit_idx (LSB=0). Returns animation; updates .value
        and .bits in place. If the bit is already at new_bit, returns a no-op
        animation so callers can always self.play(...) the result."""
        if not (0 <= bit_idx < self.num_bits):
            return AnimationGroup()

        idx = self._list_index(bit_idx)
        new_bit = 1 if new_bit else 0
        if self.bits[idx] == new_bit:
            return AnimationGroup()

        self.bits[idx] = new_bit
        # rebuild self.value from bits
        self.value = sum(b << (self.num_bits - 1 - i) for i, b in enumerate(self.bits))

        cell = self.cells[idx]
        new_text = Text(str(new_bit), font_size=int(28 * self.cell_size / 0.7),
                        color=WHITE, weight=BOLD).move_to(cell[1].get_center())
        new_color = self._ON_COLOR if new_bit else self._OFF_COLOR
        new_opacity = 0.85 if new_bit else 0.5

        return AnimationGroup(
            cell[0].animate.set_fill(new_color, opacity=new_opacity),
            Transform(cell[1], new_text),
            lag_ratio=0.0,
        )

    def anim_xor_with(self, other: "BinaryRegister", target: "BinaryRegister"):
        """Compute self ^ other into target. Returns a list of animations
        the caller can unpack: self.play(*reg_a.anim_xor_with(b, t))."""
        anims = []
        for bit_idx in range(self.num_bits):
            a_bit = self.bits[self._list_index(bit_idx)]
            b_bit = other.bits[other._list_index(bit_idx)]
            xor_bit = a_bit ^ b_bit
            sub = target.anim_set_bit(bit_idx, xor_bit)
            if sub is not None:
                anims.append(sub)
        return anims

    def flash(self, bit_idx: int, color=YELLOW, scale: float = 1.25):
        cell = self.cell_for(bit_idx)
        if cell is None:
            return AnimationGroup()
        return Indicate(cell, color=color, scale_factor=scale)
