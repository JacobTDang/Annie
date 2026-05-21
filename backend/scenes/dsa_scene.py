"""
DSA visualization scenes. Every scene runs the actual algorithm in Python
to generate steps — the LLM only supplies the input data.
"""
import json
import math
import os
from collections import deque

import numpy as np
from manim import *

from scenes.dsa_primitives import CodePanel, ComplexityBadge

# ---------------------------------------------------------------------------
# Legacy pseudocode + complexity catalog (Phase 10B)
# Same shape as _PATTERN_CATALOG in dsa_pattern_scene.py — keeps these older
# scenes visually consistent with the modern pattern scenes (CodePanel UL,
# ComplexityBadge next to title).
# ---------------------------------------------------------------------------

_LEGACY_CATALOG = {
    ("array_pointer", "binary_search"): (
        "l, r = 0, len(a) - 1\nwhile l <= r:\n    m = (l + r) // 2\n    if a[m] == target: return m\n    elif a[m] < target: l = m + 1\n    else: r = m - 1\nreturn -1",
        "O(log n)", "O(1)"),
    ("array_pointer", "two_pointers"): (
        "l, r = 0, len(a) - 1\nwhile l < r:\n    s = a[l] + a[r]\n    if s == target: return [l, r]\n    elif s < target: l += 1\n    else: r -= 1",
        "O(n)", "O(1)"),
    ("array_pointer", "palindrome"): (
        "l, r = 0, len(s) - 1\nwhile l < r:\n    if s[l] != s[r]: return False\n    l, r = l + 1, r - 1\nreturn True",
        "O(n)", "O(1)"),

    ("sliding_window", "max_subarray_fixed"): (
        "window_sum = sum(a[:k])\nbest = window_sum\nfor i in range(k, len(a)):\n    window_sum += a[i] - a[i - k]\n    best = max(best, window_sum)",
        "O(n)", "O(1)"),
    ("sliding_window", "longest_unique_substring"): (
        "seen = {}\nl = best = 0\nfor r, c in enumerate(s):\n    if c in seen and seen[c] >= l:\n        l = seen[c] + 1\n    seen[c] = r\n    best = max(best, r - l + 1)",
        "O(n)", "O(k)"),

    ("linked_list", "reverse"): (
        "prev = None\ncurr = head\nwhile curr:\n    nxt = curr.next\n    curr.next = prev\n    prev = curr\n    curr = nxt\nreturn prev",
        "O(n)", "O(1)"),
    ("linked_list", "find_middle"): (
        "slow = fast = head\nwhile fast and fast.next:\n    slow = slow.next\n    fast = fast.next.next\nreturn slow",
        "O(n)", "O(1)"),
    ("linked_list", "merge_sorted"): (
        "dummy = ListNode()\ntail = dummy\nwhile a and b:\n    if a.val <= b.val:\n        tail.next = a; a = a.next\n    else:\n        tail.next = b; b = b.next\n    tail = tail.next\ntail.next = a or b",
        "O(n + m)", "O(1)"),

    ("tree_traversal", "bfs"): (
        "queue = deque([root])\nwhile queue:\n    node = queue.popleft()\n    visit(node)\n    if node.left:  queue.append(node.left)\n    if node.right: queue.append(node.right)",
        "O(n)", "O(w)"),
    ("tree_traversal", "dfs"): (
        "def dfs(node):\n    if not node: return\n    visit(node)\n    dfs(node.left)\n    dfs(node.right)",
        "O(n)", "O(h)"),
    ("tree_traversal", "inorder"): (
        "def inorder(node):\n    if not node: return\n    inorder(node.left)\n    visit(node)\n    inorder(node.right)",
        "O(n)", "O(h)"),
    ("tree_traversal", "preorder"): (
        "def preorder(node):\n    if not node: return\n    visit(node)\n    preorder(node.left)\n    preorder(node.right)",
        "O(n)", "O(h)"),
    ("tree_traversal", "postorder"): (
        "def postorder(node):\n    if not node: return\n    postorder(node.left)\n    postorder(node.right)\n    visit(node)",
        "O(n)", "O(h)"),
    ("tree_traversal", "height"): (
        "def height(node):\n    if not node: return 0\n    return 1 + max(height(node.left),\n                  height(node.right))",
        "O(n)", "O(h)"),

    ("graph_traversal", "bfs"): (
        "queue = deque([start])\nvisited = {start}\nwhile queue:\n    u = queue.popleft()\n    for v in adj[u]:\n        if v not in visited:\n            visited.add(v)\n            queue.append(v)",
        "O(V + E)", "O(V)"),
    ("graph_traversal", "dfs"): (
        "def dfs(u):\n    visited.add(u)\n    for v in adj[u]:\n        if v not in visited:\n            dfs(v)",
        "O(V + E)", "O(V)"),
    ("graph_traversal", "has_cycle"): (
        "color = {u: 'white' for u in nodes}\ndef dfs(u):\n    color[u] = 'gray'\n    for v in adj[u]:\n        if color[v] == 'gray': return True\n        if color[v] == 'white' and dfs(v): return True\n    color[u] = 'black'; return False",
        "O(V + E)", "O(V)"),

    ("dp_array", "fibonacci"): (
        "dp = [0] * (n + 1)\ndp[1] = 1\nfor i in range(2, n + 1):\n    dp[i] = dp[i - 1] + dp[i - 2]\nreturn dp[n]",
        "O(n)", "O(n)"),
    ("dp_array", "climbing_stairs"): (
        "dp = [0] * (n + 1)\ndp[0] = dp[1] = 1\nfor i in range(2, n + 1):\n    dp[i] = dp[i - 1] + dp[i - 2]\nreturn dp[n]",
        "O(n)", "O(n)"),
    ("dp_array", "house_robber"): (
        "dp = [0] * len(a)\ndp[0] = a[0]\ndp[1] = max(a[0], a[1])\nfor i in range(2, len(a)):\n    dp[i] = max(dp[i - 1], dp[i - 2] + a[i])\nreturn dp[-1]",
        "O(n)", "O(n)"),
    ("dp_array", "coin_change"): (
        "dp = [amount + 1] * (amount + 1)\ndp[0] = 0\nfor x in range(1, amount + 1):\n    for c in coins:\n        if c <= x:\n            dp[x] = min(dp[x], dp[x - c] + 1)\nreturn -1 if dp[amount] > amount else dp[amount]",
        "O(amount × |coins|)", "O(amount)"),

    ("stack_queue", "stack"): (
        "stack = []\nfor op in ops:\n    if op == 'push': stack.append(v)\n    elif op == 'pop':  stack.pop()",
        "O(1) per op", "O(n)"),
    ("stack_queue", "queue"): (
        "queue = deque()\nfor op in ops:\n    if op == 'enqueue': queue.append(v)\n    elif op == 'dequeue': queue.popleft()",
        "O(1) per op", "O(n)"),
}


