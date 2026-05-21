import json
import math
import os
from contextlib import contextmanager

import numpy as np
import sympy as sp
from manim import *

# ---------------------------------------------------------------------------
# WARNING: sympy calls (sp.solve, sp.integrate, sp.limit, sp.series, etc.)
# can hang indefinitely on pathological inputs. There is currently no
# wall-clock timeout enforced around these calls. A proper timeout requires
# a multiprocessing.Process approach because signal-based timeouts only work
# on Unix and threading.Timer cannot interrupt a CPU-bound C extension call.
# Until that's implemented, validate inputs at the schema layer
# (see backend/schemas/types.py) and keep expressions simple.
# ---------------------------------------------------------------------------


@contextmanager
def _sympy_timeout(seconds: int = 5):
    """No-op timeout context manager (placeholder).

    NOTE: This is intentionally a no-op on Windows because:
      - signal.SIGALRM is Unix-only.
      - threading.Timer cannot interrupt CPU-bound sympy/C-extension calls.
    Proper enforcement requires running the sympy work in a
    multiprocessing.Process and joining with a timeout. Left as a TODO.
    Yields a flag list whose [0] entry is set to True if/when a real
    timeout fires, so call sites can detect it once the helper is upgraded.
    """
    flag = [False]
    yield flag

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
CURVE_COLOR    = BLUE
DERIV_COLOR    = GREEN
HIGHLIGHT_COLOR = YELLOW
CRITICAL_COLOR = RED
TANGENT_COLOR  = YELLOW

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _strip_dict_nulls(obj):
    """Drop None values from dict keys (recursively) so `p.get(K, D)`
    falls back to D when the agent passed explicit null. See dsa_scene.py."""
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


def _parse(expression: str):
    x = sp.Symbol("x")
    expr = sp.sympify(expression)
    func = sp.lambdify(x, expr, modules=["numpy"])
    return expr, func, x


def _safe_eval(func, val: float) -> float:
    try:
        y = float(func(val))
        return y if math.isfinite(y) else 0.0
    except Exception:
        return 0.0


def _y_range(func, domain: list) -> list:
    xs = np.linspace(domain[0], domain[1], 400)
    finite = [_safe_eval(func, float(v)) for v in xs]
    finite = [y for y in finite if math.isfinite(y) and abs(y) < 1e5]
    if not finite:
        return [-5.0, 5.0, 1.0]
    lo, hi = min(finite), max(finite)
    pad = max((hi - lo) * 0.2, 0.5)
    lo, hi = lo - pad, hi + pad
    step = max(1.0, round((hi - lo) / 6))
    return [lo, hi, step]


def _make_axes(domain: list, yr: list, x_len: float = 9.0, y_len: float = 5.5) -> Axes:
    x_step = max(1, round((domain[1] - domain[0]) / 8))
    return Axes(
        x_range=[domain[0], domain[1], x_step],
        y_range=yr,
        x_length=x_len,
        y_length=y_len,
        axis_config={"color": WHITE, "include_numbers": True, "font_size": 20},
        tips=False,
    )


def _num(v: float) -> str:
    return str(int(v)) if v == int(v) else str(round(v, 4))


def _fmt_num(v: float, max_chars: int = 10) -> str:
    """Format a number, switching to scientific notation if it would overflow a cell."""
    if not isinstance(v, (int, float)):
        return str(v)
    if v == int(v) and abs(v) < 10**9:
        return str(int(v))
    if abs(v) >= 10**6 or (abs(v) < 1e-3 and v != 0):
        return f"{v:.2e}"
    return f"{v:.4g}"


def _clip_latex(expr, max_chars: int = 28) -> str:
    s = sp.latex(expr)
    if len(s) <= max_chars:
        return s
    simplified = sp.latex(expr.simplify())
    return simplified if len(simplified) <= max_chars else simplified[:max_chars] + r"\cdots"


def _result_box(tex: str, font_size: int = 28) -> VGroup:
    """MathTex label inside a dark background box for readability over graphs."""
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
# Scene 1 — Function Plot
# ---------------------------------------------------------------------------

class FunctionPlotScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "x**2")
        domain     = p.get("domain") or [-4, 4]
        x_point    = p.get("x_point")
        cap        = p.get("caption", "")

        expr, f, _ = _parse(expression)
        yr = _y_range(f, domain)
        ax = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph = ax.plot(f, x_range=domain, color=CURVE_COLOR, use_smoothing=True)
        title = MathTex(r"f(x) = " + _clip_latex(expr), font_size=36).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels))
        self.play(Write(title))
        self.play(Create(graph), run_time=2)

        if x_point is not None:
            xp = float(x_point)
            yp = _safe_eval(f, xp)
            dot = Dot(ax.c2p(xp, yp), color=HIGHLIGHT_COLOR, radius=0.1)
            direction = UR if yp >= 0 else DR
            coord = _result_box(
                r"\left(" + _num(xp) + r",\ " + f"{yp:.2f}" + r"\right)", 24,
            ).next_to(dot, direction, buff=0.18)
            self.play(FadeIn(dot))
            self.play(Indicate(dot, color=HIGHLIGHT_COLOR, scale_factor=1.4))
            self.play(FadeIn(coord))

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 2 — Limit
# ---------------------------------------------------------------------------

class LimitScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "sin(x)/x")
        limit_pt   = float(p.get("limit_point", 0))
        domain     = p.get("domain") or [-5, 5]
        cap        = p.get("caption", "")

        expr, f, x_sym = _parse(expression)

        try:
            lim_val   = sp.limit(expr, x_sym, limit_pt)
            lim_float = float(lim_val)
            lim_tex   = sp.latex(lim_val)
        except Exception:
            lim_val   = None
            lim_float = None
            lim_tex   = r"\text{DNE}"

        yr = _y_range(f, domain)
        ax = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")

        eps = 0.08
        left_graph  = ax.plot(f, x_range=[domain[0], limit_pt - eps], color=CURVE_COLOR)
        right_graph = ax.plot(f, x_range=[limit_pt + eps, domain[1]], color=CURVE_COLOR)

        pt_tex = _num(limit_pt)
        title = MathTex(
            r"\lim_{x \to " + pt_tex + r"} f(x)", font_size=36,
        ).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels), Write(title))
        self.play(Create(left_graph), Create(right_graph), run_time=1.5)

        # Left approach
        lt = ValueTracker(domain[0])
        left_dot = always_redraw(lambda: Dot(
            ax.c2p(lt.get_value(), _safe_eval(f, lt.get_value())),
            color=HIGHLIGHT_COLOR, radius=0.1,
        ))
        left_tag = MathTex(
            r"x \to " + pt_tex + r"^-", font_size=24, color=HIGHLIGHT_COLOR,
        ).to_corner(UL, buff=0.3)
        self.add(left_dot)
        self.play(Write(left_tag))
        self.play(lt.animate.set_value(limit_pt - eps), run_time=2.5)
        self.wait(0.5)

        # Right approach
        rt = ValueTracker(domain[1])
        right_dot = always_redraw(lambda: Dot(
            ax.c2p(rt.get_value(), _safe_eval(f, rt.get_value())),
            color=CRITICAL_COLOR, radius=0.1,
        ))
        right_tag = MathTex(
            r"x \to " + pt_tex + r"^+", font_size=24, color=CRITICAL_COLOR,
        ).to_corner(UR, buff=0.3)
        self.add(right_dot)
        self.play(Write(right_tag))
        self.play(rt.animate.set_value(limit_pt + eps), run_time=2.5)
        self.wait(0.5)

        if lim_float is not None:
            limit_dot = Dot(ax.c2p(limit_pt, lim_float), color=WHITE, radius=0.12)
            self.play(FadeIn(limit_dot))
            self.play(Indicate(limit_dot, scale_factor=1.5))
            result = _result_box(
                r"\lim_{x \to " + pt_tex + r"} f(x) = " + lim_tex, 28,
            ).to_edge(DOWN, buff=0.55)
            self.play(FadeIn(result))

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 3 — Tangent Line
# ---------------------------------------------------------------------------

class TangentLineScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "x**2")
        x_pt       = float(p.get("x_point", 1.0))
        domain     = p.get("domain") or [-4, 4]
        cap        = p.get("caption", "")

        expr, f, x_sym = _parse(expression)
        d_expr     = sp.diff(expr, x_sym)
        y0         = _safe_eval(f, x_pt)
        slope_sym  = d_expr.subs(x_sym, x_pt)

        yr  = _y_range(f, domain)
        ax  = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph  = ax.plot(f, x_range=domain, color=CURVE_COLOR)
        title  = MathTex(
            r"f(x) = " + _clip_latex(expr), font_size=34,
        ).to_edge(UP, buff=0.3)
        dot = Dot(ax.c2p(x_pt, y0), color=HIGHLIGHT_COLOR, radius=0.1)

        h_max = min(2.0, (domain[1] - domain[0]) * 0.35)
        h = ValueTracker(h_max)

        def _secant():
            hv = max(h.get_value(), 1e-5)
            s  = (_safe_eval(f, x_pt + hv) - _safe_eval(f, x_pt - hv)) / (2 * hv)
            return ax.plot(
                lambda x: y0 + s * (x - x_pt),
                x_range=domain, color=TANGENT_COLOR, stroke_width=2.5,
            )

        line = always_redraw(_secant)
        line_label = always_redraw(lambda: Text(
            "secant" if h.get_value() > 0.05 else "tangent",
            font_size=22, color=TANGENT_COLOR,
        ).to_corner(UR, buff=0.3))

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels))
        self.play(Write(title), Create(graph))
        self.play(FadeIn(dot), Create(line), Write(line_label))
        self.play(h.animate.set_value(0.01), run_time=4, rate_func=smooth)

        self.play(Indicate(dot, color=HIGHLIGHT_COLOR, scale_factor=1.5))

        slope_result = _result_box(
            r"f'\!\left(" + _num(x_pt) + r"\right) = " + _clip_latex(slope_sym), 28,
        ).to_edge(DOWN, buff=0.55)
        self.play(FadeIn(slope_result))
        self.wait(1.5)


# ---------------------------------------------------------------------------
# Average rate of change (secant line through the endpoints of an interval)
# ---------------------------------------------------------------------------

class SecantLineScene(Scene):
    """Average rate of change = slope of the secant through (a, f(a)) and
    (b, f(b)). Renders the curve, the two endpoints, the secant, and the
    computed slope as (f(b) − f(a)) / (b − a)."""

    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "x**2 + 1")
        a = float(p.get("a", 2.0))
        b = float(p.get("b", 5.0))
        cap = p.get("caption", "")
        if a == b:
            b = a + 1  # degenerate interval — nudge so we don't divide by zero

        # Pick a domain that comfortably brackets [a, b] for context
        span    = b - a
        margin  = max(1.0, span * 0.4)
        domain  = p.get("domain") or [a - margin, b + margin]

        expr, f, _x_sym = _parse(expression)
        ya = _safe_eval(f, a)
        yb = _safe_eval(f, b)
        slope = (yb - ya) / (b - a)

        yr  = _y_range(f, domain)
        ax  = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph  = ax.plot(f, x_range=domain, color=CURVE_COLOR)
        title  = MathTex(
            r"f(x) = " + _clip_latex(expr), font_size=34,
        ).to_edge(UP, buff=0.3)

        pa  = ax.c2p(a, ya)
        pb  = ax.c2p(b, yb)
        dot_a = Dot(pa, color=HIGHLIGHT_COLOR, radius=0.1)
        dot_b = Dot(pb, color=HIGHLIGHT_COLOR, radius=0.1)
        # Dashed verticals from x-axis up to each endpoint
        zero_y = ax.c2p(a, 0)[1]
        v_a = DashedLine(start=[pa[0], zero_y, 0], end=pa, color=GRAY_B, stroke_width=2)
        v_b = DashedLine(start=[pb[0], zero_y, 0], end=pb, color=GRAY_B, stroke_width=2)
        # x-axis tick labels for a and b
        lbl_a = MathTex(_num(a), font_size=24, color=GRAY_B).next_to([pa[0], zero_y, 0], DOWN, buff=0.15)
        lbl_b = MathTex(_num(b), font_size=24, color=GRAY_B).next_to([pb[0], zero_y, 0], DOWN, buff=0.15)

        # Secant line extending slightly beyond the two endpoints for visual reach
        ext = max(0.4, span * 0.15)
        secant = ax.plot(
            lambda x: ya + slope * (x - a),
            x_range=[max(domain[0], a - ext), min(domain[1], b + ext)],
            color=TANGENT_COLOR,
            stroke_width=3,
        )
        secant_lbl = Text("secant", font_size=22, color=TANGENT_COLOR).to_corner(UR, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels))
        self.play(Write(title), Create(graph))
        self.play(FadeIn(v_a), FadeIn(v_b), Write(lbl_a), Write(lbl_b))
        self.play(FadeIn(dot_a), FadeIn(dot_b))
        self.play(Create(secant), Write(secant_lbl))

        self.play(Indicate(dot_a, color=HIGHLIGHT_COLOR, scale_factor=1.5))
        self.play(Indicate(dot_b, color=HIGHLIGHT_COLOR, scale_factor=1.5))

        # Slope formula + numeric result
        formula = MathTex(
            r"\frac{f(" + _num(b) + r") - f(" + _num(a) + r")}"
            r"{" + _num(b) + r" - " + _num(a) + r"}"
            r" = \frac{" + _num(yb) + r" - " + _num(ya) + r"}"
            r"{" + _num(b - a) + r"} = " + _num(slope),
            font_size=30,
        )
        result = _result_box(
            r"\text{avg rate of change} = " + _num(slope), 28,
        )
        VGroup(formula, result).arrange(DOWN, buff=0.18).to_edge(DOWN, buff=0.4)
        self.play(FadeIn(formula))
        self.play(FadeIn(result))
        self.wait(2)


# ---------------------------------------------------------------------------
# Scene 4 — Riemann Sum
# ---------------------------------------------------------------------------

class RiemannSumScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "x**2")
        domain     = p.get("domain") or [0, 3]
        n_start    = int(p.get("n",      5))
        method     = p.get("method",     "left")
        cap        = p.get("caption", "")

        sample_map   = {"left": "left", "right": "right", "midpoint": "center"}
        manim_method = sample_map.get(method, "left")

        expr, f, x_sym = _parse(expression)
        yr = _y_range(f, domain)
        yr[0] = min(yr[0], -0.3)
        ax     = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph  = ax.plot(f, x_range=domain, color=CURVE_COLOR)

        try:
            exact     = float(sp.integrate(expr, (x_sym, domain[0], domain[1])))
            exact_str = f"{exact:.4f}"
        except Exception:
            exact_str = r"\cdots"

        a_tex, b_tex = _num(domain[0]), _num(domain[1])
        title = MathTex(
            r"\int_{" + a_tex + r"}^{" + b_tex + r"} " + _clip_latex(expr) + r"\, dx",
            font_size=34,
        ).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels), Write(title))
        self.play(Create(graph), run_time=1.5)

        dx0   = (domain[1] - domain[0]) / n_start
        rects = ax.get_riemann_rectangles(
            graph, x_range=domain, dx=dx0,
            input_sample_type=manim_method, color=BLUE_D, fill_opacity=0.55,
        )
        n_label = MathTex(f"n = {n_start}", font_size=26).to_corner(DR, buff=0.3)
        self.play(FadeIn(rects), Write(n_label))
        self.wait(0.4)

        for n_new in [n_start * 3, n_start * 8, n_start * 20]:
            dx_new    = (domain[1] - domain[0]) / n_new
            new_rects = ax.get_riemann_rectangles(
                graph, x_range=domain, dx=dx_new,
                input_sample_type=manim_method, color=BLUE_D, fill_opacity=0.55,
            )
            new_label = MathTex(f"n = {n_new}", font_size=26).to_corner(DR, buff=0.3)
            self.play(
                Transform(rects, new_rects),
                Transform(n_label, new_label),
                run_time=0.9,
            )
            self.wait(0.25)

        exact_label = _result_box(r"= " + exact_str, 28).to_edge(DOWN, buff=0.55)
        self.play(FadeIn(exact_label))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 5 — Critical Points
