"""
Tool executor and DynamicScene for the Lesson Director agent.

DynamicScene reads a list of tool calls from its params JSON and delegates
each to ToolExecutor, which maps them to existing Manim primitives.
Unknown tools or bad args are logged and skipped — the scene never crashes.
"""
from __future__ import annotations

import json
import os
from typing import Any

from manim import *

from scenes.dsa_primitives import (
    ArrayStrip,
    HashMapPanel,
    Pointer,
    StackWidget,
    GridPanel,
    PTR_COLORS,
    DEFAULT_CELL,
    load_params,
    show_title_card,
    caption_strip,
    result_box,
)

# ─────────────────────────────────────────────────────────────────────────────
# Color mapping — LLM uses string names, we map to Manim constants
# ─────────────────────────────────────────────────────────────────────────────

_COLOR_MAP: dict[str, Any] = {
    "GREEN":  GREEN,
    "RED":    RED,
    "YELLOW": YELLOW,
    "ORANGE": ORANGE,
    "BLUE":   BLUE,
    "WHITE":  WHITE,
    "GRAY":   GRAY,
    "GREY":   GRAY,
    "PURPLE": PURPLE,
    "PINK":   PINK,
    "TEAL":   TEAL,
}

_POSITION_MAP: dict[str, Any] = {
    "UP":        UP * 2.0,
    "DOWN":      DOWN * 2.5,
    "LEFT":      LEFT * 4.5,
    "RIGHT":     RIGHT * 4.5,
    "CENTER":    ORIGIN,
    "UP_LEFT":   UP * 2.0 + LEFT * 3.0,
    "UP_RIGHT":  UP * 2.0 + RIGHT * 3.0,
}

_ANCHOR_MAP: dict[str, Any] = {
    "UR": UR,
    "UL": UL,
    "DR": DR,
    "DL": DL,
}


def _color(name: str, default=WHITE):
    return _COLOR_MAP.get(str(name).upper(), default)


def _position(name: str, default=ORIGIN):
    return _POSITION_MAP.get(str(name).upper(), default)


def _anchor(name: str, default=UR):
    return _ANCHOR_MAP.get(str(name).upper(), default)


# ─────────────────────────────────────────────────────────────────────────────
# ToolExecutor
# ─────────────────────────────────────────────────────────────────────────────