def _legacy_polish(title, scene_key: str, algorithm: str, custom_code: str = ""):
    """Build a CodePanel + ComplexityBadge for a legacy scene. Same idea as
    _polish() in dsa_pattern_scene.py but local so dsa_scene.py stays
    self-contained. Returns (code_panel, badge_vgroup, has_panel).
    Always anchored UL with conservative font_size and max_width that fit
    alongside the legacy scenes' wider centered strips.
    """
    entry = _LEGACY_CATALOG.get((scene_key, algorithm))
    custom_code = (custom_code or "").strip()
    if not entry and not custom_code:
        return None, None
    if custom_code:
        pseudo = custom_code
        t_complex, s_complex = (entry[1], entry[2]) if entry else ("—", "—")
    else:
        pseudo, t_complex, s_complex = entry
    code_panel = CodePanel(pseudo, anchor=UL, font_size=13, max_width=3.8)
    code_panel.is_custom = bool(custom_code)
    badge = ComplexityBadge(time=t_complex, space=s_complex, font_size=14)
    # Avoid collision with UR-anchored panels when title is long
    if title.width > 6.0:
        badge.vgroup.next_to(title, DOWN, buff=0.15)
    else:
        badge.vgroup.next_to(title, RIGHT, buff=0.3)
    return code_panel, badge.vgroup


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _strip_dict_nulls(obj):
    """Recursively drop keys whose value is None from dicts.

    Agents sometimes emit JSON like ``{"n": null, "amount": null}`` which
    makes downstream ``int(p.get("n", 8))`` raise TypeError because
    ``.get("n", 8)`` returns the explicit ``None`` instead of the default.
    Stripping nulls at the boundary lets every scene's defaults work.
    List elements keep their None entries — only dict KEYS are dropped,
    so list shapes (e.g. coin arrays) stay intact.
    """
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


def _make_cells(values: list, cell_size: float = None) -> list:
    """Square + label cells with adaptive sizing based on array length."""
    if cell_size is None:
        n = len(values)
        cell_size = (1.0  if n <= 4  else
                     0.85 if n <= 7  else
                     0.70 if n <= 10 else
                     max(0.50, 9.0 / n))
    font = max(16, int(24 * cell_size))
    cells = []
    for v in values:
        sq = Square(side_length=cell_size, fill_color="#1a3a5c", fill_opacity=0.70,
                    stroke_color=WHITE, stroke_width=2)
        lbl = Text(str(v), font_size=font, color=WHITE)
        cells.append(VGroup(sq, lbl))
    return cells


def _result_box(tex: str, font_size: int = 28) -> VGroup:
    label = MathTex(tex, font_size=font_size)
    box = SurroundingRectangle(label, color=WHITE, fill_color=BLACK,
                                fill_opacity=0.75, buff=0.15, corner_radius=0.1)
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


def _action_text(msg: str) -> Text:
    return Text(msg, font_size=22).to_edge(DOWN, buff=0.95)


# ---------------------------------------------------------------------------
# Algorithm step generators (pure Python — always correct)
# ---------------------------------------------------------------------------

def _binary_search_steps(arr: list, target: int) -> list:
    steps = []
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            steps.append({"lo": lo, "hi": hi, "mid": mid, "found": True,
                           "action": f"arr[{mid}]={arr[mid]} == {target}  →  Found!"})
            return steps
        elif arr[mid] < target:
            steps.append({"lo": lo, "hi": hi, "mid": mid, "found": False,
                           "action": f"arr[{mid}]={arr[mid]} < {target}  →  go right"})
            lo = mid + 1
        else:
            steps.append({"lo": lo, "hi": hi, "mid": mid, "found": False,
                           "action": f"arr[{mid}]={arr[mid]} > {target}  →  go left"})
            hi = mid - 1
    steps.append({"lo": lo, "hi": hi, "mid": -1, "found": False,
                   "action": f"{target} not found in array"})
    return steps


def _two_pointer_steps(arr: list, target: int) -> list:
    steps = []
    left, right = 0, len(arr) - 1
    while left < right:
        s = arr[left] + arr[right]
        if s == target:
            steps.append({"left": left, "right": right, "found": True,
                           "action": f"{arr[left]}+{arr[right]}={s}  →  Found pair!"})
            return steps
        elif s < target:
            steps.append({"left": left, "right": right, "found": False,
                           "action": f"{arr[left]}+{arr[right]}={s} < {target}  →  move left ▶"})
            left += 1
        else:
            steps.append({"left": left, "right": right, "found": False,
                           "action": f"{arr[left]}+{arr[right]}={s} > {target}  →  move right ◀"})
            right -= 1
    steps.append({"left": left, "right": right, "found": False,
                   "action": "No pair found"})
    return steps


def _palindrome_steps(arr: list) -> tuple:
    steps = []
    left, right = 0, len(arr) - 1
    while left < right:
        if str(arr[left]) == str(arr[right]):
            steps.append({"left": left, "right": right, "match": True,
                           "action": f"'{arr[left]}' == '{arr[right]}'  ✓"})
        else:
            steps.append({"left": left, "right": right, "match": False,
                           "action": f"'{arr[left]}' ≠ '{arr[right]}'  ✗  Not a palindrome"})
            return steps, False
        left += 1
        right -= 1
    return steps, True


def _sliding_window_fixed_steps(arr: list, k: int) -> list:
    n = len(arr)
    k = min(k, n)
    steps = []
    current = sum(arr[:k])
    steps.append({"start": 0, "end": k - 1, "current": current, "max_val": current,
                   "action": f"Initial window sum = {current}"})
    max_val = current
    for i in range(1, n - k + 1):
        current = current - arr[i - 1] + arr[i + k - 1]
        max_val = max(max_val, current)
        steps.append({"start": i, "end": i + k - 1, "current": current, "max_val": max_val,
                       "action": f"Slide right: sum = {current}  (max so far: {max_val})"})
    return steps