# ---------------------------------------------------------------------------

class CriticalPointsScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "x**3 - 3*x")
        domain     = p.get("domain") or [-3, 3]
        cap        = p.get("caption", "")

        expr, f, x_sym = _parse(expression)
        d_expr  = sp.diff(expr, x_sym)
        d2_expr = sp.diff(d_expr, x_sym)
        f_prime = sp.lambdify(x_sym, d_expr, modules=["numpy"])

        try:
            raw      = sp.solve(d_expr, x_sym)
            crit_pts = sorted([
                float(cp.evalf()) for cp in raw
                if cp.is_real and domain[0] <= float(cp.evalf()) <= domain[1]
            ])
        except Exception:
            crit_pts = []

        yr_f  = _y_range(f,       domain)
        yr_fp = _y_range(f_prime, domain)
        x_step = max(1, round((domain[1] - domain[0]) / 8))

        ax_f = Axes(
            x_range=[domain[0], domain[1], x_step],
            y_range=yr_f, x_length=7.5, y_length=2.5,
            axis_config={"color": WHITE, "include_numbers": True, "font_size": 16},
            tips=False,
        ).shift(UP * 1.85)

        ax_fp = Axes(
            x_range=[domain[0], domain[1], x_step],
            y_range=yr_fp, x_length=7.5, y_length=2.5,
            axis_config={"color": WHITE, "include_numbers": True, "font_size": 16},
            tips=False,
        ).shift(DOWN * 1.85)

        graph_f  = ax_f.plot(f,       x_range=domain, color=CURVE_COLOR)
        graph_fp = ax_fp.plot(f_prime, x_range=domain, color=DERIV_COLOR)

        # Dashed zero line on f' axes to show where derivative crosses zero
        zero_line = DashedLine(
            ax_fp.c2p(domain[0], 0), ax_fp.c2p(domain[1], 0),
            color=GRAY, dash_length=0.12, stroke_width=1.5,
        )

        lbl_f  = MathTex(r"f(x)",   font_size=20, color=CURVE_COLOR).next_to(ax_f,  LEFT, buff=0.35)
        lbl_fp = MathTex(r"f'(x)",  font_size=20, color=DERIV_COLOR).next_to(ax_fp, LEFT, buff=0.35)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax_f), Create(ax_fp), Write(lbl_f), Write(lbl_fp))
        self.play(Create(graph_f), Create(graph_fp), Create(zero_line), run_time=2)

        for cp in crit_pts:
            y_f = _safe_eval(f, cp)

            # Smart label direction: avoid top overflow
            y_frac = (y_f - yr_f[0]) / max(yr_f[1] - yr_f[0], 1e-6)
            lbl_dir = DOWN if y_frac > 0.75 else UP

            dot_f  = Dot(ax_f.c2p(cp, y_f), color=CRITICAL_COLOR, radius=0.1)
            dot_fp = Dot(ax_fp.c2p(cp, 0),  color=CRITICAL_COLOR, radius=0.1)

            s2   = float(d2_expr.subs(x_sym, cp).evalf())
            kind = "inflection" if abs(s2) < 1e-8 else ("local max" if s2 < 0 else "local min")
            cp_label = Text(kind, font_size=17, color=CRITICAL_COLOR).next_to(
                dot_f, lbl_dir, buff=0.12,
            )

            self.play(FadeIn(dot_f), FadeIn(dot_fp))
            self.play(Indicate(dot_f, color=CRITICAL_COLOR, scale_factor=1.4))
            self.play(Write(cp_label))

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 6 — Volume of Revolution (disk method, 2-D side view)
# ---------------------------------------------------------------------------

class VolumeRevolutionScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "sqrt(x)")
        domain     = p.get("domain") or [0, 4]
        n_disks    = int(p.get("n_disks", 8))
        cap        = p.get("caption", "")

        expr, f, x_sym = _parse(expression)
        yr = _y_range(f, domain)
        # Extend below axis so mirrored disks show symmetry
        yr[0] = min(yr[0], -yr[1] * 0.4)
        ax     = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph  = ax.plot(f, x_range=domain, color=CURVE_COLOR)
        area   = ax.get_area(graph, x_range=domain, color=CURVE_COLOR, opacity=0.25)

        title = MathTex(
            r"V = \pi\int_{" + _num(domain[0]) + r"}^{" + _num(domain[1]) + r"}[f(x)]^2\,dx",
            font_size=30,
        ).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)
        self.play(Create(ax), Write(labels))
        self.play(Write(title))
        self.play(Create(graph), FadeIn(area), run_time=1.5)
        self.wait(0.3)

        # Representative disks — ellipses mimicking perspective
        dx = (domain[1] - domain[0]) / n_disks
        disk_xs = np.linspace(domain[0] + dx / 2, domain[1] - dx / 2, n_disks)
        disks = VGroup()
        for xd in disk_xs:
            r = _safe_eval(f, float(xd))
            if r <= 0:
                continue
            disk_h = 2 * r * ax.y_axis.unit_size
            disk_w = dx * ax.x_axis.unit_size * 0.8
            disk = Ellipse(
                width=disk_w, height=disk_h,
                color=YELLOW, fill_color=YELLOW, fill_opacity=0.22,
                stroke_width=1.5,
            )
            disk.move_to(ax.c2p(float(xd), 0))
            disks.add(disk)

        self.play(FadeIn(disks), run_time=1.5)
        self.wait(0.3)

        try:
            vol = float(sp.pi * sp.integrate(expr ** 2, (x_sym, domain[0], domain[1])))
            vol_str = f"{vol:.4f}"
        except Exception:
            vol_str = r"?"

        self.play(FadeIn(_result_box(r"V = " + vol_str, 28).to_edge(DOWN, buff=0.55)))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 7 — Taylor Series
# ---------------------------------------------------------------------------

class TaylorSeriesScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "sin(x)")
        center     = float(p.get("center",    0.0))
        max_terms  = int(p.get("max_terms",   5))
        domain     = p.get("domain") or [-5, 5]
        cap        = p.get("caption", "")

        x_sym = sp.Symbol("x")
        expr  = sp.sympify(expression)
        f_target = sp.lambdify(x_sym, expr, modules=["numpy"])

        # Pre-compute partial sums
        partial_sums  = []
        partial_exprs = []
        for n in range(1, max_terms + 1):
            try:
                s = expr.series(x_sym, center, n + 1).removeO()
            except Exception:
                s = expr
            partial_sums.append(sp.lambdify(x_sym, s, modules=["numpy"]))
            partial_exprs.append(s)

        yr = _y_range(f_target, domain)
        ax = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")

        target_graph = ax.plot(f_target, x_range=domain, color=CURVE_COLOR, stroke_width=2.5)
        title = MathTex(r"f(x) = " + _clip_latex(expr), font_size=32, color=CURVE_COLOR)
        title.to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)
        self.play(Create(ax), Write(labels), Write(title))
        self.play(Create(target_graph), run_time=1.5)
        self.wait(0.3)

        approx = ax.plot(partial_sums[0], x_range=domain, color=CRITICAL_COLOR, stroke_width=2)
        n_lbl  = MathTex(r"T_1", font_size=26, color=CRITICAL_COLOR).to_corner(UR, buff=0.3)
        self.play(Create(approx), Write(n_lbl))

        for i, psum in enumerate(partial_sums[1:], start=2):
            new_approx = ax.plot(psum, x_range=domain, color=CRITICAL_COLOR, stroke_width=2)
            new_lbl    = MathTex(f"T_{i}", font_size=26, color=CRITICAL_COLOR).to_corner(UR, buff=0.3)
            self.play(Transform(approx, new_approx), Transform(n_lbl, new_lbl), run_time=0.8)
            self.wait(0.25)

        poly_tex = _clip_latex(partial_exprs[-1], max_chars=32)
        self.play(FadeIn(
            _result_box(r"T_{" + str(max_terms) + r"}(x) \approx " + poly_tex, 22)
            .to_edge(DOWN, buff=0.55)
        ))
        self.wait(1.2)


# ---------------------------------------------------------------------------
# Scene 8 — Fundamental Theorem of Calculus (Part 1)
# ---------------------------------------------------------------------------

class FTCScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "x**2 - 2*x + 2")
        domain     = p.get("domain") or [-0.5, 4]
        start      = float(p.get("start", 0.0))
        cap        = p.get("caption", "")

        expr, f, x_sym = _parse(expression)
        t_sym = sp.Symbol("t")
        expr_t = expr.subs(x_sym, t_sym)

        def compute_F(xv: float) -> float:
            try:
                return float(sp.integrate(expr_t, (t_sym, start, xv)))
            except Exception:
                from scipy import integrate as sci
                result, _ = sci.quad(f, start, xv)
                return result

        yr_f = _y_range(f, domain)
        F_xs = np.linspace(domain[0], domain[1], 60)
        F_ys = [compute_F(float(x)) for x in F_xs]
        F_finite = [y for y in F_ys if math.isfinite(y)]
        F_lo = min(F_finite) if F_finite else -5
        F_hi = max(F_finite) if F_finite else 5
        F_pad = max((F_hi - F_lo) * 0.2, 0.5)

        ax_f = Axes(
            x_range=[domain[0], domain[1], max(1, round((domain[1]-domain[0])/8))],
            y_range=yr_f, x_length=8, y_length=2.5,
            axis_config={"color": WHITE, "include_numbers": True, "font_size": 16},
            tips=False,
        ).shift(UP * 1.85)

        ax_F = Axes(
            x_range=[domain[0], domain[1], max(1, round((domain[1]-domain[0])/8))],
            y_range=[F_lo - F_pad, F_hi + F_pad, max(1, round((F_hi-F_lo+2*F_pad)/6))],
            x_length=8, y_length=2.5,
            axis_config={"color": WHITE, "include_numbers": True, "font_size": 16},
            tips=False,
        ).shift(DOWN * 1.85)

        graph_f = ax_f.plot(f, x_range=domain, color=CURVE_COLOR)
        graph_F = ax_F.plot(compute_F, x_range=[start, domain[1]], color=DERIV_COLOR)
        graph_F.set_stroke(opacity=0)  # hidden until revealed

        lbl_f = MathTex(r"f(x)", font_size=20, color=CURVE_COLOR).next_to(ax_f, LEFT, buff=0.3)
        lbl_F = MathTex(r"F(x)=\int_a^x f(t)\,dt", font_size=16, color=DERIV_COLOR)
        lbl_F.next_to(ax_F, LEFT, buff=0.1)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)
        self.play(Create(ax_f), Create(ax_F), Write(lbl_f), Write(lbl_F))
        self.play(Create(graph_f), run_time=1.5)
        self.wait(0.3)

        x_tracker = ValueTracker(start)

        area = always_redraw(lambda: (
            ax_f.get_area(graph_f,
                          x_range=[start, max(x_tracker.get_value(), start + 0.05)],
                          color=CURVE_COLOR, opacity=0.35)
        ))
        self.add(area)

        # Reveal F(x) curve progressively alongside area growth
        self.play(
            x_tracker.animate.set_value(domain[1]),
            Create(graph_F),
            run_time=5, rate_func=linear,
        )
        graph_F.set_stroke(opacity=1)

        self.play(FadeIn(
            _result_box(r"F'(x) = f(x)", 30).to_edge(DOWN, buff=0.55)
        ))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 9 — Sequence Convergence (recursive sequence term-by-term)
# ---------------------------------------------------------------------------

class SequenceScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p        = _load_params()
        formula  = p.get("formula",  "sqrt(x + 2)")
        a0       = float(p.get("a0",      0.0))
        n_terms  = int(p.get("n_terms",   8))
        cap      = p.get("caption", "")

        x_sym = sp.Symbol("x")
        expr  = sp.sympify(formula)
        f_rec = sp.lambdify(x_sym, expr, modules=["numpy"])

        # Compute sequence terms
        terms = [a0]
        for _ in range(n_terms - 1):
            terms.append(_safe_eval(f_rec, terms[-1]))

        # Find fixed point L where f(L) = L
        try:
            fps      = sp.solve(expr - x_sym, x_sym)
            real_fps = [float(fp.evalf()) for fp in fps if fp.is_real]
            L        = min(real_fps, key=lambda v: abs(v - terms[-1])) if real_fps else terms[-1]
        except Exception:
            L = terms[-1]

        y_vals  = terms + [L]
        y_lo    = min(0.0, min(y_vals)) - 0.2
        y_hi    = max(y_vals) * 1.15 + 0.2
        y_step  = max(0.5, round((y_hi - y_lo) / 6, 1))

        ax = Axes(
            x_range=[0, n_terms, 1],
            y_range=[y_lo, y_hi, y_step],
            x_length=10, y_length=5.5,
            axis_config={"color": WHITE, "include_numbers": True, "font_size": 18},
            tips=False,
        )
        x_lbl = MathTex("n",   font_size=22).next_to(ax.x_axis.get_end(), RIGHT, buff=0.15)
        y_lbl = MathTex("a_n", font_size=22).next_to(ax.y_axis.get_end(), UP,    buff=0.15)

        title = MathTex(
            r"a_n = " + _clip_latex(expr) + r",\quad a_0 = " + _num(a0),
            font_size=30,
        ).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(x_lbl), Write(y_lbl), Write(title))

        # Dashed limit line
        L_line  = DashedLine(ax.c2p(0, L), ax.c2p(n_terms, L), color=GREEN, stroke_width=2)
        L_label = MathTex(r"L = " + _num(round(L, 4)), font_size=22, color=GREEN)
        L_label.next_to(ax.c2p(n_terms, L), RIGHT, buff=0.1)
        self.play(Create(L_line), Write(L_label))

        # Animate terms appearing one by one
        prev_dot = None
        for i, val in enumerate(terms):
            dot = Dot(ax.c2p(i, val), color=HIGHLIGHT_COLOR, radius=0.09)
            lbl = MathTex(f"{val:.3f}", font_size=14, color=HIGHLIGHT_COLOR)
            lbl.next_to(dot, UP if val < L else DOWN, buff=0.09)

            anims = [FadeIn(dot), Write(lbl)]
            if prev_dot is not None:
                anims.append(Create(
                    DashedLine(prev_dot.get_center(), dot.get_center(),
                               color=GRAY, stroke_width=1.5)
                ))
            self.play(*anims, run_time=0.35)
            prev_dot = dot

        self.play(FadeIn(
            _result_box(r"a_n \to " + _num(round(L, 4)) + r"\text{ as }n\to\infty", 26)
            .to_edge(DOWN, buff=0.55)
        ))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 10 — Cobweb Diagram (fixed-point iteration convergence)
