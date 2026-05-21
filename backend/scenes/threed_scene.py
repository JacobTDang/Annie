import json
import math
import os

import numpy as np
import sympy as sp
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
        path = os.path.join(temp_dir, f"{job_id}.json")
        if os.path.exists(path):
            with open(path) as f:
                return _strip_dict_nulls(json.load(f))
    return {}


def _safe_eval(f, val: float) -> float:
    try:
        y = float(f(val))
        return y if math.isfinite(y) else 0.0
    except Exception:
        return 0.0


def _safe_eval_2d(f, u: float, v: float) -> float:
    try:
        z = float(f(u, v))
        return z if math.isfinite(z) else 0.0
    except Exception:
        return 0.0


def _caption_3d(text: str) -> Text:
    return Text(text, font_size=20, color=GRAY, slant=ITALIC).to_corner(DR, buff=0.2)


# ---------------------------------------------------------------------------
# SurfacePlotScene — z = f(x, y) with rotating camera
# ---------------------------------------------------------------------------

class SurfacePlotScene(ThreeDScene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p          = _load_params()
        expression = p.get("expression", "x**2 + y**2")
        x_domain   = p.get("x_domain") or [-3, 3]
        y_domain   = p.get("y_domain") or [-3, 3]
        cap        = p.get("caption",   "")

        x_sym, y_sym = sp.symbols("x y")
        expr = sp.sympify(expression)
        f    = sp.lambdify((x_sym, y_sym), expr, modules=["numpy"])

        # Sample the surface to compute a sensible z-range
        xs = np.linspace(x_domain[0], x_domain[1], 20)
        ys = np.linspace(y_domain[0], y_domain[1], 20)
        zs = [_safe_eval_2d(f, float(u), float(v)) for u in xs for v in ys]
        zs = [z for z in zs if math.isfinite(z) and abs(z) < 1e4]
        z_min = min(zs) if zs else -5.0
        z_max = max(zs) if zs else  5.0
        z_pad = max((z_max - z_min) * 0.18, 0.5)

        x_step = max(1, round((x_domain[1] - x_domain[0]) / 6))
        y_step = max(1, round((y_domain[1] - y_domain[0]) / 6))
        z_step = max(1, round((z_max - z_min) / 4))

        axes = ThreeDAxes(
            x_range=[x_domain[0], x_domain[1], x_step],
            y_range=[y_domain[0], y_domain[1], y_step],
            z_range=[z_min - z_pad, z_max + z_pad, z_step],
            x_length=6, y_length=6, z_length=4,
            axis_config={"color": WHITE, "include_numbers": False},
            tips=True,
        )

        axis_labels = axes.get_axis_labels(
            x_label=Text("x", font_size=22),
            y_label=Text("y", font_size=22),
            z_label=Text("z", font_size=22),
        )

        surface = Surface(
            lambda u, v: axes.c2p(u, v, _safe_eval_2d(f, u, v)),
            u_range=x_domain,
            v_range=y_domain,
            resolution=(28, 28),
            fill_opacity=0.88,
            checkerboard_colors=False,
            stroke_width=0.3,
            stroke_color=WHITE,
        )
        surface.set_color_by_gradient(BLUE_E, TEAL, GREEN, YELLOW, RED)

        title = Text(f"z = {expression}", font_size=26, color=WHITE).to_corner(UL, buff=0.25)

        self.set_camera_orientation(phi=70 * DEGREES, theta=-60 * DEGREES)
        self.add(axes, axis_labels)

        if cap:
            self.add_fixed_in_frame_mobjects(_caption_3d(cap))

        self.add_fixed_in_frame_mobjects(title)
        self.play(Create(surface), run_time=2.5)
        self.begin_ambient_camera_rotation(rate=0.18)
        self.wait(6)
        self.stop_ambient_camera_rotation()

        # Tilt to a top-down view to show contours
        self.move_camera(phi=20 * DEGREES, theta=-90 * DEGREES, run_time=2)
        self.wait(1.5)


# ---------------------------------------------------------------------------
# ContourScene — level curves of z = f(x, y)
# ---------------------------------------------------------------------------

class ContourScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "x**2 + y**2")
        x_domain   = p.get("x_domain") or [-3, 3]
        y_domain   = p.get("y_domain") or [-3, 3]
        num_levels = int(p.get("num_levels", 8))
        cap        = p.get("caption", "")

        x_sym, y_sym = sp.symbols("x y")
        expr = sp.sympify(expression)
        f    = sp.lambdify((x_sym, y_sym), expr, modules=["numpy"])

        # Use matplotlib (already a Manim dep) to compute contour paths
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        xs = np.linspace(x_domain[0], x_domain[1], 120)
        ys = np.linspace(y_domain[0], y_domain[1], 120)
        X, Y = np.meshgrid(xs, ys)
        Z = np.vectorize(lambda u, v: _safe_eval_2d(f, u, v))(X, Y)

        fig, ax_mpl = plt.subplots()
        cs = ax_mpl.contour(X, Y, Z, levels=num_levels)
        plt.close(fig)

        level_colors = color_gradient([BLUE_E, TEAL, GREEN, YELLOW, RED], max(len(cs.levels), 2))

        ax = Axes(
            x_range=[x_domain[0], x_domain[1], max(1, round((x_domain[1]-x_domain[0])/6))],
            y_range=[y_domain[0], y_domain[1], max(1, round((y_domain[1]-y_domain[0])/6))],
            x_length=7, y_length=7,
            axis_config={"color": WHITE, "include_numbers": True, "font_size": 18},
            tips=False,
        )
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        title  = MathTex(r"z = " + sp.latex(expr), font_size=30).to_edge(UP, buff=0.3)

        if cap:
            self.play(Write(_caption(cap)))
        self.play(Create(ax), Write(labels), Write(title))

        # Draw contour lines level by level (cs.allsegs works in all matplotlib versions)
        contour_curves = VGroup()
        for level_idx, (segs, lv) in enumerate(zip(cs.allsegs, cs.levels)):
            clr = level_colors[level_idx % len(level_colors)]
            for seg in segs:        # seg is an (N, 2) ndarray
                if len(seg) < 2:
                    continue
                pts = [ax.c2p(float(seg[i, 0]), float(seg[i, 1])) for i in range(len(seg))]
                curve = VMobject(color=clr, stroke_width=2.2)
                curve.set_points_smoothly(pts)
                contour_curves.add(curve)

        self.play(FadeIn(contour_curves), run_time=1.5)
        lv_label = Text(f"{num_levels} level curves", font_size=22, color=YELLOW).to_corner(UR, buff=0.3)
        self.play(Write(lv_label))
        self.wait(0.8)