def _sliding_window_unique_steps(arr: list) -> list:
    steps = []
    left = 0
    seen = {}
    max_len = 0
    for right in range(len(arr)):
        ch = str(arr[right])
        if ch in seen and seen[ch] >= left:
            left = seen[ch] + 1
        seen[ch] = right
        length = right - left + 1
        max_len = max(max_len, length)
        steps.append({"start": left, "end": right, "length": length, "max_len": max_len,
                       "action": f"Window '{arr[left:right+1]}' length={length}  max={max_len}"
                       if hasattr(arr[left], '__iter__') else
                       f"Window [{left}..{right}] len={length}  max={max_len}"})
    return steps


def _tree_positions(values: list) -> dict:
    positions = {}
    width = 11.0
    for idx in range(len(values)):
        if values[idx] is None:
            continue
        level = int(math.log2(idx + 1)) if idx > 0 else 0
        pos_in_level = idx - (2 ** level - 1)
        level_width = 2 ** level
        x = (pos_in_level + 0.5) * (width / level_width) - width / 2
        y = 2.5 - level * 1.5
        positions[idx] = np.array([x, y, 0])
    return positions


def _inorder(values, idx=0):
    if idx >= len(values) or values[idx] is None:
        return []
    return _inorder(values, 2*idx+1) + [idx] + _inorder(values, 2*idx+2)


def _preorder(values, idx=0):
    if idx >= len(values) or values[idx] is None:
        return []
    return [idx] + _preorder(values, 2*idx+1) + _preorder(values, 2*idx+2)


def _postorder(values, idx=0):
    if idx >= len(values) or values[idx] is None:
        return []
    return _postorder(values, 2*idx+1) + _postorder(values, 2*idx+2) + [idx]


def _bfs_order(values):
    order = []
    q = deque([0])
    while q:
        idx = q.popleft()
        if idx >= len(values) or values[idx] is None:
            continue
        order.append(idx)
        q.append(2 * idx + 1)
        q.append(2 * idx + 2)
    return order


def _graph_bfs_steps(adj: dict, start: int, n: int, positions: list = None) -> list:
    """BFS steps, visiting neighbors left-to-right on screen (by x-position)."""
    steps = []
    visited = [False] * n
    visited[start] = True
    q = deque([start])
    while q:
        node = q.popleft()
        neighbors_added = []
        # Sort neighbors by screen x-position (left → right); fall back to node index
        neighbors = sorted(
            adj.get(node, []),
            key=lambda nb: positions[nb][0] if positions is not None else nb,
        )
        for nb in neighbors:
            if not visited[nb]:
                visited[nb] = True
                q.append(nb)
                neighbors_added.append(nb)
        steps.append({"visit": node, "queue": list(q),
                       "action": f"Visit {node}, add {neighbors_added} to queue"})
    return steps


def _graph_dfs_steps(adj: dict, start: int, n: int, positions: list = None) -> list:
    """DFS steps, pushing neighbors right-to-left so left is popped first."""
    steps = []
    visited = [False] * n
    stack = [start]
    while stack:
        node = stack.pop()
        if visited[node]:
            continue
        visited[node] = True
        neighbors_added = []
        # Push in reverse x-order so the leftmost neighbor is popped first
        neighbors = sorted(
            adj.get(node, []),
            key=lambda nb: positions[nb][0] if positions is not None else nb,
            reverse=True,
        )
        for nb in neighbors:
            if not visited[nb]:
                stack.append(nb)
                neighbors_added.append(nb)
        steps.append({"visit": node, "stack": list(stack),
                       "action": f"Visit {node}, push {neighbors_added} to stack"})
    return steps


def _dp_fibonacci_steps(n: int) -> list:
    n = min(n, 12)
    dp = [0] * (n + 1)
    if n >= 1:
        dp[1] = 1
    steps = [{"idx": 0, "value": 0, "deps": [], "formula": "dp[0]=0"}]
    if n >= 1:
        steps.append({"idx": 1, "value": 1, "deps": [], "formula": "dp[1]=1"})
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
        steps.append({"idx": i, "value": dp[i], "deps": [i-1, i-2],
                       "formula": f"dp[{i}]=dp[{i-1}]+dp[{i-2}]={dp[i]}"})
    return steps, dp


def _dp_climbing_stairs_steps(n: int) -> list:
    n = min(n, 12)
    dp = [0] * (n + 1)
    dp[0], dp[1] = 1, 1
    steps = [{"idx": 0, "value": 1, "deps": [], "formula": "dp[0]=1"},
              {"idx": 1, "value": 1, "deps": [], "formula": "dp[1]=1"}]
    for i in range(2, n + 1):
        dp[i] = dp[i-1] + dp[i-2]
        steps.append({"idx": i, "value": dp[i], "deps": [i-1, i-2],
                       "formula": f"dp[{i}]={dp[i-1]}+{dp[i-2]}={dp[i]}"})
    return steps, dp


def _dp_house_robber_steps(n: int) -> list:
    n = min(n, 10)
    import random
    random.seed(42)
    houses = [random.randint(1, 9) for _ in range(n)]
    dp = [0] * n
    dp[0] = houses[0]
    steps = [{"idx": 0, "value": dp[0], "deps": [], "formula": f"dp[0]={dp[0]}",
               "house": houses[0]}]
    if n > 1:
        dp[1] = max(houses[0], houses[1])
        steps.append({"idx": 1, "value": dp[1], "deps": [0],
                       "formula": f"dp[1]=max({houses[0]},{houses[1]})={dp[1]}",
                       "house": houses[1]})
    for i in range(2, n):
        dp[i] = max(dp[i-1], dp[i-2] + houses[i])
        steps.append({"idx": i, "value": dp[i], "deps": [i-1, i-2],
                       "formula": f"dp[{i}]=max({dp[i-1]},{dp[i-2]}+{houses[i]})={dp[i]}",
                       "house": houses[i]})
    return steps, dp, houses


# ---------------------------------------------------------------------------
# Scene 1 — Array Pointer (binary search / two pointers / palindrome)
# ---------------------------------------------------------------------------

class ArrayPointerScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        array     = p.get("array") or [1, 3, 5, 7, 9, 11, 13]
        algorithm = p.get("algorithm", "binary_search")
        target    = p.get("target",    7)
        cap       = p.get("caption",   "")

        cells = _make_cells([str(v) for v in array])
        row   = VGroup(*cells).arrange(RIGHT, buff=0.1).center().shift(UP * 0.8)

        idx_labels = VGroup(*[
            Text(str(i), font_size=15, color=GRAY).next_to(cells[i], DOWN, buff=0.06)
            for i in range(len(cells))
        ])

        titles = {"binary_search": f"Binary Search  target = {target}",
                  "two_pointers":  f"Two Pointers  target = {target}",
                  "palindrome":    "Palindrome Check"}
        title = Text(titles.get(algorithm, algorithm), font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _legacy_polish(title, "array_pointer", algorithm,
                                              custom_code=p.get("pseudocode", ""))

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)
        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(row), Write(idx_labels))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.wait(0.3)

        if algorithm == "binary_search":
            steps = _binary_search_steps(list(array), target)
            self._run_binary_search(cells, steps)
        elif algorithm == "two_pointers":
            steps = _two_pointer_steps(list(array), int(target) if target else 0)
            self._run_two_pointer(cells, steps)
        elif algorithm == "palindrome":
            steps, is_pal = _palindrome_steps(list(array))
            self._run_palindrome(cells, steps, is_pal)

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)

    def _ptr(self, label: str, color) -> VGroup:
        # Shorter, thinner arrow + smaller label so multiple pointers don't collide visually
        arrow = Arrow(DOWN * 0.45, ORIGIN, color=color, buff=0,
                      max_tip_length_to_length_ratio=0.4, stroke_width=2.5)
        lbl = Text(label, font_size=15, color=color, weight=BOLD).next_to(arrow.get_start(), DOWN, buff=0.04)
        return VGroup(arrow, lbl)

    def _run_binary_search(self, cells, steps):
        lo_ptr  = self._ptr("L", GREEN)
        hi_ptr  = self._ptr("R", RED)
        mid_ptr = self._ptr("M", YELLOW)

        def _place(ptr, cell, extra_down=0):
            ptr.move_to(cell.get_bottom() + DOWN * (0.3 + extra_down))

        _place(lo_ptr,  cells[steps[0]["lo"]])
        _place(hi_ptr,  cells[steps[0]["hi"]])
        _place(mid_ptr, cells[steps[0]["mid"]], 0.25)
        self.play(FadeIn(lo_ptr), FadeIn(hi_ptr), FadeIn(mid_ptr))

        action = _action_text(steps[0]["action"])
        self.play(Write(action))

        for step in steps:
            anims = [
                lo_ptr.animate.move_to(cells[step["lo"]].get_bottom() + DOWN * 0.3),
                hi_ptr.animate.move_to(cells[step["hi"]].get_bottom() + DOWN * 0.3),
            ]
            if step["mid"] >= 0:
                anims.append(mid_ptr.animate.move_to(cells[step["mid"]].get_bottom() + DOWN * 0.55))
                self.play(*anims, run_time=0.5)
                self.play(cells[step["mid"]][0].animate.set_fill(
                    GREEN if step["found"] else YELLOW, opacity=0.8), run_time=0.3)
            else:
                self.play(*anims, run_time=0.5)

            new_action = _action_text(step["action"])
            self.play(Transform(action, new_action), run_time=0.3)
            self.wait(0.5)

    def _run_two_pointer(self, cells, steps):
        l_ptr = self._ptr("L", GREEN)
        r_ptr = self._ptr("R", RED)
        l_ptr.move_to(cells[steps[0]["left"]].get_bottom()  + DOWN * 0.3)
        r_ptr.move_to(cells[steps[0]["right"]].get_bottom() + DOWN * 0.3)
        self.play(FadeIn(l_ptr), FadeIn(r_ptr))
        action = _action_text(steps[0]["action"])
        self.play(Write(action))

        for step in steps:
            clr = GREEN if step["found"] else YELLOW
            self.play(
                cells[step["left"]][0].animate.set_fill(clr, opacity=0.7),
                cells[step["right"]][0].animate.set_fill(clr, opacity=0.7),
                run_time=0.3,
            )
            self.play(
                l_ptr.animate.move_to(cells[step["left"]].get_bottom()  + DOWN * 0.3),
                r_ptr.animate.move_to(cells[step["right"]].get_bottom() + DOWN * 0.3),
                run_time=0.4,
            )
            self.play(Transform(action, _action_text(step["action"])), run_time=0.3)
            self.wait(0.5)
            if not step["found"]:
                self.play(
                    cells[step["left"]][0].animate.set_fill(BLUE_E, opacity=0.55),
                    cells[step["right"]][0].animate.set_fill(BLUE_E, opacity=0.55),
                    run_time=0.2,
                )

    def _run_palindrome(self, cells, steps, is_pal):
        l_ptr = self._ptr("L", GREEN)
        r_ptr = self._ptr("R", RED)
        if steps:
            l_ptr.move_to(cells[steps[0]["left"]].get_bottom()  + DOWN * 0.3)
            r_ptr.move_to(cells[steps[0]["right"]].get_bottom() + DOWN * 0.3)
        self.play(FadeIn(l_ptr), FadeIn(r_ptr))
        action = _action_text("Checking each pair from outside in...")
        self.play(Write(action))

        for step in steps:
            clr = GREEN if step["match"] else RED
            self.play(
                cells[step["left"]][0].animate.set_fill(clr, opacity=0.7),
                cells[step["right"]][0].animate.set_fill(clr, opacity=0.7),
                l_ptr.animate.move_to(cells[step["left"]].get_bottom()  + DOWN * 0.3),
                r_ptr.animate.move_to(cells[step["right"]].get_bottom() + DOWN * 0.3),
                run_time=0.4,
            )
            self.play(Transform(action, _action_text(step["action"])), run_time=0.3)
            self.wait(0.5)

        verdict = "Palindrome!" if is_pal else "Not a Palindrome"
        clr_v   = GREEN if is_pal else RED
        verdict_lbl = Text(verdict, font_size=30, color=clr_v)
        box = SurroundingRectangle(verdict_lbl, color=WHITE, fill_color=BLACK,
                                    fill_opacity=0.75, buff=0.15, corner_radius=0.1)
        verdict_group = VGroup(box, verdict_lbl).to_edge(DOWN, buff=1.75)
        self.play(FadeIn(verdict_group))


# ---------------------------------------------------------------------------
# Scene 2 — Sliding Window
# ---------------------------------------------------------------------------

class SlidingWindowScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        array     = p.get("array") or [2, 1, 5, 1, 3, 2]
        algorithm = p.get("algorithm", "max_subarray_fixed")
        k         = int(p.get("k",    3))
        cap       = p.get("caption",  "")

        cells = _make_cells([str(v) for v in array])
        row   = VGroup(*cells).arrange(RIGHT, buff=0.1).center().shift(UP * 0.5)

        if algorithm == "max_subarray_fixed":
            title = Text(f"Sliding Window — Max Sum of {k} Elements", font_size=26).to_edge(UP, buff=0.3)
            steps = _sliding_window_fixed_steps([int(v) for v in array], k)
        else:
            title = Text("Sliding Window — Longest Unique Substring", font_size=26).to_edge(UP, buff=0.3)
            steps = _sliding_window_unique_steps(list(array))

        code_panel, badge_v = _legacy_polish(title, "sliding_window", algorithm,
                                              custom_code=p.get("pseudocode", ""))

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)
        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(row))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.wait(0.3)

        # Highlight rectangle around the window
        rect = SurroundingRectangle(
            VGroup(*cells[steps[0]["start"]:steps[0]["end"]+1]),
            color=YELLOW, buff=0.08, corner_radius=0.05, stroke_width=2.5,
        )
        for c in cells[steps[0]["start"]:steps[0]["end"]+1]:
            c[0].set_fill(YELLOW, opacity=0.5)

        val_key = "current" if algorithm == "max_subarray_fixed" else "length"
        label_word = "Sum" if algorithm == "max_subarray_fixed" else "Length"
        info = Text(f"{label_word} = {steps[0][val_key]}", font_size=24).to_corner(UR, buff=0.4)
        self.play(Create(rect), FadeIn(info))

        action = _action_text(steps[0]["action"])
        self.play(Write(action))
        self.wait(0.5)

        best_start, best_end = steps[0]["start"], steps[0]["end"]

        for step in steps[1:]:
            # Reset old window color
            for c in cells:
                c[0].set_fill(BLUE_E, opacity=0.55)
            # Highlight new window
            for c in cells[step["start"]:step["end"]+1]:
                c[0].set_fill(YELLOW, opacity=0.5)

            new_rect = SurroundingRectangle(
                VGroup(*cells[step["start"]:step["end"]+1]),
                color=YELLOW, buff=0.08, corner_radius=0.05, stroke_width=2.5,
            )
            new_info = Text(f"{label_word} = {step[val_key]}", font_size=24).to_corner(UR, buff=0.4)
            self.play(
                Transform(rect, new_rect),
                Transform(info, new_info),
                Transform(action, _action_text(step["action"])),
                run_time=0.6,
            )
            if algorithm == "max_subarray_fixed":
                if step["current"] == step["max_val"]:
                    best_start, best_end = step["start"], step["end"]
            self.wait(0.3)

        # Highlight the best window
        for c in cells:
            c[0].set_fill(BLUE_E, opacity=0.55)
        for c in cells[best_start:best_end+1]:
            c[0].set_fill(GREEN, opacity=0.65)

        max_key = "max_val" if algorithm == "max_subarray_fixed" else "max_len"
        self.play(FadeIn(_result_box(f"Max = {steps[-1][max_key]}", 30).to_edge(DOWN, buff=1.75)))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 3 — Linked List
# ---------------------------------------------------------------------------

class LinkedListScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        values    = p.get("values") or [1, 2, 3, 4, 5]
        algorithm = p.get("algorithm", "reverse")
        values2   = p.get("values2")
        cap       = p.get("caption",  "")

        title_map = {"reverse": "Reverse a Linked List",
                     "find_middle": "Find Middle of Linked List",
                     "merge_sorted": "Merge Two Sorted Lists"}
        title = Text(title_map.get(algorithm, algorithm), font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _legacy_polish(title, "linked_list", algorithm,
                                              custom_code=p.get("pseudocode", ""))

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)
        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        if algorithm == "reverse":
            self._reverse(values)
        elif algorithm == "find_middle":
            self._find_middle(values)
        elif algorithm == "merge_sorted":
            self._merge_sorted(values, values2 or [])

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)

    def _build_chain(self, values, y_offset=0):
        """Returns (nodes, arrows) where nodes[i] is VGroup(circle, text)."""
        nodes, arrows = [], []
        spacing = min(2.2, 11.0 / max(len(values), 1))
        start_x = -(len(values) - 1) * spacing / 2

        for i, v in enumerate(values):
            cx = start_x + i * spacing
            circle = Circle(radius=0.38, color=WHITE, fill_color=DARK_GRAY,
                             fill_opacity=0.85, stroke_width=2)
            label  = Text(str(v), font_size=22, color=WHITE)
            node   = VGroup(circle, label).move_to(np.array([cx, y_offset, 0]))
            nodes.append(node)
            if i > 0:
                arr = Arrow(nodes[i-1].get_right(), node.get_left(),
                             buff=0.08, color=GRAY, stroke_width=2,
                             max_tip_length_to_length_ratio=0.25)
                arrows.append(arr)

        null_lbl = Text("null", font_size=18, color=GRAY)
        null_lbl.next_to(nodes[-1], RIGHT, buff=0.3)
        null_arr = Arrow(nodes[-1].get_right(), null_lbl.get_left(),
                          buff=0.05, color=GRAY, stroke_width=2,
                          max_tip_length_to_length_ratio=0.2)
        return nodes, arrows, null_lbl, null_arr

    def _reverse(self, values):
        nodes, arrows, null_lbl, null_arr = self._build_chain(values, y_offset=0.5)
        head_label = Text("head", font_size=18, color=YELLOW).next_to(nodes[0], UP, buff=0.2)

        self.play(FadeIn(VGroup(*nodes)), Create(VGroup(*arrows)),
                  Write(null_lbl), Create(null_arr), Write(head_label))
        self.wait(0.5)

        # Animate reversal step by step
        prev_lbl = Text("prev=null", font_size=20, color=GREEN).to_corner(DL, buff=0.4)
        curr_lbl = Text(f"curr={values[0]}", font_size=20, color=YELLOW).to_corner(DR, buff=0.4)
        self.play(Write(prev_lbl), Write(curr_lbl))

        n = len(values)
        for i in range(n):
            self.play(nodes[i][0].animate.set_fill(YELLOW, opacity=0.8), run_time=0.3)
            new_prev = Text(f"prev={values[i]}", font_size=20, color=GREEN).to_corner(DL, buff=0.4)
            new_curr = Text(f"curr={values[i+1]}" if i+1 < n else "curr=null",
                             font_size=20, color=YELLOW).to_corner(DR, buff=0.4)
            self.play(Transform(prev_lbl, new_prev), Transform(curr_lbl, new_curr), run_time=0.4)
            self.wait(0.3)

        # Show reversed chain
        self.wait(0.3)
        rev_nodes, rev_arrows, rev_null, rev_null_arr = self._build_chain(
            list(reversed(values)), y_offset=-1.8)
        rev_head = Text("head", font_size=18, color=YELLOW).next_to(rev_nodes[0], UP, buff=0.2)
        self.play(FadeIn(VGroup(*rev_nodes)), Create(VGroup(*rev_arrows)),
                  Write(rev_null), Create(rev_null_arr), Write(rev_head))
        self.play(FadeIn(_result_box(r"\text{Reversed!}", 28).shift(UP * 1.5 + RIGHT * 3)))

    def _find_middle(self, values):
        nodes, arrows, null_lbl, null_arr = self._build_chain(values, y_offset=0)
        head_label = Text("head", font_size=18, color=YELLOW).next_to(nodes[0], UP, buff=0.2)
        self.play(FadeIn(VGroup(*nodes)), Create(VGroup(*arrows)),
                  Write(null_lbl), Create(null_arr), Write(head_label))
        self.wait(0.4)

        slow_lbl = Text("slow", font_size=18, color=GREEN).next_to(nodes[0], DOWN, buff=0.3)
        fast_lbl = Text("fast", font_size=18, color=RED).next_to(nodes[0], DOWN, buff=0.65)
        self.play(Write(slow_lbl), Write(fast_lbl))

        slow, fast = 0, 0
        n = len(values)
        while fast < n - 1 and fast + 1 < n - 1:
            fast = min(fast + 2, n - 1)
            slow = min(slow + 1, n - 1)
            self.play(
                slow_lbl.animate.next_to(nodes[slow], DOWN, buff=0.3),
                fast_lbl.animate.next_to(nodes[fast], DOWN, buff=0.6),
                run_time=0.5,
            )
            self.wait(0.3)

        self.play(nodes[slow][0].animate.set_fill(GREEN, opacity=0.85), run_time=0.3)
        self.play(FadeIn(_result_box(f"\\text{{Middle = }}{values[slow]}", 28)
                         .to_edge(DOWN, buff=1.75)))

    def _merge_sorted(self, v1, v2):
        n1, a1, _, _ = self._build_chain(v1, y_offset=1.2)
        n2, a2, _, _ = self._build_chain(v2, y_offset=-0.2)
        lbl1 = Text("list1", font_size=18, color=BLUE).next_to(n1[0], LEFT, buff=0.3)
        lbl2 = Text("list2", font_size=18, color=GREEN).next_to(n2[0], LEFT, buff=0.3)
        for node in n1:
            node[0].set_fill(BLUE_E, opacity=0.7)
        for node in n2:
            node[0].set_fill(GREEN_E, opacity=0.7)
        self.play(FadeIn(VGroup(*n1, *a1)), FadeIn(VGroup(*n2, *a2)),
                  Write(lbl1), Write(lbl2))
        self.wait(0.5)

        merged = sorted(v1 + v2)
        m_nodes, m_arrows, m_null, m_null_arr = self._build_chain(merged, y_offset=-1.8)
        m_lbl = Text("merged", font_size=18, color=YELLOW).next_to(m_nodes[0], LEFT, buff=0.3)
        self.play(FadeIn(VGroup(*m_nodes, *m_arrows)), Write(m_null), Create(m_null_arr), Write(m_lbl))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 4 — Tree Traversal