# ---------------------------------------------------------------------------

class CobwebScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p        = _load_params()
        formula  = p.get("formula",  "sqrt(x + 2)")
        a0       = float(p.get("a0",      0.0))
        n_steps  = int(p.get("n_steps",   8))
        domain   = p.get("domain") or [0, 4]
        cap      = p.get("caption",  "")

        x_sym = sp.Symbol("x")
        expr  = sp.sympify(formula)
        f_rec = sp.lambdify(x_sym, expr, modules=["numpy"])

        yr = _y_range(f_rec, domain)
        yr[0] = min(yr[0], 0)
        yr[1] = max(yr[1], domain[1])   # y must reach diagonal

        ax      = _make_axes(domain, yr)
        labels  = ax.get_axis_labels(x_label="x", y_label="y")
        graph_f = ax.plot(f_rec, x_range=domain, color=CURVE_COLOR, stroke_width=2.5)
        graph_id = ax.plot(lambda x: x, x_range=[max(yr[0], domain[0]), domain[1]],
                           color=DERIV_COLOR, stroke_width=2)

        lbl_f  = MathTex(r"y = f(x) = " + _clip_latex(expr), font_size=20, color=CURVE_COLOR)
        lbl_id = MathTex(r"y = x", font_size=20, color=DERIV_COLOR)
        lbl_f.to_corner(UR, buff=0.3)
        lbl_id.next_to(lbl_f, DOWN, buff=0.1)

        title = MathTex(r"\text{Cobweb Diagram}", font_size=30).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels), Write(title))
        self.play(Create(graph_f), Create(graph_id))
        self.play(Write(lbl_f), Write(lbl_id))
        self.wait(0.3)

        # Fixed point: solve f(x) = x
        try:
            fps  = sp.solve(expr - x_sym, x_sym)
            rfps = [float(fp.evalf()) for fp in fps
                    if fp.is_real and domain[0] <= float(fp.evalf()) <= domain[1]]
            L = rfps[0] if rfps else None
        except Exception:
            L = None

        if L is not None:
            fp_dot = Dot(ax.c2p(L, L), color=CRITICAL_COLOR, radius=0.12)
            fp_lbl = MathTex(r"L = " + _num(round(L, 3)), font_size=22, color=CRITICAL_COLOR)
            fp_lbl.next_to(fp_dot, UR, buff=0.15)
            self.play(FadeIn(fp_dot), Write(fp_lbl))

        # Starting dot
        self.play(FadeIn(Dot(ax.c2p(a0, a0), color=HIGHLIGHT_COLOR, radius=0.1)))

        x_cur = a0
        for step in range(n_steps):
            x_next = _safe_eval(f_rec, x_cur)
            if not (domain[0] - 0.1 <= x_next <= domain[1] + 0.1):
                break

            # Opacity fades as we get closer to the fixed point
            opacity = max(0.25, 1.0 - step * 0.09)

            # Vertical: (x_cur, x_cur) → (x_cur, x_next)  [touches f(x)]
            vline = Line(ax.c2p(x_cur, x_cur), ax.c2p(x_cur, x_next),
                         color=HIGHLIGHT_COLOR, stroke_width=2.5, stroke_opacity=opacity)
            self.play(Create(vline), run_time=0.4)

            # Horizontal: (x_cur, x_next) → (x_next, x_next)  [touches y=x]
            hline = Line(ax.c2p(x_cur, x_next), ax.c2p(x_next, x_next),
                         color=HIGHLIGHT_COLOR, stroke_width=2.5, stroke_opacity=opacity)
            self.play(Create(hline), run_time=0.4)

            x_cur = x_next

        self.play(FadeIn(Dot(ax.c2p(x_cur, x_cur), color=GREEN, radius=0.1)))
        lim_str = _num(round(L, 3)) if L is not None else _num(round(x_cur, 3))
        self.play(FadeIn(
            _result_box(r"a_n \to " + lim_str + r"\text{ (fixed point)}", 26)
            .to_edge(DOWN, buff=0.55)
        ))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  INTEGRAL APPLICATION SCENES
# ===========================================================================

# ---------------------------------------------------------------------------
# Scene 11 — Area Between Curves
# ---------------------------------------------------------------------------

class AreaBetweenCurvesScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        f_expr_str = p.get("f_expression", "x")
        g_expr_str = p.get("g_expression", "x**2")
        domain     = p.get("domain") or [0, 1]
        cap        = p.get("caption", "")

        expr_f, f, x_sym = _parse(f_expr_str)
        expr_g, g, _     = _parse(g_expr_str)

        # Combined y-range
        yr_f = _y_range(f, domain)
        yr_g = _y_range(g, domain)
        yr   = [min(yr_f[0], yr_g[0]), max(yr_f[1], yr_g[1]),
                max(yr_f[2], yr_g[2])]

        ax     = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph_f = ax.plot(f, x_range=domain, color=CURVE_COLOR,  stroke_width=2.5)
        graph_g = ax.plot(g, x_range=domain, color=CRITICAL_COLOR, stroke_width=2.5)

        lbl_f = MathTex(r"f(x)=" + _clip_latex(expr_f), font_size=22, color=CURVE_COLOR)
        lbl_g = MathTex(r"g(x)=" + _clip_latex(expr_g), font_size=22, color=CRITICAL_COLOR)
        lbl_f.to_corner(UR, buff=0.3)
        lbl_g.next_to(lbl_f, DOWN, buff=0.1)

        title = MathTex(r"\int [f(x)-g(x)]\,dx", font_size=32).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels), Write(title))
        self.play(Create(graph_f), Create(graph_g))
        self.play(Write(lbl_f), Write(lbl_g))

        # Intersection points
        try:
            ints = sp.solve(expr_f - expr_g, x_sym)
            int_xs = sorted([float(v.evalf()) for v in ints
                             if v.is_real and domain[0] <= float(v.evalf()) <= domain[1]])
        except Exception:
            int_xs = []

        for ix in int_xs:
            iy = _safe_eval(f, ix)
            self.play(FadeIn(Dot(ax.c2p(ix, iy), color=WHITE, radius=0.1)), run_time=0.3)

        # Shade the region
        area = ax.get_area(graph_f, x_range=domain,
                           bounded_graph=graph_g, color=BLUE, opacity=0.35)
        self.play(FadeIn(area), run_time=1.5)

        # Compute area
        try:
            val = float(sp.integrate(expr_f - expr_g, (x_sym, domain[0], domain[1])))
            val = abs(val)
            val_str = f"{val:.4f}"
        except Exception:
            val_str = r"?"

        a_tex, b_tex = _num(domain[0]), _num(domain[1])
        self.play(FadeIn(
            _result_box(r"A = \int_{" + a_tex + r"}^{" + b_tex + r"}"
                        r"[f-g]\,dx = " + val_str, 26)
            .to_edge(DOWN, buff=0.55)
        ))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 12 — Washer Method
# ---------------------------------------------------------------------------

class WasherMethodScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        f_str    = p.get("f_expression", "sqrt(x)")
        g_str    = p.get("g_expression", "x**2")
        domain   = p.get("domain") or [0, 1]
        n_washers = int(p.get("n_washers", 8))
        cap      = p.get("caption", "")

        expr_f, f, x_sym = _parse(f_str)
        expr_g, g, _     = _parse(g_str)

        max_y = _y_range(f, domain)[1]
        yr = [-max_y * 1.05, max_y * 1.05, max(0.5, round(max_y / 4, 1))]
        ax = _make_axes(domain, yr)
        labels  = ax.get_axis_labels(x_label="x", y_label="y")
        graph_f = ax.plot(f, x_range=domain, color=CURVE_COLOR,   stroke_width=2.5)
        graph_g = ax.plot(g, x_range=domain, color=CRITICAL_COLOR, stroke_width=2.5)

        lbl_f = MathTex(r"R=f(x)=" + _clip_latex(expr_f), font_size=20, color=CURVE_COLOR).to_corner(UR, buff=0.3)
        lbl_g = MathTex(r"r=g(x)=" + _clip_latex(expr_g), font_size=20, color=CRITICAL_COLOR).next_to(lbl_f, DOWN, buff=0.1)

        title = MathTex(r"V = \pi\int[R^2-r^2]\,dx", font_size=30).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels), Write(title))
        self.play(Create(graph_f), Create(graph_g), Write(lbl_f), Write(lbl_g))
        self.play(FadeIn(ax.get_area(graph_f, x_range=domain,
                                     bounded_graph=graph_g, color=BLUE, opacity=0.2)))
        self.wait(0.4)

        dx = (domain[1] - domain[0]) / n_washers
        ux = ax.x_axis.unit_size
        uy = ax.y_axis.unit_size
        washers = VGroup()

        for k in range(n_washers):
            xd = domain[0] + (k + 0.5) * dx
            R  = max(_safe_eval(f, xd), 0)
            r  = max(_safe_eval(g, xd), 0)
            if R <= 0:
                continue
            w = dx * ux * 0.8
            outer = Ellipse(width=w, height=2*R*uy,
                            color=BLUE, fill_color=BLUE, fill_opacity=0.30, stroke_width=1.5)
            inner = Ellipse(width=w * 0.95, height=max(2*r*uy, 0.02),
                            fill_color="#0d1117", fill_opacity=1.0, stroke_width=0)
            washer = VGroup(outer, inner).move_to(ax.c2p(xd, 0))
            washers.add(washer)

        self.play(FadeIn(washers), run_time=1.5)

        try:
            vol = float(sp.pi * sp.integrate(expr_f**2 - expr_g**2,
                                              (x_sym, domain[0], domain[1])))
            vol_str = f"{vol:.4f}"
        except Exception:
            vol_str = r"?"

        self.play(FadeIn(_result_box(r"V = " + vol_str, 28).to_edge(DOWN, buff=0.55)))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 13 — Shell Method
# ---------------------------------------------------------------------------

class ShellMethodScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "sqrt(x)")
        domain     = p.get("domain") or [0, 4]
        n_shells   = int(p.get("n_shells", 8))
        cap        = p.get("caption", "")

        expr, f, x_sym = _parse(expression)
        yr = _y_range(f, domain)
        yr[0] = min(yr[0], 0)
        ax     = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph  = ax.plot(f, x_range=domain, color=CURVE_COLOR, stroke_width=2.5)
        area   = ax.get_area(graph, x_range=domain, color=CURVE_COLOR, opacity=0.18)

        title = MathTex(r"V = 2\pi\int x\cdot f(x)\,dx", font_size=30).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels), Write(title))
        self.play(Create(graph), FadeIn(area))
        self.wait(0.3)

        dx  = (domain[1] - domain[0]) / n_shells
        ux  = ax.x_axis.unit_size
        uy  = ax.y_axis.unit_size
        shells = VGroup()

        for k in range(n_shells):
            xd = domain[0] + (k + 0.5) * dx
            h  = _safe_eval(f, xd)
            if h <= 0:
                continue
            shell_w = dx * ux * 0.82
            shell_h = h  * uy
            # Shell as a tall rectangle (side view)
            alpha = max(0.35, 0.75 - k * 0.04)
            rect = Rectangle(
                width=shell_w, height=shell_h,
                fill_color=YELLOW, fill_opacity=alpha,
                stroke_color=WHITE, stroke_width=1,
            )
            rect.move_to(ax.c2p(xd, h / 2))
            shells.add(rect)

        # Animate shells appearing one by one
        self.play(LaggedStart(*[FadeIn(s) for s in shells], lag_ratio=0.15), run_time=2)

        # Label one shell
        mid_shell = shells[n_shells // 2]
        xd_mid = domain[0] + (n_shells // 2 + 0.5) * dx
        r_label = MathTex(r"r=x", font_size=18, color=YELLOW).next_to(mid_shell, DOWN, buff=0.15)
        h_label = MathTex(r"h=f(x)", font_size=18, color=YELLOW).next_to(mid_shell, RIGHT, buff=0.08)
        self.play(Write(r_label), Write(h_label))

        formula = MathTex(r"V_{\text{shell}} \approx 2\pi x\cdot f(x)\cdot\Delta x",
                          font_size=24, color=YELLOW).to_corner(UL, buff=0.3)
        self.play(Write(formula))
        self.wait(0.5)

        try:
            vol = float(2 * sp.pi * sp.integrate(x_sym * expr, (x_sym, domain[0], domain[1])))
            vol_str = f"{vol:.4f}"
        except Exception:
            vol_str = r"?"

        self.play(FadeIn(_result_box(r"V = 2\pi\int x\,f(x)\,dx = " + vol_str, 26)
                         .to_edge(DOWN, buff=0.55)))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 14 — Arc Length
# ---------------------------------------------------------------------------

class ArcLengthScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "sin(x)")
        domain     = p.get("domain") or [0, 3.14]
        n_segments = int(p.get("n_segments", 8))
        cap        = p.get("caption", "")

        expr, f, x_sym = _parse(expression)
        d_expr = sp.diff(expr, x_sym)
        f_prime = sp.lambdify(x_sym, d_expr, modules=["numpy"])

        yr = _y_range(f, domain)
        ax = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph  = ax.plot(f, x_range=domain, color=CURVE_COLOR, stroke_width=2)
        title  = MathTex(r"L = \int\sqrt{1+[f'(x)]^2}\,dx", font_size=30).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels), Write(title))
        self.play(Create(graph), run_time=1.5)
        self.wait(0.3)

        def make_segments(n):
            xs  = np.linspace(domain[0], domain[1], n + 1)
            pts = [ax.c2p(float(x), _safe_eval(f, float(x))) for x in xs]
            return VGroup(*[
                Line(pts[i], pts[i + 1], color=HIGHLIGHT_COLOR, stroke_width=2.5)
                for i in range(n)
            ])

        segs = make_segments(n_segments)
        self.play(Create(segs), run_time=1.5)
        self.wait(0.4)

        # Animate increasing n
        for n_new in [n_segments * 3, n_segments * 8]:
            new_segs = make_segments(n_new)
            self.play(Transform(segs, new_segs), run_time=0.8)
            self.wait(0.2)

        # Compute arc length
        try:
            integrand = sp.sqrt(1 + d_expr**2)
            L = float(sp.integrate(integrand, (x_sym, domain[0], domain[1])))
            L_str = f"{L:.4f}"
        except Exception:
            from scipy import integrate as sci
            L, _ = sci.quad(lambda x: math.sqrt(1 + _safe_eval(f_prime, x)**2), *domain)
            L_str = f"{L:.4f}"

        self.play(FadeIn(_result_box(r"L = " + L_str, 28).to_edge(DOWN, buff=0.55)))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 15 — Average Value
# ---------------------------------------------------------------------------

class AverageValueScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "sin(x)")
        domain     = p.get("domain") or [0, 3.14]
        cap        = p.get("caption", "")

        expr, f, x_sym = _parse(expression)
        a, b = domain[0], domain[1]

        try:
            avg = float(sp.integrate(expr, (x_sym, a, b)) / (b - a))
        except Exception:
            from scipy import integrate as sci
            total, _ = sci.quad(f, a, b)
            avg = total / (b - a)

        yr = _y_range(f, domain)
        ax = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph  = ax.plot(f, x_range=domain, color=CURVE_COLOR, stroke_width=2.5)
        title  = MathTex(r"f_{\text{avg}} = \frac{1}{b-a}\int_a^b f(x)\,dx",
                         font_size=30).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels), Write(title))
        self.play(Create(graph), run_time=1.5)

        # Shade area under curve
        area = ax.get_area(graph, x_range=domain, color=CURVE_COLOR, opacity=0.35)
        self.play(FadeIn(area))
        self.wait(0.4)

        # Draw average line
        avg_line = DashedLine(ax.c2p(a, avg), ax.c2p(b, avg), color=HIGHLIGHT_COLOR, stroke_width=2.5)
        avg_label = MathTex(r"f_{\text{avg}} = " + f"{avg:.3f}", font_size=24, color=HIGHLIGHT_COLOR)
        avg_label.next_to(ax.c2p(b, avg), RIGHT, buff=0.15)
        self.play(Create(avg_line), Write(avg_label))
        self.wait(0.5)

        # Morph area → rectangle of same area (the key animation)
        avg_rect = ax.get_area(
            ax.plot(lambda x: avg, x_range=domain),
            x_range=domain, color=HIGHLIGHT_COLOR, opacity=0.4,
        )
        self.play(Transform(area, avg_rect), run_time=1.5)

        self.play(FadeIn(_result_box(r"f_{\text{avg}} = " + f"{avg:.4f}", 28)
                         .to_edge(DOWN, buff=0.55)))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 16 — Improper Integral
# ---------------------------------------------------------------------------

class ImproperIntegralScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression     = p.get("expression",     "1/x**2")
        domain         = p.get("domain") or [1, 10]
        improper_bound = p.get("improper_bound", "right")
        cap            = p.get("caption", "")

        expr, f, x_sym = _parse(expression)
        a, b_display   = domain[0], domain[1]

        yr = _y_range(f, [a, min(b_display, a + 5)])
        yr[0] = min(yr[0], 0)
        ax     = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph  = ax.plot(f, x_range=[a + 0.05, b_display], color=CURVE_COLOR, stroke_width=2.5)

        inf_sym = r"\infty" if improper_bound == "right" else r"-\infty"
        a_tex   = _num(a)
        title   = MathTex(r"\int_{" + a_tex + r"}^{" + inf_sym + r"} f(x)\,dx",
                          font_size=32).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels), Write(title), Create(graph))

        # Check convergence with sympy
        try:
            lim = sp.limit(sp.integrate(expr, (x_sym, a, sp.Symbol("b"))),
                           sp.Symbol("b"), sp.oo)
            converges   = lim.is_finite
            limit_val   = float(lim) if converges else None
            conv_str    = f"{float(lim):.4f}" if converges else r"\infty"
        except Exception:
            converges, limit_val, conv_str = None, None, "?"

        # Animate expanding area
        b_tracker = ValueTracker(a + 0.5)

        def get_area():
            bv = b_tracker.get_value()
            if bv <= a + 0.05:
                return VMobject()
            return ax.get_area(graph, x_range=[a, min(bv, b_display)],
                               color=CURVE_COLOR, opacity=0.4)

        def get_val_label():
            bv = b_tracker.get_value()
            try:
                val = float(sp.integrate(expr, (x_sym, a, bv)))
                return Text(f"Area ≈ {val:.4f}", font_size=22, color=HIGHLIGHT_COLOR).to_corner(UR, buff=0.4)
            except Exception:
                return Text("Area ≈ ...", font_size=22, color=HIGHLIGHT_COLOR).to_corner(UR, buff=0.4)

        area_mob  = always_redraw(get_area)
        val_label = always_redraw(get_val_label)
        self.add(area_mob, val_label)

        self.play(b_tracker.animate.set_value(b_display), run_time=4, rate_func=smooth)
        self.wait(0.4)

        result_tex = (r"\int_{" + a_tex + r"}^{\infty} f\,dx = " + conv_str
                      if converges else r"\int_{" + a_tex + r"}^{\infty} f\,dx \to \infty\ \text{(diverges)}")
        self.play(FadeIn(_result_box(result_tex, 24).to_edge(DOWN, buff=0.55)))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 17 — U-Substitution
# ---------------------------------------------------------------------------

class USubstitutionScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression",   "cos(2*x)")
        u_expr_str = p.get("u_expression", "2*x")
        domain     = p.get("domain") or [0, 1.57]
        cap        = p.get("caption", "")

        x_sym = sp.Symbol("x")
        u_sym = sp.Symbol("u")
        expr  = sp.sympify(expression)
        u_expr = sp.sympify(u_expr_str)
        f     = sp.lambdify(x_sym, expr, modules=["numpy"])

        # After substitution: substitute x → solve(u=g(x)) into integrand
        try:
            sols = sp.solve(u_expr - u_sym, x_sym)
            if not sols:
                raise ValueError("no inverse for u")
            x_of_u = sols[0]
            du_dx  = sp.diff(u_expr, x_sym)
            if du_dx == 0:
                raise ValueError("du/dx is zero")
            integrand_u = (expr.subs(x_sym, x_of_u) / du_dx).simplify()
            f_u_raw = sp.lambdify(u_sym, integrand_u, modules=["numpy"])
            # Test eval at midpoint to ensure it produces real numbers
            test_u = 1.0
            try:
                v = float(f_u_raw(test_u))
                if not math.isfinite(v):
                    raise ValueError("non-finite test")
            except Exception:
                raise ValueError("u_func failed test eval")
            f_u = f_u_raw
        except Exception:
            integrand_u = expr
            f_u = f

        yr = _y_range(f, domain)
        # Use number-free axes for the split-screen comparison to avoid LaTeX issues
        def _simple_ax(dom, yr_, x_len=7, y_len=4.5):
            return Axes(
                x_range=[dom[0], dom[1], max(0.5, round((dom[1]-dom[0])/6, 1))],
                y_range=yr_,
                x_length=x_len, y_length=y_len,
                axis_config={"color": WHITE, "include_numbers": False},
                tips=False,
            )

        ax_x = _simple_ax(domain, yr).shift(LEFT * 2.8)

        u_domain = [float(u_expr.subs(x_sym, domain[0])),
                    float(u_expr.subs(x_sym, domain[1]))]
        yr_u = _y_range(f_u, u_domain) if u_domain[0] < u_domain[1] else yr
        ax_u = _simple_ax(u_domain, yr_u).shift(RIGHT * 2.8)

        graph_x = ax_x.plot(f,   x_range=domain,   color=CURVE_COLOR,   stroke_width=2.5)
        graph_u = ax_u.plot(f_u, x_range=u_domain, color=HIGHLIGHT_COLOR, stroke_width=2.5)

        lbl_x = Text(f"∫ f(x) dx  (original)", font_size=20, color=CURVE_COLOR).next_to(ax_x, DOWN, buff=0.3)
        lbl_u = Text(f"∫ f(u) du  (after sub)", font_size=20, color=HIGHLIGHT_COLOR).next_to(ax_u, DOWN, buff=0.3)
        arrow = Text(f"u = {str(u_expr)}", font_size=22, color=HIGHLIGHT_COLOR).center()

        title = Text(f"u-substitution:  u = {str(u_expr)}", font_size=28).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Write(title))
        self.play(Create(ax_x), Create(graph_x), Write(lbl_x))
        self.wait(0.5)
        self.play(Write(arrow))
        self.play(Create(ax_u), Create(graph_u), Write(lbl_u))
        self.wait(0.5)

        # Shade both areas
        area_x = ax_x.get_area(graph_x, x_range=domain,   color=CURVE_COLOR,    opacity=0.3)
        area_u = ax_u.get_area(graph_u, x_range=u_domain, color=HIGHLIGHT_COLOR, opacity=0.3)
        self.play(FadeIn(area_x), FadeIn(area_u))

        try:
            antideriv = sp.integrate(expr, x_sym)
            result_str = str(antideriv) + " + C"
        except Exception:
            result_str = "F(x) + C"

        # Use Text for result to avoid LaTeX brace issues with complex expressions
        result_txt = Text(f"∫ f(x) dx = {result_str}", font_size=20, color=WHITE)
        result_bg  = SurroundingRectangle(result_txt, color=WHITE, fill_color=BLACK,
                                           fill_opacity=0.75, buff=0.15, corner_radius=0.1)
        result_grp = VGroup(result_bg, result_txt).to_edge(DOWN, buff=0.55)
        self.play(FadeIn(result_grp))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 18 — Integration by Parts