# ---------------------------------------------------------------------------
# VectorFieldScene — 2D arrow / stream line field
# ---------------------------------------------------------------------------

class VectorFieldScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        x_expression    = p.get("x_expression",    "-y")
        y_expression    = p.get("y_expression",    "x")
        domain          = p.get("domain") or [-3, 3]
        show_streamlines = bool(p.get("show_streamlines", False))
        cap             = p.get("caption", "")

        x_sym, y_sym = sp.symbols("x y")
        fx_f = sp.lambdify((x_sym, y_sym), sp.sympify(x_expression), modules=["numpy"])
        fy_f = sp.lambdify((x_sym, y_sym), sp.sympify(y_expression), modules=["numpy"])

        def vec_func(pos):
            x, y = pos[0], pos[1]
            try:
                vx = float(fx_f(x, y))
                vy = float(fy_f(x, y))
                if not (math.isfinite(vx) and math.isfinite(vy)):
                    return np.zeros(3)
                mag = math.sqrt(vx ** 2 + vy ** 2)
                if mag > 1.8:
                    vx, vy = vx / mag * 1.8, vy / mag * 1.8
                return np.array([vx, vy, 0.0])
            except Exception:
                return np.zeros(3)

        title = MathTex(
            r"\vec{F} = \langle " + x_expression + r",\ " + y_expression + r"\rangle",
            font_size=32,
        ).to_edge(UP, buff=0.3)

        if cap:
            self.play(Write(_caption(cap)))
        self.play(Write(title))

        if show_streamlines:
            field = StreamLines(
                vec_func,
                x_range=[domain[0], domain[1], 0.6],
                y_range=[domain[0], domain[1], 0.6],
                stroke_width=2, max_anchors_per_line=25,
            )
            self.play(field.create(), run_time=3)
        else:
            field = ArrowVectorField(
                vec_func,
                x_range=[domain[0], domain[1], 0.8],
                y_range=[domain[0], domain[1], 0.8],
                colors=[BLUE_E, BLUE, TEAL, GREEN],
            )
            self.play(Create(field), run_time=2)

        self.wait(1.5)