class ToolExecutor:
    """
    Interprets a sequence of tool-call dicts and drives Manim animations.

    State maps element_id strings to the created primitive objects so later
    tool calls can reference them. Pointers are tracked separately by name.
    """

    def __init__(self, scene: Scene):
        self.scene = scene
        self.state: dict[str, Any] = {}       # element_id → primitive
        self.vgroups: dict[str, Any] = {}     # element_id → top-level VGroup on screen
        self.pointers: dict[str, tuple[Pointer, ArrayStrip]] = {}  # name → (ptr, strip)
        self.caption_mob = None                # current caption VGroup on screen
        self.code_lines: dict[str, list[Text]] = {}  # element_id → Text list

    # ── dispatch ──────────────────────────────────────────────────────────────

    def execute(self, tool: str, args: dict) -> None:
        method = getattr(self, f"_tool_{tool}", None)
        if method is None:
            print(f"[ToolExecutor] unknown tool '{tool}' — skipping")
            return
        try:
            method(**args)
        except Exception as exc:
            print(f"[ToolExecutor] error in '{tool}({args})': {exc}")

    # ── element creation ──────────────────────────────────────────────────────

    def _tool_show_array(self, values: list, label: str = "", element_id: str = "array_0"):
        str_values = [str(v) for v in values]
        strip = ArrayStrip(str_values, position=ORIGIN)

        # Nudge downward slightly if a code panel is occupying UL
        if any("code" in eid for eid in self.state):
            strip.vgroup.shift(DOWN * 0.4)

        anims = [FadeIn(strip.vgroup)]
        if strip.indices:
            anims.append(FadeIn(strip.indices))
        self.scene.play(*anims, run_time=0.5)

        label_mob = None
        if label:
            label_mob = Text(label, font_size=20, color=GRAY)
            label_mob.next_to(strip.vgroup, UP, buff=0.2)
            self.scene.play(FadeIn(label_mob), run_time=0.3)

        self.state[element_id] = strip
        top = VGroup(strip.vgroup)
        if strip.indices:
            top.add(strip.indices)
        if label_mob:
            top.add(label_mob)
        self.vgroups[element_id] = top

    def _tool_show_hashmap(self, title: str = "HashMap", anchor: str = "UR",
                           element_id: str = "map_0"):
        # HashMapPanel positions itself via .to_corner() in __init__; vgroup
        # contains the background rectangle + title — both must be shown.
        panel = HashMapPanel(anchor=_anchor(anchor), title=title)
        self.scene.play(FadeIn(panel.vgroup), run_time=0.4)
        self.state[element_id] = panel
        self.vgroups[element_id] = panel.vgroup

    def _tool_show_stack(self, title: str = "stack", anchor: str = "DR",
                         element_id: str = "stack_0"):
        # StackWidget takes position=, not anchor=. Create at ORIGIN then move.
        widget = StackWidget(title=title)
        widget.vgroup.to_corner(_anchor(anchor), buff=0.3)
        self.scene.play(FadeIn(widget.vgroup), run_time=0.4)
        self.state[element_id] = widget
        self.vgroups[element_id] = widget.vgroup

    def _tool_show_grid(self, rows: int, cols: int, values: list,
                        label: str = "", element_id: str = "grid_0"):
        # Normalize values into a 2D list-of-lists matching the declared
        # rows × cols shape. The agent sometimes passes a flat list +
        # rows/cols; reshape it. (Previously this passed (rows, cols, flat)
        # to a GridPanel constructor that takes 2D `values` directly, which
        # silently errored. Bug fix: reshape + pass 2D.)
        cells_2d: list[list[str]]
        if values and isinstance(values[0], list):
            cells_2d = [[str(c) for c in row] for row in values]
        else:
            flat = [str(v) for v in values]
            cells_2d = []
            for r in range(rows):
                start = r * cols
                cells_2d.append(flat[start:start + cols])
        panel = GridPanel(cells_2d)
        self.scene.play(FadeIn(panel.vgroup), run_time=0.6)
        if label:
            lbl = Text(label, font_size=18, color=GRAY)
            lbl.next_to(panel.vgroup, UP, buff=0.2)
            self.scene.play(FadeIn(lbl), run_time=0.3)
        self.state[element_id] = panel
        self.vgroups[element_id] = panel.vgroup

    # ── Grid-aware cell ops (Phase 1) ────────────────────────────────────────
    # The existing highlight_cells / set_cell_value tools only work on 1D
    # ArrayStrips. These three tools cover the 2D DP table case.

    def _tool_set_grid_cell(self, element_id: str, row: int, col: int,
                             value, color: str | None = None):
        """Update a single cell's value (and optionally its fill color).
        Used by 2D DP scenes to animate `dp[row][col] = value`."""
        grid = self.state.get(element_id)
        if grid is None or not hasattr(grid, "anim_set_value"):
            return
        if not (0 <= row < grid.rows and 0 <= col < grid.cols):
            return
        anims = [grid.anim_set_value(row, col, value)]
        if color is not None:
            anims.append(grid.anim_set_fill(row, col, _color(color)))
        self.scene.play(*anims, run_time=0.4)

    def _tool_highlight_grid_cells(self, element_id: str, cells: list,
                                    color: str = "YELLOW"):
        """Pulse one or more (row, col) cells. ``cells`` is a list of
        2-element lists/tuples: [[r1, c1], [r2, c2], ...]."""
        grid = self.state.get(element_id)
        if grid is None or not hasattr(grid, "anim_set_fill"):
            return
        anims = []
        for rc in cells:
            try:
                r, c = int(rc[0]), int(rc[1])
            except (TypeError, ValueError, IndexError):
                continue
            if not (0 <= r < grid.rows and 0 <= c < grid.cols):
                continue
            anims.append(grid.anim_set_fill(r, c, _color(color)))
        if anims:
            self.scene.play(*anims, run_time=0.4)

    def _tool_draw_grid_arrow(self, element_id: str,
                               from_row: int, from_col: int,
                               to_row: int, to_col: int,
                               color: str = "TEAL",
                               label: str | None = None):
        """Curved dependency arrow between two cells of the same grid.
        Used by DP scenes to show `dp[to_r][to_c]` was computed from
        `dp[from_r][from_c]`."""
        grid = self.state.get(element_id)
        if grid is None or not hasattr(grid, "cell_top"):
            return
        if not (0 <= from_row < grid.rows and 0 <= from_col < grid.cols):
            return
        if not (0 <= to_row < grid.rows and 0 <= to_col < grid.cols):
            return
        from scenes.dsa_primitives import GridArrow
        arrow = GridArrow.between(grid, (from_row, from_col), (to_row, to_col),
                                    color=_color(color), label=label)
        self.scene.play(Create(arrow), run_time=0.4)

    def _tool_show_code(self, lines: list, anchor: str = "UL",
                        element_id: str = "code_0"):
        text_lines = []
        for line in lines[:8]:
            t = Text(line, font_size=16, color=GRAY,
                     font="Monospace", disable_ligatures=True)
            text_lines.append(t)

        code_vg = VGroup(*text_lines).arrange(DOWN, aligned_edge=LEFT, buff=0.08)
        # Background
        bg = BackgroundRectangle(code_vg, fill_opacity=0.8, buff=0.12,
                                 fill_color="#0d1117")
        group = VGroup(bg, code_vg)

        anch = _anchor(anchor)
        group.to_corner(anch, buff=0.3)

        self.scene.play(FadeIn(group), run_time=0.4)
        self.state[element_id] = group
        self.vgroups[element_id] = group
        self.code_lines[element_id] = text_lines

    def _tool_show_text(self, content: str, position: str = "UP",
                        style: str = "normal", element_id: str = "text_0"):
        weight = BOLD if style == "bold" else NORMAL
        txt = Text(content, font_size=22, color=WHITE, weight=weight,
                   slant=(ITALIC if style == "italic" else NORMAL))
        if txt.width > 11:
            txt.scale(11 / txt.width)
        pos = _position(position, UP * 2.0)
        txt.move_to(pos)
        self.scene.play(FadeIn(txt), run_time=0.35)
        self.state[element_id] = txt
        self.vgroups[element_id] = txt

    def _tool_show_equation(self, latex: str, position: str = "CENTER",
                            element_id: str = "eq_0"):
        try:
            eq = MathTex(latex, font_size=36)
        except Exception:
            eq = Text(latex, font_size=28)
        pos = _position(position, ORIGIN)
        eq.move_to(pos)
        self.scene.play(Write(eq), run_time=0.8)
        self.state[element_id] = eq
        self.vgroups[element_id] = eq

    # ── pointers ──────────────────────────────────────────────────────────────

    def _tool_add_pointer(self, name: str, element_id: str, index: int = 0,
                          color: str = "YELLOW"):
        strip = self.state.get(element_id)
        if not isinstance(strip, ArrayStrip):
            print(f"[ToolExecutor] add_pointer: '{element_id}' is not an ArrayStrip")
            return
        col = PTR_COLORS.get(name, _color(color, YELLOW))
        ptr = Pointer(name, color=col)
        ptr.place_below(strip, min(index, len(strip.cells) - 1))
        self.scene.play(FadeIn(ptr.vgroup), run_time=0.3)
        self.pointers[name] = (ptr, strip)

    def _tool_move_pointer(self, name: str, element_id: str, to_index: int):
        if name not in self.pointers:
            print(f"[ToolExecutor] move_pointer: unknown pointer '{name}'")
            return
        ptr, strip = self.pointers[name]
        idx = min(to_index, len(strip.cells) - 1)
        self.scene.play(ptr.anim_move_to(strip, idx), run_time=0.4,
                        rate_func=smooth)

    # ── cell / value ops ──────────────────────────────────────────────────────

    def _tool_highlight_cells(self, element_id: str, indices: list,
                              color: str = "YELLOW"):
        strip = self.state.get(element_id)
        if not isinstance(strip, ArrayStrip):
            print(f"[ToolExecutor] highlight_cells: '{element_id}' not ArrayStrip")
            return
        col = _color(color, YELLOW)
        valid = [i for i in indices if 0 <= i < len(strip.cells)]
        if not valid:
            return
        anims = [strip.flash(i, color=col) for i in valid]
        self.scene.play(LaggedStart(*anims, lag_ratio=0.15), run_time=0.5)

    def _tool_swap_cells(self, element_id: str, i: int, j: int):
        strip = self.state.get(element_id)
        if not isinstance(strip, ArrayStrip):
            return
        n = len(strip.cells)
        if not (0 <= i < n and 0 <= j < n and i != j):
            return
        ci, cj = strip.cells[i], strip.cells[j]
        pi, pj = ci.get_center(), cj.get_center()
        # Swap display values via arc paths
        self.scene.play(
            ci.animate.move_to(pj),
            cj.animate.move_to(pi),
            path_arc=PI / 3,
            run_time=0.6,
            rate_func=smooth,
        )
        # Swap in the internal list so future references are correct
        strip.cells[i], strip.cells[j] = strip.cells[j], strip.cells[i]
        strip.values[i], strip.values[j] = strip.values[j], strip.values[i]

    def _tool_set_cell_value(self, element_id: str, index: int, value: str):
        strip = self.state.get(element_id)
        if not isinstance(strip, ArrayStrip):
            return
        if 0 <= index < len(strip.cells):
            self.scene.play(strip.anim_set_value(index, str(value)), run_time=0.35)

    # ── collection ops ────────────────────────────────────────────────────────

    def _tool_push_stack(self, element_id: str, value: str,
                         color: str = "WHITE"):
        widget = self.state.get(element_id)
        if not isinstance(widget, StackWidget):
            return
        col = _color(color, WHITE)
        anims = widget.anim_push(str(value), col)
        if anims:
            self.scene.play(*anims, run_time=0.4)

    def _tool_pop_stack(self, element_id: str):
        widget = self.state.get(element_id)
        if not isinstance(widget, StackWidget):
            return
        anims = widget.anim_pop()
        if anims:
            self.scene.play(*anims, run_time=0.35)

    def _tool_set_hashmap_entry(self, element_id: str, key: str, value: str):
        panel = self.state.get(element_id)
        if not isinstance(panel, HashMapPanel):
            return
        anims = panel.anim_set(str(key), str(value))
        if anims:
            self.scene.play(*anims, run_time=0.4)

    def _tool_delete_hashmap_entry(self, element_id: str, key: str):
        panel = self.state.get(element_id)
        if not isinstance(panel, HashMapPanel):
            return
        anims = panel.anim_delete(str(key))
        if anims:
            self.scene.play(*anims, run_time=0.35)

    def _tool_highlight_code_line(self, element_id: str, line_index: int):
        lines = self.code_lines.get(element_id)
        if not lines:
            return
        anims = []
        for i, t in enumerate(lines):
            target_color = YELLOW if i == line_index else "#555566"
            anims.append(t.animate.set_color(target_color))
        self.scene.play(*anims, run_time=0.25)

    # ── narrative / pacing ────────────────────────────────────────────────────

    def _tool_set_caption(self, text: str):
        new_cap = caption_strip(text)
        if self.caption_mob is not None:
            self.scene.play(
                FadeOut(self.caption_mob),
                FadeIn(new_cap),
                run_time=0.3,
            )
        else:
            self.scene.play(FadeIn(new_cap), run_time=0.3)
        self.caption_mob = new_cap

    def _tool_add_annotation(self, text: str, element_id: str, index: int = -1,
                              annotation_id: str = "annotation_0"):
        mob = self.vgroups.get(element_id) or self.state.get(element_id)
        if mob is None:
            return

        strip = self.state.get(element_id)
        if isinstance(strip, ArrayStrip) and index >= 0:
            target_point = strip.cell_top(min(index, len(strip.cells) - 1))
        else:
            target_point = mob.get_top() if hasattr(mob, "get_top") else ORIGIN

        label = Text(text, font_size=16, color=LIGHT_GRAY, slant=ITALIC)
        if label.width > 5:
            label.scale(5 / label.width)
        label.next_to(target_point, UP, buff=0.3)
        arrow = Arrow(label.get_bottom(), target_point, stroke_width=1.5,
                      max_tip_length_to_length_ratio=0.25, color=GRAY)
        grp = VGroup(label, arrow)
        self.scene.play(FadeIn(grp), run_time=0.35)
        # Store so fade_out_element can remove it
        self.state[annotation_id] = grp
        self.vgroups[annotation_id] = grp

    def _tool_emphasize(self, element_id: str, index: int = -1,
                         pace: str = "normal"):
        strip = self.state.get(element_id)
        mob = self.vgroups.get(element_id)

        if isinstance(strip, ArrayStrip) and index >= 0 and index < len(strip.cells):
            target = strip.cells[index]
        elif mob is not None:
            target = mob
        else:
            return

        # Rhythm: slow draws out the aha moment, fast is for minor beats.
        if pace == "slow":
            run_time, scale, hold = 1.0, 1.4, 0.6
        elif pace == "fast":
            run_time, scale, hold = 0.3, 1.15, 0.0
        else:  # normal
            run_time, scale, hold = 0.6, 1.25, 0.0

        self.scene.play(
            Indicate(target, color=YELLOW, scale_factor=scale),
            run_time=run_time,
            rate_func=there_and_back,
        )
        if hold > 0:
            self.scene.wait(hold)

    def _tool_show_result(self, value: str, label: str = ""):
        text = f"{label}: {value}" if label else str(value)
        box = result_box(text, font_size=30)
        box.to_edge(DOWN, buff=1.75)
        self.scene.play(FadeIn(box), run_time=0.5)
        self.scene.play(box.animate.scale(1.08), run_time=0.2,
                        rate_func=there_and_back)

    def _tool_pause(self, beats: int = 1):
        self.scene.wait(max(1, beats) * 0.6)

    def _tool_fade_out_element(self, element_id: str):
        mob = self.vgroups.get(element_id)
        if mob is None:
            mob = self.state.get(element_id)
        if mob is None:
            return
        # For primitives that expose .vgroup
        if hasattr(mob, "vgroup"):
            mob = mob.vgroup
        self.scene.play(FadeOut(mob), run_time=0.4)
        self.state.pop(element_id, None)
        self.vgroups.pop(element_id, None)

    # ── camera (Item #7) ──────────────────────────────────────────────────────
    # These require MovingCameraScene. DynamicScene inherits from it so
    # self.scene.camera.frame exists. If the scene is a plain Scene (e.g.
    # called from another scene class), these silently no-op.

    def _camera_frame(self):
        cam = getattr(self.scene, "camera", None)
        return getattr(cam, "frame", None) if cam is not None else None

    def _resolve_mobject(self, element_id: str):
        mob = self.vgroups.get(element_id) or self.state.get(element_id)
        if mob is not None and hasattr(mob, "vgroup"):
            mob = mob.vgroup
        return mob

    def _tool_pan_to(self, element_id: str):
        frame = self._camera_frame()
        target = self._resolve_mobject(element_id)
        if frame is None or target is None:
            return
        self.scene.play(frame.animate.move_to(target.get_center()), run_time=0.6)

    def _tool_zoom_to(self, element_id: str, level: float = 1.5):
        frame = self._camera_frame()
        target = self._resolve_mobject(element_id)
        if frame is None or target is None:
            return
        # Clamp to a sane range so the LLM can't accidentally produce a render
        # zoomed to a single pixel or zoomed infinitely out.
        try:
            level = float(level)
        except (TypeError, ValueError):
            level = 1.5
        level = max(1.05, min(level, 2.5))
        self.scene.play(
            frame.animate.move_to(target.get_center()).scale(1.0 / level),
            run_time=0.7,
        )

    def _tool_zoom_out(self):
        frame = self._camera_frame()
        if frame is None:
            return
        # Reset to default viewport: 14 × 8 unit camera frame at origin.
        self.scene.play(
            frame.animate.move_to(ORIGIN).set(width=config.frame_width),
            run_time=0.6,
        )


