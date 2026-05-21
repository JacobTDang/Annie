import json
import math
import os

import numpy as np
import sympy as sp
from manim import *

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

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
        path = os.path.join(temp_dir, f"{job_id}.json")
        if os.path.exists(path):
            with open(path) as f:
                return _strip_dict_nulls(json.load(f))
    return {}


def _result_box(tex: str, font_size: int = 28) -> VGroup:
    label = MathTex(tex, font_size=font_size)
    box = SurroundingRectangle(
        label, color=WHITE, fill_color=BLACK,
        fill_opacity=0.75, buff=0.15, corner_radius=0.1,
    )
    return VGroup(box, label)


def _show_title_card(scene, text: str):
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


def _caption(text: str) -> VGroup:
    import textwrap as _tw
    wrapped = _tw.fill(text, width=72)
    bg  = Rectangle(width=14.5, height=0.65, fill_color=BLACK,
                    fill_opacity=0.82, stroke_width=0).to_edge(DOWN, buff=0)
    txt = Text(wrapped, font_size=21, color=WHITE).to_edge(DOWN, buff=0.13)
    if txt.width > 13.5:
        txt.scale(13.5 / txt.width)
    return VGroup(bg, txt)


# ---------------------------------------------------------------------------
# TrigUnitCircleScene
# ---------------------------------------------------------------------------

class TrigUnitCircleScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p               = _load_params()
        target_angle    = float(p.get("angle",            0.785))
        animate_rotation = bool(p.get("animate_rotation", True))
        cap             = p.get("caption", "")

        # Square axes for the unit circle — x and y on same scale
        ax = Axes(
            x_range=[-1.6, 1.6, 0.5],
            y_range=[-1.6, 1.6, 0.5],
            x_length=5.5, y_length=5.5,
            axis_config={"color": WHITE, "include_numbers": True, "font_size": 18},
            tips=False,
        ).shift(LEFT * 1.5)

        unit_circle = Circle(
            radius=ax.x_axis.unit_size,
            color=WHITE, stroke_width=2,
        ).move_to(ax.c2p(0, 0))

        title = Text("Unit Circle", font_size=32).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Create(unit_circle), Write(title))

        # Initial angle
        theta = ValueTracker(0.0 if animate_rotation else target_angle)

        def _pt():
            t = theta.get_value()
            return ax.c2p(np.cos(t), np.sin(t))

        def _origin():
            return ax.c2p(0, 0)

        # Radius line
        radius_line = always_redraw(lambda: Line(
            _origin(), _pt(),
            color=WHITE, stroke_width=2.5,
        ))

        # Angle point dot
        angle_dot = always_redraw(lambda: Dot(_pt(), color=YELLOW, radius=0.1))

        # Sin projection (vertical line from point down to x-axis)
        sin_line = always_redraw(lambda: DashedLine(
            _pt(),
            ax.c2p(np.cos(theta.get_value()), 0),
            color=GREEN, stroke_width=2, dash_length=0.12,
        ))

        # Cos projection (horizontal line from point to y-axis)
        cos_line = always_redraw(lambda: DashedLine(
            _pt(),
            ax.c2p(0, np.sin(theta.get_value())),
            color=BLUE, stroke_width=2, dash_length=0.12,
        ))

        # Live sin/cos value labels on the right panel
        sin_val_label = always_redraw(lambda: _result_box(
            r"\sin\theta = " + f"{np.sin(theta.get_value()):.2f}", 26,
        ).to_corner(UR, buff=0.35).shift(DOWN * 0.5))

        cos_val_label = always_redraw(lambda: _result_box(
            r"\cos\theta = " + f"{np.cos(theta.get_value()):.2f}", 26,
        ).to_corner(UR, buff=0.35).shift(DOWN * 1.8))

        self.play(
            Create(radius_line), FadeIn(angle_dot),
            Create(sin_line), Create(cos_line),
        )
        self.play(Write(sin_val_label), Write(cos_val_label))
        self.wait(0.3)

        if animate_rotation:
            # Full rotation 0 → 2π  (takes ~6 seconds)
            self.play(
                theta.animate.set_value(2 * np.pi),
                run_time=6,
                rate_func=linear,
            )
            self.wait(0.5)
            # Then land on the target angle
            self.play(theta.animate.set_value(target_angle), run_time=1.5, rate_func=smooth)
        else:
            self.play(theta.animate.set_value(target_angle), run_time=2, rate_func=smooth)

        # Static labels at final angle
        t_final = theta.get_value()
        cx, cy  = np.cos(t_final), np.sin(t_final)

        sin_dot = Dot(ax.c2p(cx, 0), color=GREEN, radius=0.1)
        cos_dot = Dot(ax.c2p(0, cy), color=BLUE, radius=0.1)

        theta_tex = r"\theta \approx " + f"{t_final:.2f}"
        theta_label = _result_box(theta_tex, 24).to_corner(UR, buff=0.35).shift(DOWN * 3.1)

        self.play(FadeIn(sin_dot), FadeIn(cos_dot), FadeIn(theta_label))
        self.wait(1.5)