# ---------------------------------------------------------------------------

class TreeTraversalScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        values    = p.get("values") or [1, 2, 3, 4, 5, 6, 7]
        algorithm = p.get("algorithm", "bfs")
        cap       = p.get("caption",  "")

        # Normalise: allow null strings
        values = [None if (v is None or v == "null") else v for v in values]

        positions = _tree_positions(values)
        if not positions:
            return

        # Build nodes and edges
        node_mobs = {}
        edge_mobs = []

        for idx, pos in positions.items():
            circle = Circle(radius=0.38, fill_color="#1a2744", fill_opacity=0.90,
                             color=WHITE, stroke_width=2)
            lbl    = Text(str(values[idx]), font_size=22, color=WHITE)
            node_mobs[idx] = VGroup(circle, lbl).move_to(pos)

        for idx in positions:
            for child in [2*idx+1, 2*idx+2]:
                if child in positions:
                    edge_mobs.append(
                        Line(positions[idx], positions[child],
                             color=GRAY, stroke_width=1.8)
                    )

        algo_names = {"bfs": "BFS (Level-Order)", "dfs": "DFS (Pre-Order)",
                      "inorder": "In-Order", "preorder": "Pre-Order",
                      "postorder": "Post-Order", "height": "Tree Height"}
        title = Text(algo_names.get(algorithm, algorithm), font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _legacy_polish(title, "tree_traversal", algorithm,
                                              custom_code=p.get("pseudocode", ""))

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)
        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(Create(VGroup(*edge_mobs)), FadeIn(VGroup(*node_mobs.values())))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.wait(0.3)

        # Get traversal order
        order_fn = {"bfs": _bfs_order, "dfs": _preorder, "inorder": _inorder,
                    "preorder": _preorder, "postorder": _postorder}
        traversal = order_fn.get(algorithm, _bfs_order)(values)

        # Pre-compute layout so the entire sequence fits on screen
        n_visit = len(traversal)
        seq_font = 20 if n_visit <= 8 else (16 if n_visit <= 15 else 13)
        seq_spacing = 0.4 if n_visit <= 8 else (0.32 if n_visit <= 15 else 0.26)

        seq_labels = []
        for step_i, node_idx in enumerate(traversal):
            mob = node_mobs[node_idx]
            self.play(mob[0].animate.set_fill(YELLOW, opacity=0.9), run_time=0.25)
            self.play(mob[0].animate.set_fill(GREEN,  opacity=0.7), run_time=0.2)

            lbl = Text(str(values[node_idx]), font_size=seq_font, color=GREEN)
            if not seq_labels:
                # Center the first label, letting subsequent ones extend right
                # Pre-position based on total expected width
                first_x = -((n_visit - 1) * seq_spacing) / 2
                lbl.move_to(np.array([first_x, -3.2, 0]))
            else:
                lbl.next_to(seq_labels[-1], RIGHT, buff=seq_spacing - 0.15)
            self.play(FadeIn(lbl), run_time=0.2)
            seq_labels.append(lbl)
            self.wait(0.1)

        self.wait(0.8)