# ─────────────────────────────────────────────────────────────────────────────
# DynamicScene — the Manim scene class registered in SCENE_REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

class DynamicScene(MovingCameraScene):
    """
    Manim scene driven entirely by tool calls from the Lesson Director agent.

    Params JSON shape:
    {
      "title": "Scene title shown as title card",
      "tool_calls": [
        {"tool": "show_array", "args": {"values": ["3","1","4"], "element_id": "array_0"}},
        {"tool": "add_pointer", "args": {"name": "i", "element_id": "array_0", "color": "YELLOW"}},
        ...
      ]
    }
    """

    def construct(self):
        params = load_params()
        title = params.get("title", "")
        tool_calls = params.get("tool_calls", [])

        # Cap tool calls to keep render time inside the 180s worker budget.
        # Override via LUMEN_MAX_TOOL_CALLS env var for testing.
        max_calls = int(os.environ.get("LUMEN_MAX_TOOL_CALLS", "20"))
        if len(tool_calls) > max_calls:
            print(f"[DynamicScene] capping {len(tool_calls)} → {max_calls} tool calls")
            tool_calls = tool_calls[:max_calls]

        if title:
            show_title_card(self, title)

        executor = ToolExecutor(self)
        for call in tool_calls:
            tool_name = call.get("tool", "")
            args = call.get("args", {})
            if not tool_name:
                continue
            try:
                executor.execute(tool_name, args)
            except Exception as e:
                # Never crash a scene due to a single bad tool call
                print(f"[DynamicScene] skipping '{tool_name}': {e}")

        # Hold final frame
        self.wait(0.5)
