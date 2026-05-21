import json
import math
import os

import numpy as np
import sympy as sp
from manim import *

# ---------------------------------------------------------------------------
# Shared helpers (mirrors calculus_scene.py)
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


def _make_axes(domain, yr, x_len=9.0, y_len=5.5):
    x_step = max(1, round((domain[1] - domain[0]) / 8))
    return Axes(
        x_range=[domain[0], domain[1], x_step],
        y_range=yr,
        x_length=x_len, y_length=y_len,
        axis_config={"color": WHITE, "include_numbers": True, "font_size": 20},
        tips=False,
    )


def _num(v: float) -> str:
    return str(int(v)) if v == int(v) else str(round(v, 3))


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
# LinearFunctionScene
# ---------------------------------------------------------------------------

class LinearFunctionScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression        = p.get("expression",        "2*x + 1")
        domain            = p.get("domain") or [-5, 5]
        second_expression = p.get("second_expression")
        cap               = p.get("caption", "")

        expr, f, x_sym = _parse(expression)

        # Compute slope and y-intercept
        slope = float(sp.diff(expr, x_sym).evalf())
        y_int = float(expr.subs(x_sym, 0).evalf())

        # Y-range from both lines if needed
        all_funcs = [f]
        expr2, f2, _ = (None, None, None)
        if second_expression:
            expr2, f2, _ = _parse(second_expression)
            all_funcs.append(f2)

        combined_yr = _y_range(f, domain)
        if f2:
            yr2 = _y_range(f2, domain)
            combined_yr[0] = min(combined_yr[0], yr2[0])
            combined_yr[1] = max(combined_yr[1], yr2[1])

        ax     = _make_axes(domain, combined_yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph  = ax.plot(f, x_range=domain, color=BLUE, stroke_width=3)

        slope_sign = "+" if slope >= 0 else "-"
        abs_slope  = abs(slope)
        y_int_sign = "+" if y_int >= 0 else "-"
        title = MathTex(
            r"f(x) = " + _num(slope) + r"x\ " + y_int_sign + r"\ " + _num(abs(y_int)),
            font_size=36,
        ).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels))
        self.play(Write(title))
        self.play(Create(graph), run_time=1.5)

        # Y-intercept dot
        y_int_dot = Dot(ax.c2p(0, y_int), color=YELLOW, radius=0.12)
        y_int_label = _result_box(
            r"y\text{-int} = " + _num(y_int), 24,
        ).next_to(y_int_dot, UR if y_int >= 0 else DR, buff=0.2)
        self.play(FadeIn(y_int_dot), FadeIn(y_int_label))
        self.wait(0.4)

        # Slope triangle (rise over run) — drawn at a visible region
        run_start_x = max(domain[0] + 0.5, -1.5)
        run_end_x   = min(run_start_x + 2.0, domain[1] - 0.5)
        run_y       = _safe_eval(f, run_start_x)
        rise_y      = _safe_eval(f, run_end_x)

        run_line  = DashedLine(ax.c2p(run_start_x, run_y),  ax.c2p(run_end_x, run_y),  color=GREEN)
        rise_line = DashedLine(ax.c2p(run_end_x,  run_y),  ax.c2p(run_end_x, rise_y), color=RED)

        run_label  = MathTex(r"\text{run} = " + _num(run_end_x - run_start_x), font_size=20, color=GREEN)
        run_label.next_to(run_line, DOWN, buff=0.1)
        rise_label = MathTex(r"\text{rise} = " + _num(round(rise_y - run_y, 3)), font_size=20, color=RED)
        rise_label.next_to(rise_line, RIGHT, buff=0.1)

        self.play(Create(run_line), Create(rise_line))
        self.play(Write(run_label), Write(rise_label))

        slope_box = _result_box(
            r"\text{slope} = \frac{\Delta y}{\Delta x} = " + _num(slope), 26,
        ).to_edge(DOWN, buff=0.55)
        self.play(FadeIn(slope_box))
        self.wait(0.5)

        # Second line + intersection
        if f2 and expr2 is not None:
            graph2 = ax.plot(f2, x_range=domain, color=RED, stroke_width=3)
            self.play(Create(graph2))
            try:
                x_int_val = float(sp.solve(expr - expr2, x_sym)[0].evalf())
                y_int_val = _safe_eval(f, x_int_val)
                if domain[0] <= x_int_val <= domain[1]:
                    inter_dot = Dot(ax.c2p(x_int_val, y_int_val), color=WHITE, radius=0.12)
                    inter_label = _result_box(
                        r"\text{intersection: } (" + _num(round(x_int_val, 2)) + r",\ " + _num(round(y_int_val, 2)) + r")", 22,
                    ).to_corner(UR, buff=0.3)
                    self.play(FadeIn(inter_dot), FadeIn(inter_label))
            except Exception:
                pass

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# QuadraticScene
# ---------------------------------------------------------------------------

class QuadraticScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "x**2 - 4")
        domain     = p.get("domain") or [-5, 5]
        cap        = p.get("caption", "")

        expr, f, x_sym = _parse(expression)

        # Vertex
        d_expr = sp.diff(expr, x_sym)
        try:
            vx_sym = sp.solve(d_expr, x_sym)[0]
            vx = float(vx_sym.evalf())
            vy = float(expr.subs(x_sym, vx_sym).evalf())
        except Exception:
            vx, vy = 0.0, float(expr.subs(x_sym, 0).evalf())

        # Roots
        try:
            raw_roots = sp.solve(expr, x_sym)
            real_roots = [float(r.evalf()) for r in raw_roots if r.is_real]
        except Exception:
            real_roots = []

        yr = _y_range(f, domain)
        ax = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph  = ax.plot(f, x_range=domain, color=BLUE, stroke_width=3)
        title  = MathTex(r"f(x) = " + sp.latex(expr), font_size=36).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(ax), Write(labels))
        self.play(Write(title))
        self.play(Create(graph), run_time=2)

        # Axis of symmetry (dashed vertical)
        if domain[0] <= vx <= domain[1]:
            sym_line = DashedLine(
                ax.c2p(vx, yr[0]), ax.c2p(vx, yr[1]),
                color=GRAY, dash_length=0.15, stroke_width=1.5,
            )
            self.play(Create(sym_line))

        # Vertex
        if domain[0] <= vx <= domain[1]:
            vertex_dot = Dot(ax.c2p(vx, vy), color=YELLOW, radius=0.12)
            v_dir = UP if vy < (yr[0] + yr[1]) / 2 else DOWN
            vertex_label = _result_box(
                r"\text{vertex} = (" + _num(round(vx, 2)) + r",\ " + _num(round(vy, 2)) + r")", 24,
            ).next_to(vertex_dot, v_dir, buff=0.2)
            self.play(FadeIn(vertex_dot))
            self.play(Indicate(vertex_dot, color=YELLOW, scale_factor=1.4))
            self.play(FadeIn(vertex_label))
            self.wait(0.4)

        # Roots
        root_dots = []
        for rx in real_roots:
            if domain[0] <= rx <= domain[1]:
                rdot = Dot(ax.c2p(rx, 0), color=RED, radius=0.1)
                root_dots.append(rdot)

        if root_dots:
            self.play(*[FadeIn(d) for d in root_dots])
            roots_str = r",\ ".join(_num(round(r, 2)) for r in sorted(real_roots))
            roots_box = _result_box(r"x = " + roots_str, 26).to_edge(DOWN, buff=0.55)
            self.play(FadeIn(roots_box))

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# InequalityScene
# ---------------------------------------------------------------------------

class InequalityScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression = p.get("expression", "x + 2 > 5")
        domain     = p.get("domain") or [-10, 10]
        cap        = p.get("caption", "")

        import re
        m = re.search(r"(>=|<=|>|<)", expression)
        if m:
            op = m.group(1)
            lhs_str, rhs_str = expression.split(op, 1)
        else:
            op, lhs_str, rhs_str = ">", expression, "0"

        x_sym = sp.Symbol("x")
        try:
            lhs = sp.sympify(lhs_str.strip())
            rhs = sp.sympify(rhs_str.strip())
            diff_expr = lhs - rhs
            bpts = [float(b.evalf()) for b in sp.solve(diff_expr, x_sym) if b.is_real]
        except Exception:
            bpts = [5.0]

        nl = NumberLine(
            x_range=[domain[0], domain[1], max(1, round((domain[1]-domain[0])/10))],
            length=10, color=WHITE,
            include_numbers=True, include_tip=True,
            tip_width=0.15, font_size=20,
        ).center()

        ineq_tex = expression.replace(">=", r"\geq").replace("<=", r"\leq")
        title = MathTex(ineq_tex, font_size=40).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)
        self.play(Create(nl), Write(title))

        strict = op in (">", "<")
        for bp in bpts:
            if domain[0] <= bp <= domain[1]:
                if strict:
                    pt = Circle(radius=0.13, color=RED, stroke_width=2.5, fill_opacity=0)
                    pt.move_to(nl.n2p(bp))
                else:
                    pt = Dot(nl.n2p(bp), color=RED, radius=0.13)
                self.play(FadeIn(pt))

        bp = bpts[0] if bpts else 0.0
        try:
            test_x = bp + 1
            lhs_v = float(lhs.subs(x_sym, test_x))
            rhs_v = float(rhs.subs(x_sym, test_x))
            shade_right = {">": lhs_v > rhs_v, "<": lhs_v < rhs_v,
                           ">=": lhs_v >= rhs_v, "<=": lhs_v <= rhs_v}.get(op, True)
        except Exception:
            shade_right = True

        shade = Line(
            nl.n2p(bp if shade_right else domain[0]),
            nl.n2p(domain[1] if shade_right else bp),
            color=BLUE, stroke_width=9,
        )
        self.play(Create(shade))
        self.play(FadeIn(_result_box(ineq_tex, 30).to_edge(DOWN, buff=0.55)))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# ExponentialScene