# ---------------------------------------------------------------------------
# Scene 5 — Graph Traversal
# ---------------------------------------------------------------------------

class GraphScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        num_nodes  = int(p.get("num_nodes",  6))
        edges      = p.get("edges",       [[0,1],[0,2],[1,3],[2,4],[3,5]])
        start_node = int(p.get("start_node", 0))
        algorithm  = p.get("algorithm",  "bfs")
        directed   = bool(p.get("directed", False))
        cap        = p.get("caption",    "")

        # Build adjacency list — accept [u, v] or [u, v, w] (weight ignored here)
        adj = {i: [] for i in range(num_nodes)}
        for e in edges:
            u, v = e[0], e[1]
            adj[u].append(v)
            if not directed:
                adj[v].append(u)

        # Position nodes in a circle
        radius = 2.8
        positions = []
        for i in range(num_nodes):
            angle = 2 * math.pi * i / num_nodes - math.pi / 2
            positions.append(np.array([radius * math.cos(angle),
                                        radius * math.sin(angle), 0]))

        # Build node mobjects
        node_mobs = []
        for i in range(num_nodes):
            circle = Circle(radius=0.36, fill_color="#1a2744", fill_opacity=0.90,
                             color=WHITE, stroke_width=2)
            lbl = Text(str(i), font_size=22, color=WHITE)
            node_mobs.append(VGroup(circle, lbl).move_to(positions[i]))

        # Build edges — accept [u, v] or [u, v, w] (legacy scene ignores weight)
        edge_mobs = []
        for e in edges:
            u, v = e[0], e[1]
            if directed:
                em = Arrow(positions[u], positions[v], buff=0.38, color=GRAY,
                            stroke_width=2, max_tip_length_to_length_ratio=0.15)
            else:
                em = Line(positions[u], positions[v], color=GRAY, stroke_width=1.8)
            edge_mobs.append(em)

        title = Text(f"Graph {algorithm.upper()} from node {start_node}", font_size=26).to_edge(UP, buff=0.3)
        code_panel, badge_v = _legacy_polish(title, "graph_traversal", algorithm,
                                              custom_code=p.get("pseudocode", ""))

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)
        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(Create(VGroup(*edge_mobs)), FadeIn(VGroup(*node_mobs)))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.wait(0.3)

        steps_fn = _graph_bfs_steps if algorithm == "bfs" else _graph_dfs_steps
        steps = steps_fn(adj, start_node, num_nodes, positions)

        # Structure label (queue or stack)
        struct_label = Text("Queue: []" if algorithm == "bfs" else "Stack: []",
                             font_size=20, color=YELLOW).to_corner(UR, buff=0.4)
        self.play(Write(struct_label))

        action = _action_text(f"Start at node {start_node}")
        self.play(Write(action))

        visit_order = []
        for step in steps:
            n = step["visit"]
            node_mobs[n][0].set_stroke(color=YELLOW, width=3)
            self.play(node_mobs[n][0].animate.set_fill(YELLOW, opacity=0.85), run_time=0.3)
            self.play(node_mobs[n][0].animate.set_fill(GREEN,  opacity=0.7),  run_time=0.2)

            visit_order.append(str(n))
            struct_content = step["queue"] if algorithm == "bfs" else step["stack"]
            label_text = ("Queue" if algorithm == "bfs" else "Stack") + f": {struct_content}"
            new_struct = Text(label_text, font_size=20, color=YELLOW)
            if new_struct.width > 5.5:
                new_struct.scale(5.5 / new_struct.width)
            new_struct.to_corner(UR, buff=0.4)
            self.play(
                Transform(struct_label, new_struct),
                Transform(action, _action_text(step["action"])),
                run_time=0.3,
            )
            self.wait(0.4)

        order_str = " -> ".join(visit_order)
        order_lbl = Text(f"Order: {order_str}", font_size=22, color=WHITE)
        if order_lbl.width > 13.5:
            order_lbl.scale(13.5 / order_lbl.width)
        order_box = SurroundingRectangle(order_lbl, color=WHITE, fill_color=BLACK,
                                          fill_opacity=0.75, buff=0.15, corner_radius=0.1)
        self.play(FadeIn(VGroup(order_box, order_lbl).to_edge(DOWN, buff=1.75)))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 6 — 1D Dynamic Programming
# ---------------------------------------------------------------------------

class DPArrayScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        algorithm = p.get("algorithm") or "fibonacci"
        # Agents occasionally pass `n: null` / `amount: null` explicitly
        # (instead of omitting the key), which makes p.get(...) return None
        # and `int(None)` raise TypeError. Coerce defensively.
        n         = int(p.get("n")      or 8)
        coins     = p.get("coins") or [1, 3, 4]
        amount    = int(p.get("amount") or 6)
        cap       = p.get("caption")    or ""

        if algorithm == "fibonacci":
            steps, dp = _dp_fibonacci_steps(n)
            title_str  = f"Fibonacci — dp[{n}] = ?"
        elif algorithm == "climbing_stairs":
            steps, dp = _dp_climbing_stairs_steps(n)
            title_str  = f"Climbing Stairs — n={n} ways"
        elif algorithm == "house_robber":
            steps, dp, houses = _dp_house_robber_steps(n)
            title_str  = f"House Robber — max loot"
        else:
            title_str = "DP"
            steps, dp = _dp_fibonacci_steps(n)

        n_cells = len(steps)
        cell_w = min(0.85, 9.5 / n_cells)

        cells = _make_cells(["?"] * n_cells, cell_size=cell_w)
        row   = VGroup(*cells).arrange(RIGHT, buff=0.06).center().shift(UP * 0.5)

        idx_labels = VGroup(*[
            Text(str(i), font_size=14, color=GRAY).next_to(cells[i], DOWN, buff=0.06)
            for i in range(n_cells)
        ])

        title = Text(title_str, font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _legacy_polish(title, "dp_array", algorithm,
                                              custom_code=p.get("pseudocode", ""))

        if algorithm == "house_robber":
            house_labels = VGroup(*[
                Text(str(houses[i]), font_size=14, color=YELLOW).next_to(cells[i], UP, buff=0.08)
                for i in range(n_cells)
            ])
            self.play(Write(Text("house values:", font_size=18, color=YELLOW).to_corner(UL, buff=0.4)))
            self.play(Write(house_labels))

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)
        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(row), Write(idx_labels))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.wait(0.3)

        action = Text("Filling DP table...", font_size=22).to_edge(DOWN, buff=1.4)
        self.play(Write(action))

        for step in steps:
            idx, val = step["idx"], step["value"]
            # Update cell
            new_cell_text = Text(str(val), font_size=22, color=WHITE)
            new_cell_text.move_to(cells[idx][1].get_center())

            # Draw dependency arrows
            dep_arcs = []
            for dep in step.get("deps", []):
                arc = CurvedArrow(
                    cells[dep].get_top() + UP * 0.05,
                    cells[idx].get_top() + UP * 0.05,
                    color=TEAL, angle=-PI / 3, stroke_width=2,
                )
                dep_arcs.append(arc)

            if dep_arcs:
                self.play(*[Create(a) for a in dep_arcs], run_time=0.3)

            self.play(
                cells[idx][0].animate.set_fill(YELLOW, opacity=0.8),
                Transform(cells[idx][1], new_cell_text),
                Transform(action, Text(step["formula"], font_size=22).to_edge(DOWN, buff=1.4)),
                run_time=0.45,
            )
            self.play(cells[idx][0].animate.set_fill(GREEN, opacity=0.65), run_time=0.2)
            self.wait(0.2)

        self.play(FadeIn(_result_box(f"\\text{{Answer: }}{dp[-1]}", 30).to_edge(DOWN, buff=1.75)))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene 7 — Stack / Queue