# ---------------------------------------------------------------------------
# PartialDerivativeScene — 3D surface with cross-section slice
# ---------------------------------------------------------------------------

class PartialDerivativeScene(ThreeDScene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression  = p.get("expression",   "x**2 + y**2")
        variable    = p.get("variable",     "x")
        fixed_value = float(p.get("fixed_value", 0.0))
        x_domain    = p.get("x_domain") or [-3, 3]
        y_domain    = p.get("y_domain") or [-3, 3]
        cap         = p.get("caption", "")

        x_sym, y_sym = sp.symbols("x y")
        expr   = sp.sympify(expression)
        f_2d   = sp.lambdify((x_sym, y_sym), expr, modules=["numpy"])

        d_expr = sp.diff(expr, sp.Symbol(variable))

        # Z range
        zs = [_safe_eval_2d(f_2d, float(u), float(v))
              for u in np.linspace(x_domain[0], x_domain[1], 12)
              for v in np.linspace(y_domain[0], y_domain[1], 12)]
        zs = [z for z in zs if math.isfinite(z) and abs(z) < 1e4]
        z_min, z_max = (min(zs) if zs else -5), (max(zs) if zs else 5)
        z_pad = max((z_max - z_min) * 0.2, 0.5)

        axes = ThreeDAxes(
            x_range=[x_domain[0], x_domain[1], 1],
            y_range=[y_domain[0], y_domain[1], 1],
            z_range=[z_min - z_pad, z_max + z_pad, max(1, round((z_max - z_min) / 4))],
            x_length=5, y_length=5, z_length=3.5,
            axis_config={"color": WHITE, "include_numbers": False},
        )
        surface = Surface(
            lambda u, v: axes.c2p(u, v, _safe_eval_2d(f_2d, u, v)),
            u_range=x_domain, v_range=y_domain,
            resolution=(18, 18), fill_opacity=0.55,
            checkerboard_colors=False,
        )
        surface.set_color_by_gradient(BLUE_E, TEAL, GREEN, YELLOW)

        if variable == "x":
            f_slice = sp.lambdify(y_sym, expr.subs(x_sym, fixed_value), modules=["numpy"])
            slice_curve = ParametricFunction(
                lambda t: axes.c2p(fixed_value, t, _safe_eval(f_slice, t)),
                t_range=[y_domain[0], y_domain[1]], color=RED, stroke_width=4,
            )
            plane = Surface(
                lambda u, v: axes.c2p(fixed_value, u, v),
                u_range=[y_domain[0], y_domain[1]],
                v_range=[z_min - z_pad, z_max + z_pad],
                resolution=(8, 8), fill_opacity=0.15, fill_color=RED,
                checkerboard_colors=False,
            )
        else:
            f_slice = sp.lambdify(x_sym, expr.subs(y_sym, fixed_value), modules=["numpy"])
            slice_curve = ParametricFunction(
                lambda t: axes.c2p(t, fixed_value, _safe_eval(f_slice, t)),
                t_range=[x_domain[0], x_domain[1]], color=RED, stroke_width=4,
            )
            plane = Surface(
                lambda u, v: axes.c2p(u, fixed_value, v),
                u_range=[x_domain[0], x_domain[1]],
                v_range=[z_min - z_pad, z_max + z_pad],
                resolution=(8, 8), fill_opacity=0.15, fill_color=RED,
                checkerboard_colors=False,
            )

        self.set_camera_orientation(phi=70 * DEGREES, theta=-60 * DEGREES)
        self.add(axes)
        self.play(Create(surface), run_time=2)
        self.play(Create(plane), Create(slice_curve), run_time=1.5)
        self.begin_ambient_camera_rotation(rate=0.15)
        self.wait(4)
        self.stop_ambient_camera_rotation()

        d_label = Text(
            f"∂f/∂{variable} = {sp.latex(d_expr)}", font_size=22,
        ).to_corner(UL, buff=0.25)
        self.add_fixed_in_frame_mobjects(d_label)
        self.play(Write(d_label))
        self.wait(0.8)