# ---------------------------------------------------------------------------

class ExponentialScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        expression      = p.get("expression",      "2**x")
        domain          = p.get("domain") or [-3, 5]
        show_key_points = p.get("show_key_points",  True)
        cap             = p.get("caption", "")

        expr, f, _ = _parse(expression)
        yr     = _y_range(f, domain)
        ax     = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")
        graph  = ax.plot(f, x_range=domain, color=BLUE, use_smoothing=True)
        title  = MathTex(r"f(x) = " + sp.latex(expr), font_size=34).to_edge(UP, buff=0.3)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)
        self.play(Create(ax), Write(labels))
        self.play(Write(title))
        self.play(Create(graph), run_time=2)

        if show_key_points:
            is_growth = _safe_eval(f, domain[1]) > _safe_eval(f, domain[0])
            y0 = max(_safe_eval(f, 0.0), 1e-9)
            mults = [2, 4, 8] if is_growth else [0.5, 0.25]
            key_xs = []
            for mult in mults:
                target = y0 * mult
                lo, hi = domain[0], domain[1]
                for _ in range(60):
                    mid = (lo + hi) / 2
                    if _safe_eval(f, mid) < target:
                        lo = mid
                    else:
                        hi = mid
                kx = (lo + hi) / 2
                if domain[0] < kx < domain[1]:
                    key_xs.append(kx)

            if key_xs:
                dashes = VGroup(*[
                    DashedLine(ax.c2p(kx, 0), ax.c2p(kx, _safe_eval(f, kx)),
                               color=GRAY, stroke_width=1.5)
                    for kx in key_xs
                ])
                dots = VGroup(*[
                    Dot(ax.c2p(kx, _safe_eval(f, kx)), color=YELLOW, radius=0.1)
                    for kx in key_xs
                ])
                self.play(Create(dashes), FadeIn(dots))
                msg = "doubles at each step" if is_growth else "halves at each step"
                self.play(Write(Text(msg, font_size=22, color=YELLOW).to_corner(UR, buff=0.3)))

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# TransformationScene
# ---------------------------------------------------------------------------

class TransformationScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        base_str  = p.get("base_expression",       "x**2")
        trans_str = p.get("transformed_expression", "(x-2)**2 + 3")
        domain    = p.get("domain") or [-5, 5]
        cap       = p.get("caption", "")

        base_expr,  f_base,  _ = _parse(base_str)
        trans_expr, f_trans, _ = _parse(trans_str)

        yr = [
            min(_y_range(f_base, domain)[0], _y_range(f_trans, domain)[0]),
            max(_y_range(f_base, domain)[1], _y_range(f_trans, domain)[1]),
            max(_y_range(f_base, domain)[2], _y_range(f_trans, domain)[2]),
        ]

        ax     = _make_axes(domain, yr)
        labels = ax.get_axis_labels(x_label="x", y_label="y")

        base_graph  = ax.plot(f_base,  x_range=domain, color=GRAY,
                              stroke_width=2, stroke_opacity=0.5)
        trans_graph = ax.plot(f_trans, x_range=domain, color=BLUE, stroke_width=2.5)

        lbl_base  = MathTex(r"f(x) = " + sp.latex(base_expr),  font_size=26, color=GRAY)
        lbl_trans = MathTex(r"g(x) = " + sp.latex(trans_expr), font_size=26, color=BLUE)
        lbl_base.to_edge(UP, buff=0.3)
        lbl_trans.next_to(lbl_base, DOWN, buff=0.1)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)
        self.play(Create(ax), Write(labels))
        self.play(Create(base_graph), Write(lbl_base))
        self.wait(0.5)
        self.play(Create(trans_graph), Write(lbl_trans), run_time=2)
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)