# ---------------------------------------------------------------------------

class IntegrationByPartsScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        u_str  = p.get("u_expression",  "x")
        dv_str = p.get("dv_expression", "exp(x)")
        domain = p.get("domain") or [0, 2]
        cap    = p.get("caption", "")

        x_sym  = sp.Symbol("x")
        u_expr = sp.sympify(u_str)
        dv_expr = sp.sympify(dv_str)
        v_expr  = sp.integrate(dv_expr, x_sym)
        du_expr = sp.diff(u_expr, x_sym)
        result  = (u_expr * v_expr - sp.integrate(v_expr * du_expr, x_sym)).simplify()

        title = MathTex(r"\int u\,dv = uv - \int v\,du", font_size=34).to_edge(UP, buff=0.3)

        # Step-by-step algebra display
        steps = [
            MathTex(r"u = " + _clip_latex(u_expr) + r",\quad dv = " + _clip_latex(dv_expr) + r"\,dx", font_size=26),
            MathTex(r"du = " + _clip_latex(du_expr) + r"\,dx,\quad v = " + _clip_latex(v_expr), font_size=26),
            MathTex(r"\int u\,dv = uv - \int v\,du", font_size=26, color=HIGHLIGHT_COLOR),
            MathTex(r"= " + _clip_latex(u_expr) + r"\cdot " + _clip_latex(v_expr)
                    + r"\ -\ \int " + _clip_latex(v_expr * du_expr) + r"\,dx", font_size=24),
            MathTex(r"= " + _clip_latex(result) + r"\ +\ C", font_size=26, color=DERIV_COLOR),
        ]

        # Auto-scale steps wider than the screen
        for s in steps:
            if s.width > 12.5:
                s.scale(12.5 / s.width)

        for i, s in enumerate(steps):
            s.shift(DOWN * (i * 0.85 - 1.4))

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Write(title))
        for step in steps:
            self.play(FadeIn(step, shift=DOWN * 0.1), run_time=0.6)
            self.wait(0.3)

        # Highlight the final result
        self.play(Indicate(steps[-1], color=DERIV_COLOR, scale_factor=1.1))
        self.play(FadeIn(_result_box(r"\int " + _clip_latex(u_expr * dv_expr) + r"\,dx = "
                                     + _clip_latex(result) + r"\ +\ C", 22)
                         .to_edge(DOWN, buff=0.55)))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 19 — Volume by Cross-Sections
# ---------------------------------------------------------------------------

class CrossSectionScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "sin(x)")
        domain     = p.get("domain") or [0, 3.14]
        shape      = p.get("shape",      "square")
        cap        = p.get("caption", "")

        expr, f, x_sym = _parse(expression)
        yr = _y_range(f, domain)
        yr[0] = min(yr[0], 0)
        ax     = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph  = ax.plot(f, x_range=domain, color=CURVE_COLOR, stroke_width=2.5)

        shape_labels = {"square": r"A(x)=[f(x)]^2",
                        "semicircle": r"A(x)=\frac{\pi}{8}[f(x)]^2",
                        "equilateral_triangle": r"A(x)=\frac{\sqrt{3}}{4}[f(x)]^2"}
        shape_factors = {"square": 1.0,
                         "semicircle": math.pi / 8,
                         "equilateral_triangle": math.sqrt(3) / 4}
        factor = shape_factors.get(shape, 1.0)

        title = MathTex(r"V = \int A(x)\,dx\quad(" + shape + r"\text{ cross-sections})",
                        font_size=26).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels), Write(title))
        self.play(Create(graph), run_time=1.5)
        self.wait(0.3)

        # Animate cross-sections appearing left to right with 3D-perspective tilt
        n_slices = 12
        xs = np.linspace(domain[0], domain[1], n_slices + 1)
        slices = VGroup()
        tilt_x = 0.18  # horizontal shift suggesting depth
        tilt_y = 0.12  # vertical shift suggesting depth

        for i in range(n_slices):
            x_mid = (xs[i] + xs[i + 1]) / 2
            s     = max(_safe_eval(f, float(x_mid)), 0)
            w     = (xs[i + 1] - xs[i]) * ax.x_axis.unit_size * 0.88
            cx, cy_bot = ax.c2p(float(x_mid), 0)[:2]
            _, cy_top  = ax.c2p(float(x_mid), s)[:2]

            # Parallelogram with tilted top edge → cross-section seen at an angle
            poly = Polygon(
                np.array([cx - w/2,           cy_bot,           0]),
                np.array([cx + w/2,           cy_bot,           0]),
                np.array([cx + w/2 + tilt_x,  cy_top + tilt_y,  0]),
                np.array([cx - w/2 + tilt_x,  cy_top + tilt_y,  0]),
                fill_color=YELLOW, fill_opacity=0.55,
                stroke_color=WHITE, stroke_width=1.2,
            )
            slices.add(poly)

        self.play(LaggedStart(*[FadeIn(s) for s in slices], lag_ratio=0.08), run_time=2.2)

        area_label = MathTex(shape_labels.get(shape, r"A(x)"), font_size=22, color=YELLOW)
        area_label.to_corner(UR, buff=0.3)
        self.play(Write(area_label))
        self.wait(0.4)

        # Compute volume
        try:
            vol = float(factor * sp.integrate(expr**2, (x_sym, domain[0], domain[1])))
            vol_str = f"{vol:.4f}"
        except Exception:
            vol = 0.0
            vol_str = r"?"

        # Riemann-sum style transition: show running sum building up
        running_sum = 0.0
        sum_label = MathTex(r"\sum A(x_i)\,\Delta x = 0.000", font_size=24, color=HIGHLIGHT_COLOR)
        sum_label.to_corner(UL, buff=0.3)
        self.play(Write(sum_label))

        # Animate each slice contributing to the running sum
        dx_real = (domain[1] - domain[0]) / n_slices
        for i, slc in enumerate(slices):
            x_mid_real = (xs[i] + xs[i + 1]) / 2
            s_real     = max(_safe_eval(f, float(x_mid_real)), 0)
            running_sum += factor * (s_real ** 2) * dx_real

            new_sum_lbl = MathTex(
                r"\sum A(x_i)\,\Delta x = " + f"{running_sum:.3f}",
                font_size=24, color=HIGHLIGHT_COLOR,
            ).to_corner(UL, buff=0.3)

            self.play(
                Indicate(slc, color=GREEN, scale_factor=1.15),
                Transform(sum_label, new_sum_lbl),
                run_time=0.25,
            )

        # Final transition: sum → integral
        integral_eq = MathTex(
            r"\sum A(x_i)\,\Delta x \;\longrightarrow\; \int A(x)\,dx = " + vol_str,
            font_size=26, color=DERIV_COLOR,
        ).to_edge(DOWN, buff=0.55)
        self.play(FadeOut(sum_label), FadeIn(integral_eq))
        self.wait(1.0)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)
