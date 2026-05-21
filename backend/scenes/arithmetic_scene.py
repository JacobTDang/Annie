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


def _num(v) -> str:
    try:
        fv = float(v)
        return str(int(fv)) if fv == int(fv) else str(round(fv, 3))
    except Exception:
        return str(v)


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


def _make_fraction_bar(numer: int, denom: int, color=BLUE,
                        width: float = 6.0, height: float = 0.75) -> VGroup:
    bar = VGroup()
    piece_w = width / max(denom, 1)
    for i in range(denom):
        fill = color if i < numer else DARK_GRAY
        rect = Rectangle(
            width=piece_w - 0.04, height=height,
            fill_color=fill, fill_opacity=0.85,
            stroke_color=WHITE, stroke_width=1.5,
        )
        rect.shift(RIGHT * (i * piece_w - width / 2 + piece_w / 2))
        bar.add(rect)
    return bar


def _frac_tex(n: int, d: int, font_size: int = 34) -> MathTex:
    return MathTex(rf"\frac{{{n}}}{{{d}}}", font_size=font_size)


# ---------------------------------------------------------------------------
# NumberLineScene
# ---------------------------------------------------------------------------

class NumberLineScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        mode       = p.get("mode",             "addition")
        values     = p.get("values") or [3, 4]
        domain     = p.get("domain") or [-2, 12]
        ineq_sign  = p.get("inequality_sign",   ">")
        cap        = p.get("caption", "")

        nl = NumberLine(
            x_range=[domain[0], domain[1], 1],
            length=10,
            color=WHITE,
            include_numbers=True,
            include_tip=True,
            tip_width=0.15,
            font_size=22,
        ).move_to(ORIGIN)

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        self.play(Create(nl))

        if mode == "addition":
            a, b = float(values[0]), float(values[1])
            result = a + b
            title = MathTex(
                _num(a) + r" + " + _num(b) + r" = \, ?", font_size=44,
            ).to_edge(UP, buff=0.4)
            self.play(Write(title))

            start_dot = Dot(nl.n2p(a), color=YELLOW, radius=0.14)
            self.play(FadeIn(start_dot))

            arc = CurvedArrow(
                nl.n2p(a) + UP * 0.08,
                nl.n2p(result) + UP * 0.08,
                color=GREEN, angle=-PI / 3,
            )
            arc_lbl = MathTex(r"+" + _num(b), font_size=22, color=GREEN)
            arc_lbl.next_to(arc, UP, buff=0.08)
            self.play(Create(arc), Write(arc_lbl))

            end_dot = Dot(nl.n2p(result), color=GREEN, radius=0.14)
            self.play(FadeIn(end_dot))

            ans = _result_box(_num(a) + r" + " + _num(b) + r" = " + _num(result), 36)
            ans.to_edge(DOWN, buff=0.55)
            self.play(FadeIn(ans))

        elif mode == "subtraction":
            a, b = float(values[0]), float(values[1])
            result = a - b
            title = MathTex(
                _num(a) + r" - " + _num(b) + r" = \, ?", font_size=44,
            ).to_edge(UP, buff=0.4)
            self.play(Write(title))

            start_dot = Dot(nl.n2p(a), color=YELLOW, radius=0.14)
            self.play(FadeIn(start_dot))

            arc = CurvedArrow(
                nl.n2p(a) + UP * 0.08,
                nl.n2p(result) + UP * 0.08,
                color=RED, angle=PI / 3,
            )
            arc_lbl = MathTex(r"-" + _num(b), font_size=22, color=RED)
            arc_lbl.next_to(arc, UP, buff=0.08)
            self.play(Create(arc), Write(arc_lbl))

            end_dot = Dot(nl.n2p(result), color=RED, radius=0.14)
            self.play(FadeIn(end_dot))

            ans = _result_box(_num(a) + r" - " + _num(b) + r" = " + _num(result), 36)
            ans.to_edge(DOWN, buff=0.55)
            self.play(FadeIn(ans))

        elif mode == "inequality":
            boundary = float(values[0])
            strict = ineq_sign in (">", "<")
            shade_right = ineq_sign in (">", ">=")

            ineq_tex = ineq_sign.replace(">=", r"\geq").replace("<=", r"\leq")
            title = MathTex(r"x\ " + ineq_tex + r"\ " + _num(boundary), font_size=44)
            title.to_edge(UP, buff=0.4)
            self.play(Write(title))

            if strict:
                pt = Circle(radius=0.13, color=RED, stroke_width=2.5, fill_opacity=0)
                pt.move_to(nl.n2p(boundary))
            else:
                pt = Dot(nl.n2p(boundary), color=RED, radius=0.13)
            self.play(FadeIn(pt))

            if shade_right:
                shade = Line(nl.n2p(boundary), nl.n2p(domain[1]),
                             color=BLUE, stroke_width=9)
            else:
                shade = Line(nl.n2p(domain[0]), nl.n2p(boundary),
                             color=BLUE, stroke_width=9)
            self.play(Create(shade))

            sol = _result_box(r"x\ " + ineq_tex + r"\ " + _num(boundary), 30)
            sol.to_edge(DOWN, buff=0.55)
            self.play(FadeIn(sol))

        elif mode == "absolute_value":
            center = float(values[0])
            radius = float(values[1]) if len(values) > 1 else 3.0

            title = MathTex(
                r"|x - " + _num(center) + r"| \leq " + _num(radius), font_size=40,
            ).to_edge(UP, buff=0.4)
            self.play(Write(title))

            center_dot = Dot(nl.n2p(center), color=YELLOW, radius=0.14)
            left_dot   = Dot(nl.n2p(center - radius), color=RED, radius=0.13)
            right_dot  = Dot(nl.n2p(center + radius), color=RED, radius=0.13)
            shaded     = Line(nl.n2p(center - radius), nl.n2p(center + radius),
                              color=BLUE, stroke_width=9)

            self.play(FadeIn(center_dot))
            self.play(Create(shaded), FadeIn(left_dot), FadeIn(right_dot))

            span = Line(nl.n2p(center), nl.n2p(center + radius))
            brace = Brace(span, DOWN, color=WHITE)
            brace_lbl = brace.get_text(_num(radius), buff=0.1)
            self.play(Create(brace), Write(brace_lbl))

            ans = _result_box(
                _num(center - radius) + r" \leq x \leq " + _num(center + radius), 28,
            ).to_edge(DOWN, buff=0.55)
            self.play(FadeIn(ans))

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# FractionScene
# ---------------------------------------------------------------------------

class FractionScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        mode      = p.get("mode",      "represent")
        fractions = p.get("fractions", [[2, 3]])
        cap       = p.get("caption", "")

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        if mode == "represent":
            n, d = fractions[0]
            title = MathTex(rf"\frac{{{n}}}{{{d}}}", font_size=60).to_edge(UP, buff=0.3)
            self.play(Write(title))

            bar = _make_fraction_bar(n, d).center()
            lbl = Text(f"{n} out of {d} equal parts", font_size=26).next_to(bar, DOWN, buff=0.35)
            self.play(Create(bar), run_time=1.5)
            self.play(Write(lbl))

        elif mode == "compare":
            n1, d1 = fractions[0]
            n2, d2 = fractions[1]

            bar1 = _make_fraction_bar(n1, d1, color=BLUE).shift(UP * 0.8)
            bar2 = _make_fraction_bar(n2, d2, color=GREEN).shift(DOWN * 0.8)
            lbl1 = _frac_tex(n1, d1).next_to(bar1, LEFT, buff=0.35)
            lbl2 = _frac_tex(n2, d2).next_to(bar2, LEFT, buff=0.35)

            self.play(Create(bar1), Create(bar2))
            self.play(Write(lbl1), Write(lbl2))

            import fractions as fr_lib
            f1, f2 = fr_lib.Fraction(n1, d1), fr_lib.Fraction(n2, d2)
            sym   = ">" if f1 > f2 else ("<" if f1 < f2 else "=")
            clr   = BLUE if f1 > f2 else (GREEN if f1 < f2 else WHITE)
            cmp   = MathTex(
                rf"\frac{{{n1}}}{{{d1}}}\ {sym}\ \frac{{{n2}}}{{{d2}}}",
                font_size=40, color=clr,
            ).to_edge(DOWN, buff=0.55)
            self.play(Write(cmp))

        elif mode in ("add", "subtract"):
            n1, d1 = fractions[0]
            n2, d2 = fractions[1]
            lcd = (d1 * d2) // math.gcd(d1, d2)
            new_n1 = n1 * (lcd // d1)
            new_n2 = n2 * (lcd // d2)
            result_n = new_n1 + new_n2 if mode == "add" else new_n1 - new_n2
            g = math.gcd(abs(result_n), lcd) if result_n != 0 else 1
            simp_n, simp_d = result_n // g, lcd // g

            op_sym = "+" if mode == "add" else "-"
            title = MathTex(
                rf"\frac{{{n1}}}{{{d1}}} {op_sym} \frac{{{n2}}}{{{d2}}} = \,?",
                font_size=40,
            ).to_edge(UP, buff=0.3)
            self.play(Write(title))

            c2 = GREEN if mode == "add" else RED
            bar1 = _make_fraction_bar(n1, d1, color=BLUE).shift(UP * 0.8)
            bar2 = _make_fraction_bar(n2, d2, color=c2).shift(DOWN * 0.1)
            lbl1 = _frac_tex(n1, d1, 28).next_to(bar1, LEFT, buff=0.3)
            lbl2 = _frac_tex(n2, d2, 28).next_to(bar2, LEFT, buff=0.3)

            self.play(Create(bar1), Create(bar2))
            self.play(Write(lbl1), Write(lbl2))
            self.wait(0.4)

            if lcd != d1 or lcd != d2:
                new_bar1 = _make_fraction_bar(new_n1, lcd, color=BLUE).shift(UP * 0.8)
                new_bar2 = _make_fraction_bar(new_n2, lcd, color=c2).shift(DOWN * 0.1)
                new_lbl1 = _frac_tex(new_n1, lcd, 28).next_to(new_bar1, LEFT, buff=0.3)
                new_lbl2 = _frac_tex(new_n2, lcd, 28).next_to(new_bar2, LEFT, buff=0.3)
                lcd_note = Text(f"common denominator: {lcd}", font_size=20, color=YELLOW)
                lcd_note.to_corner(UR, buff=0.3)
                self.play(Write(lcd_note))
                self.play(
                    Transform(bar1, new_bar1), Transform(bar2, new_bar2),
                    Transform(lbl1, new_lbl1), Transform(lbl2, new_lbl2),
                    run_time=1.5,
                )
                self.wait(0.3)

            shown_n = max(result_n, 0) if mode == "subtract" else result_n
            result_bar = _make_fraction_bar(shown_n, lcd, color=YELLOW).shift(DOWN * 1.1)
            result_lbl = _frac_tex(result_n, lcd, 34).next_to(result_bar, LEFT, buff=0.3)
            self.play(FadeIn(result_bar), Write(result_lbl))

            if simp_n != result_n or simp_d != lcd:
                final_tex = rf"\frac{{{result_n}}}{{{lcd}}} = \frac{{{simp_n}}}{{{simp_d}}}"
            else:
                final_tex = rf"\frac{{{result_n}}}{{{lcd}}}"
            self.play(FadeIn(_result_box(final_tex, 32).to_edge(DOWN, buff=0.55)))

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# AreaModelScene
# ---------------------------------------------------------------------------

class AreaModelScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        mode  = p.get("mode", "integer")
        a_str = str(p.get("a", "4"))
        b_str = str(p.get("b", "6"))
        cap   = p.get("caption", "")

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)

        if mode == "integer":
            a = max(1, min(int(float(a_str)), 12))
            b = max(1, min(int(float(b_str)), 12))
            cell = min(5.5 / max(a, b), 0.85)

            title = MathTex(f"{a} \\times {b} = \\,?", font_size=44).to_edge(UP, buff=0.3)
            self.play(Write(title))

            grid = VGroup()
            for row in range(b):
                for col in range(a):
                    sq = Square(
                        side_length=cell - 0.04,
                        fill_color=BLUE_D, fill_opacity=0.0,
                        stroke_color=WHITE, stroke_width=1.5,
                    )
                    sq.move_to(RIGHT * col * cell + DOWN * row * cell)
                    grid.add(sq)
            grid.center()

            self.play(Create(grid), run_time=1.5)
            self.play(
                LaggedStart(
                    *[sq.animate.set_fill(BLUE_D, opacity=0.75) for sq in grid],
                    lag_ratio=0.04,
                ),
                run_time=2,
            )

            ans = _result_box(f"{a} \\times {b} = {a * b}", 38).to_edge(DOWN, buff=0.55)
            self.play(FadeIn(ans))

        elif mode == "algebraic":
            x_sym = sp.Symbol("x")
            a_expr = sp.sympify(a_str)
            b_expr = sp.sympify(b_str)
            product = sp.expand(a_expr * b_expr)

            a_terms = a_expr.as_ordered_terms()
            b_terms = b_expr.as_ordered_terms()
            if len(a_terms) < 2:
                a_terms = [a_expr, sp.Integer(0)]
            if len(b_terms) < 2:
                b_terms = [b_expr, sp.Integer(0)]

            title = MathTex(
                r"\left(" + sp.latex(a_expr) + r"\right)\!\left(" + sp.latex(b_expr) + r"\right) = \,?",
                font_size=36,
            ).to_edge(UP, buff=0.3)
            self.play(Write(title))

            W, H = 3.2, 2.4
            cell_colors = [BLUE_D, TEAL_D, TEAL_D, GREEN_D]
            sub_products = [
                sp.expand(a_terms[0] * b_terms[0]),
                sp.expand(a_terms[0] * b_terms[1]),
                sp.expand(a_terms[1] * b_terms[0]),
                sp.expand(a_terms[1] * b_terms[1]),
            ]

            cells = VGroup()
            labels = VGroup()
            for idx, (prod, clr) in enumerate(zip(sub_products, cell_colors)):
                row, col = idx // 2, idx % 2
                rect = Rectangle(
                    width=W - 0.05, height=H - 0.05,
                    fill_color=clr, fill_opacity=0.65,
                    stroke_color=WHITE, stroke_width=2,
                )
                rect.move_to(RIGHT * (col - 0.5) * W + DOWN * (row - 0.5) * H)
                lbl = MathTex(sp.latex(prod), font_size=28)
                lbl.move_to(rect)
                cells.add(rect)
                labels.add(lbl)

            grid_group = VGroup(cells, labels).center()

            self.play(Create(cells), run_time=1.5)
            self.play(Write(labels))

            ans = _result_box(r"= " + sp.latex(product), 32).to_edge(DOWN, buff=0.55)
            self.play(FadeIn(ans))

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)