# ---------------------------------------------------------------------------

class StackQueueScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = _load_params()
        operations = p.get("operations") or ["push 3", "push 1", "push 4", "pop", "push 1", "push 5"]
        structure  = p.get("structure",  "stack")
        cap        = p.get("caption",   "")

        title = Text(f"{structure.upper()} Operations", font_size=30).to_edge(UP, buff=0.3)
        code_panel, badge_v = _legacy_polish(title, "stack_queue", structure,
                                              custom_code=p.get("pseudocode", ""))

        if cap:
            _show_title_card(self, cap)
            self.play(FadeIn(_caption(cap)), run_time=0.3)
        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        if structure == "stack":
            self._animate_stack(operations)
        else:
            self._animate_queue(operations)
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)

    def _animate_stack(self, operations):
        CELL_H, CELL_W = 0.62, 2.4
        MAX_VISIBLE = 7
        container = Rectangle(width=CELL_W + 0.2, height=MAX_VISIBLE * CELL_H + 0.2,
                               color=WHITE, stroke_width=2, fill_opacity=0)
        container.shift(LEFT * 2)
        self.play(Create(container))

        items = []   # list of VGroup(rect, label)
        base_y = container.get_bottom()[1] + CELL_H / 2 + 0.1

        op_label = Text("", font_size=24, color=BLUE).to_edge(RIGHT, buff=0.5).shift(UP * 0.5)

        for op in operations:
            op = op.strip()
            new_op_label = Text(f"→ {op}", font_size=24, color=BLUE).to_edge(RIGHT, buff=0.5).shift(UP * 0.5)
            self.play(Transform(op_label, new_op_label), run_time=0.3)

            if op.lower().startswith("push"):
                val = op.split()[-1]
                rect = Rectangle(width=CELL_W - 0.06, height=CELL_H - 0.05,
                                  fill_color=BLUE_D, fill_opacity=0.75, stroke_color=WHITE, stroke_width=1.5)
                lbl  = Text(str(val), font_size=22, color=WHITE)
                item = VGroup(rect, lbl)
                target_y = base_y + len(items) * CELL_H
                item.move_to(np.array([container.get_center()[0], target_y + 2.5, 0]))
                self.add(item)
                self.play(item.animate.move_to(
                    np.array([container.get_center()[0], target_y, 0])), run_time=0.45)
                items.append(item)

            elif op.lower() == "pop" and items:
                top = items[-1]
                self.play(top.animate.shift(UP * 2.5 + RIGHT * 1.5), run_time=0.4)
                self.play(FadeOut(top), run_time=0.2)
                items.pop()

            size_lbl = Text(f"size = {len(items)}", font_size=20, color=GRAY).to_corner(DR, buff=0.5)
            if not hasattr(self, '_size_mob'):
                self._size_mob = size_lbl
                self.add(size_lbl)
            else:
                self.play(Transform(self._size_mob, size_lbl), run_time=0.2)

            self.wait(0.3)

    def _animate_queue(self, operations):
        CELL_H, CELL_W = 0.7, 0.75
        MAX_VISIBLE = 8
        container = Rectangle(width=MAX_VISIBLE * CELL_W + 0.2, height=CELL_H + 0.2,
                               color=WHITE, stroke_width=2, fill_opacity=0)
        container.shift(DOWN * 0.3)
        self.play(Create(container))

        enqueue_lbl = Text("← enqueue", font_size=18, color=GREEN).next_to(container, RIGHT, buff=0.2)
        dequeue_lbl = Text("dequeue →", font_size=18, color=RED).next_to(container, LEFT, buff=0.2)
        self.play(Write(enqueue_lbl), Write(dequeue_lbl))

        items = []
        base_x = container.get_left()[0] + CELL_W / 2 + 0.1
        center_y = container.get_center()[1]

        op_label = Text("", font_size=24, color=BLUE).to_edge(UP, buff=0.6)

        for op in operations:
            op = op.strip()
            new_op_label = Text(f"→ {op}", font_size=24, color=BLUE).to_edge(UP, buff=0.6)
            self.play(Transform(op_label, new_op_label), run_time=0.3)

            if op.lower().startswith("push") or op.lower().startswith("enqueue"):
                val = op.split()[-1]
                rect = Rectangle(width=CELL_W - 0.06, height=CELL_H - 0.06,
                                  fill_color=GREEN_D, fill_opacity=0.75, stroke_color=WHITE, stroke_width=1.5)
                lbl  = Text(str(val), font_size=20, color=WHITE)
                item = VGroup(rect, lbl)
                slot = base_x + len(items) * CELL_W
                item.move_to(np.array([container.get_right()[0] + 1.5, center_y, 0]))
                self.add(item)
                self.play(item.animate.move_to(np.array([slot, center_y, 0])), run_time=0.45)
                items.append(item)

            elif (op.lower() in ("pop", "dequeue")) and items:
                front = items[0]
                self.play(front.animate.shift(LEFT * 2.5), run_time=0.4)
                self.play(FadeOut(front), run_time=0.2)
                items.pop(0)
                # Slide remaining items left
                if items:
                    self.play(*[
                        item.animate.shift(LEFT * CELL_W) for item in items
                    ], run_time=0.35)

            self.wait(0.3)
