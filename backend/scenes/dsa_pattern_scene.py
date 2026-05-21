"""
Granular DSA pattern scenes that compose primitives.

Each scene:
  - runs the actual algorithm in pure Python (always correct)
  - generates a list of step dicts
  - composes primitives from dsa_primitives.py to animate those steps

No visual code is duplicated across scenes — everything reusable lives in
dsa_primitives.
"""
from collections import deque

import numpy as np
from manim import *

from scenes.dsa_primitives import (
    DEFAULT_CELL, HILITE, KEEP, REJECT, PTR_COLORS, PANEL_BG,
    ArrayStrip, Pointer, HighlightZone, HashMapPanel, StatePanel,
    ComparisonMarker, StackWidget, DependencyArc,
    GridPanel, GridArrow, BinaryTreePanel, RecursionTree, IntervalBars,
    DoublyLinkedListPanel, GraphPanel, CodePanel,
    ComplexityBadge, InvariantOverlay, BruteForceComparison, BinaryRegister,
    load_params, show_title_card, caption_strip, result_box, action_text,
)


# ---------------------------------------------------------------------------
# Pattern catalog: pseudocode + complexity per (scene_key, algorithm) pair.
# Used by the polish pass to add CodePanel + ComplexityBadge to existing
# pattern scenes without restructuring their step loops.
# ---------------------------------------------------------------------------

_PATTERN_CATALOG = {
    # two_pointers_opposite
    ("two_pointers_opposite", "palindrome"): (
        "l, r = 0, len(s) - 1\nwhile l < r:\n    if s[l] != s[r]: return False\n    l, r = l + 1, r - 1\nreturn True",
        "O(n)", "O(1)"),
    ("two_pointers_opposite", "two_sum_sorted"): (
        "l, r = 0, len(a) - 1\nwhile l < r:\n    s = a[l] + a[r]\n    if s == target: return [l, r]\n    elif s < target: l += 1\n    else: r -= 1",
        "O(n)", "O(1)"),
    ("two_pointers_opposite", "container_water"): (
        "l, r = 0, len(h) - 1\nbest = 0\nwhile l < r:\n    area = (r - l) * min(h[l], h[r])\n    best = max(best, area)\n    if h[l] < h[r]: l += 1\n    else: r -= 1",
        "O(n)", "O(1)"),
    ("two_pointers_opposite", "reverse_array"): (
        "l, r = 0, len(a) - 1\nwhile l < r:\n    a[l], a[r] = a[r], a[l]\n    l, r = l + 1, r - 1",
        "O(n)", "O(1)"),

    # hashmap_iteration
    ("hashmap_iteration", "two_sum_hashmap"): (
        "seen = {}\nfor i, v in enumerate(a):\n    if target - v in seen:\n        return [seen[target - v], i]\n    seen[v] = i",
        "O(n)", "O(n)"),
    ("hashmap_iteration", "frequency_count"): (
        "freq = {}\nfor v in a:\n    freq[v] = freq.get(v, 0) + 1\nreturn freq",
        "O(n)", "O(k)"),
    ("hashmap_iteration", "anagram_check"): (
        "if len(s) != len(t): return False\nfreq = {}\nfor c in s: freq[c] = freq.get(c, 0) + 1\nfor c in t: freq[c] = freq.get(c, 0) - 1\nreturn all(v == 0 for v in freq.values())",
        "O(n)", "O(k)"),

    # sliding_window_variable
    ("sliding_window_variable", "longest_no_repeat"): (
        "seen = {}\nl = best = 0\nfor r, c in enumerate(s):\n    if c in seen and seen[c] >= l:\n        l = seen[c] + 1\n    seen[c] = r\n    best = max(best, r - l + 1)",
        "O(n)", "O(k)"),
    ("sliding_window_variable", "longest_at_most_k_distinct"): (
        "freq = {}\nl = best = 0\nfor r, c in enumerate(s):\n    freq[c] = freq.get(c, 0) + 1\n    while len(freq) > k:\n        freq[s[l]] -= 1\n        if freq[s[l]] == 0: del freq[s[l]]\n        l += 1\n    best = max(best, r - l + 1)",
        "O(n)", "O(k)"),

    # binary_search_index
    ("binary_search_index", "find_target"): (
        "l, r = 0, len(a) - 1\nwhile l <= r:\n    m = (l + r) // 2\n    if a[m] == target: return m\n    elif a[m] < target: l = m + 1\n    else: r = m - 1\nreturn -1",
        "O(log n)", "O(1)"),
    ("binary_search_index", "first_occurrence"): (
        "l, r = 0, len(a) - 1\nans = -1\nwhile l <= r:\n    m = (l + r) // 2\n    if a[m] >= target:\n        if a[m] == target: ans = m\n        r = m - 1\n    else: l = m + 1\nreturn ans",
        "O(log n)", "O(1)"),

    # monotonic_stack
    ("monotonic_stack", "next_greater"): (
        "stack = []\nresult = [-1] * n\nfor i in range(n):\n    while stack and a[stack[-1]] < a[i]:\n        result[stack.pop()] = a[i]\n    stack.append(i)",
        "O(n)", "O(n)"),
    ("monotonic_stack", "daily_temperatures"): (
        "stack = []\ndays = [0] * n\nfor i in range(n):\n    while stack and t[stack[-1]] < t[i]:\n        j = stack.pop()\n        days[j] = i - j\n    stack.append(i)",
        "O(n)", "O(n)"),

    # prefix_sum
    ("prefix_sum", "build_prefix"): (
        "prefix = [0] * (n + 1)\nfor i in range(n):\n    prefix[i + 1] = prefix[i] + a[i]",
        "O(n)", "O(n)"),
    ("prefix_sum", "range_sum_query"): (
        "# After preprocessing prefix[]:\nrange_sum(l, r) = prefix[r + 1] - prefix[l]",
        "O(1) / query", "O(n) prep"),

    # two_pointers_same_dir
    ("two_pointers_same_dir", "remove_duplicates"): (
        "slow = 0\nfor fast in range(1, len(a)):\n    if a[fast] != a[slow]:\n        slow += 1\n        a[slow] = a[fast]\nreturn slow + 1",
        "O(n)", "O(1)"),
    ("two_pointers_same_dir", "move_zeros"): (
        "slow = 0\nfor fast in range(len(a)):\n    if a[fast] != 0:\n        a[slow], a[fast] = a[fast], a[slow]\n        slow += 1",
        "O(n)", "O(1)"),

    # binary_search_answer
    ("binary_search_answer", "default"): (
        "lo, hi = min_val, max_val\nwhile lo < hi:\n    mid = (lo + hi) // 2\n    if predicate(mid):\n        hi = mid\n    else:\n        lo = mid + 1\nreturn lo",
        "O(log range)", "O(1)"),

    # interval_merging
    ("interval_merging", "default"): (
        "intervals.sort(key=lambda x: x[0])\nmerged = []\nfor s, e in intervals:\n    if merged and merged[-1][1] >= s:\n        merged[-1][1] = max(merged[-1][1], e)\n    else:\n        merged.append([s, e])",
        "O(n log n)", "O(n)"),

    # backtracking_subsets
    ("backtracking_subsets", "subsets"): (
        "def dfs(i, path):\n    if i == len(a):\n        out.append(path[:])\n        return\n    dfs(i + 1, path)            # exclude\n    dfs(i + 1, path + [a[i]])  # include",
        "O(2^n)", "O(n)"),
    ("backtracking_subsets", "permutations"): (
        "def dfs(used, path):\n    if len(path) == len(a):\n        out.append(path[:]); return\n    for i in range(len(a)):\n        if not used[i]:\n            used[i] = True\n            dfs(used, path + [a[i]])\n            used[i] = False",
        "O(n!)", "O(n)"),

    # lru_cache
    ("lru_cache", "default"): (
        "def get(k):\n    if k in cache: move_to_head(k); return cache[k]\n    return -1\ndef put(k, v):\n    if k in cache: update + move_to_head\n    elif size == capacity: evict_tail()\n    add_to_head(k, v)",
        "O(1) per op", "O(capacity)"),

    # grid_traversal
    ("grid_traversal", "bfs"): (
        "queue = [(start, 0)]\nvisited[start] = True\nwhile queue:\n    (r, c), d = queue.popleft()\n    if (r, c) == target: return d\n    for nr, nc in neighbors(r, c):\n        if grid[nr][nc] == 0 and not visited[nr][nc]:\n            visited[nr][nc] = True\n            queue.append(((nr, nc), d + 1))",
        "O(rc)", "O(rc)"),
    ("grid_traversal", "dfs"): (
        "def dfs(r, c):\n    if (r, c) == target: return True\n    visited[r][c] = True\n    for nr, nc in neighbors(r, c):\n        if grid[nr][nc] == 0 and not visited[nr][nc]:\n            if dfs(nr, nc): return True\n    return False",
        "O(rc)", "O(rc)"),

    # heap_ops
    ("heap_ops", "default"): (
        "def push(v):\n    heap.append(v); sift_up(len(heap) - 1)\ndef pop():\n    swap(0, -1); top = heap.pop()\n    sift_down(0)\n    return top",
        "O(log n) per op", "O(n)"),

    # dp_2d
    ("dp_2d", "lcs"): (
        "for i in 1..m:\n    for j in 1..n:\n        if s1[i-1] == s2[j-1]:\n            dp[i][j] = dp[i-1][j-1] + 1\n        else:\n            dp[i][j] = max(dp[i-1][j], dp[i][j-1])",
        "O(mn)", "O(mn)"),
    ("dp_2d", "edit_distance"): (
        "for i in 0..m:\n    for j in 0..n:\n        if i == 0: dp[i][j] = j\n        elif j == 0: dp[i][j] = i\n        elif s1[i-1] == s2[j-1]:\n            dp[i][j] = dp[i-1][j-1]\n        else:\n            dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])",
        "O(mn)", "O(mn)"),
    ("dp_2d", "unique_paths"): (
        "for i in 0..m:\n    for j in 0..n:\n        if i == 0 or j == 0: dp[i][j] = 1\n        else: dp[i][j] = dp[i-1][j] + dp[i][j-1]",
        "O(mn)", "O(mn)"),

    # trie_ops
    ("trie_ops", "default"): (
        "def insert(word):\n    node = root\n    for c in word:\n        if c not in node.children:\n            node.children[c] = TrieNode()\n        node = node.children[c]\n    node.is_end = True",
        "O(L)", "O(N · L)"),

    # union_find
    ("union_find", "default"): (
        "def find(x):\n    while parent[x] != x:\n        parent[x] = parent[parent[x]]  # path compression\n        x = parent[x]\n    return x\ndef union(a, b):\n    ra, rb = find(a), find(b)\n    if ra != rb: parent[ra] = rb",
        "~O(α(n)) per op", "O(n)"),

    # dijkstra
    ("dijkstra", "default"): (
        "dist[source] = 0\npq = [(0, source)]\nwhile pq:\n    d, u = heappop(pq)\n    if d > dist[u]: continue\n    for v, w in adj[u]:\n        if dist[u] + w < dist[v]:\n            dist[v] = dist[u] + w\n            heappush(pq, (dist[v], v))",
        "O((V+E) log V)", "O(V)"),

    # segment_tree
    ("segment_tree", "default"): (
        "def build(node, l, r):\n    if l == r: tree[node] = a[l]; return\n    m = (l + r) // 2\n    build(2*node, l, m)\n    build(2*node + 1, m + 1, r)\n    tree[node] = tree[2*node] + tree[2*node + 1]",
        "O(n) build, O(log n) query", "O(n)"),
}


def _polish(scene, title, algorithm: str, scene_key: str, custom_code: str = ""):
    """Build a CodePanel + ComplexityBadge for an existing pattern scene.

    If `custom_code` is provided (typically from /api/parse-leetcode using
    the user's literal variable names), it overrides the catalog template
    and the panel is flagged `is_custom`. Synced line highlighting is
    auto-disabled for custom code because line numbers may not match the
    catalog's _STEP_LINE_MAPS keyed by (scene_key, algorithm).

    Returns (code_panel, badge_vgroup_or_None). Caller FadeIns both early
    in construct() and optionally calls code_panel.anim_dim_all() to set
    the initial dim state.
    """
    entry = _PATTERN_CATALOG.get((scene_key, algorithm))
    pseudo = (custom_code or "").strip()
    is_custom = bool(pseudo)

    if not pseudo:
        if entry is None:
            return None, None
        pseudo = entry[0]

    if entry is not None:
        t_complex, s_complex = entry[1], entry[2]
    else:
        t_complex, s_complex = "—", "—"

    code_panel = CodePanel(pseudo, anchor=UL, font_size=14, max_width=4.0)
    code_panel.is_custom = is_custom
    badge = ComplexityBadge(time=t_complex, space=s_complex, font_size=14)
    # Long titles + a right-adjacent badge can collide with UR-anchored
    # StatePanel/HashMapPanel. If the title is wide, drop the badge below
    # it instead of beside; otherwise keep it inline.
    if title.width > 6.0:
        badge.vgroup.next_to(title, DOWN, buff=0.15)
    else:
        badge.vgroup.next_to(title, RIGHT, buff=0.3)
    return code_panel, badge.vgroup


# ---------------------------------------------------------------------------
# Step → pseudocode line mapping per (scene_key, algorithm).
# Drives synced line-highlighting: as the algorithm steps through, the
# matching pseudocode line lights up yellow in the CodePanel.
# ---------------------------------------------------------------------------

_STEP_LINE_MAPS = {
    # two_pointers_opposite
    ("two_pointers_opposite", "palindrome"):       {"match": 2, "fail": 2},
    ("two_pointers_opposite", "two_sum_sorted"):   {"match": 3, "advance_l": 4, "advance_r": 5, "fail": 1},
    ("two_pointers_opposite", "container_water"):  {"compute": 3},
    ("two_pointers_opposite", "reverse_array"):    {"swap": 2},

    # hashmap_iteration
    ("hashmap_iteration", "two_sum_hashmap"): {"match": 3, "store": 4},
    ("hashmap_iteration", "frequency_count"): {"increment": 2},
    ("hashmap_iteration", "anagram_check"):   {"increment": 2},

    # sliding_window_variable
    ("sliding_window_variable", "longest_no_repeat"): {
        "expand": 5, "shrink": 4, "best": 6,
    },
    ("sliding_window_variable", "longest_at_most_k_distinct"): {
        "expand": 3, "shrink": 7, "best": 8,
    },

    # binary_search_index
    ("binary_search_index", "find_target"): {
        "compare": 3, "match": 3, "go_right": 4, "go_left": 5, "not_found": 6,
    },
    ("binary_search_index", "first_occurrence"): {
        "compare": 4, "match": 5, "go_left": 6, "go_right": 7,
    },

    # monotonic_stack
    ("monotonic_stack", "next_greater"): {"pop": 4, "push": 5},
    ("monotonic_stack", "daily_temperatures"): {"pop": 5, "push": 6},

    # prefix_sum
    ("prefix_sum", "build_prefix"):    {"build": 2},
    ("prefix_sum", "range_sum_query"): {"query": 1, "build": 1},

    # two_pointers_same_dir
    ("two_pointers_same_dir", "remove_duplicates"): {
        "compare": 2, "write": 4, "skip": 2, "advance_fast": 1,
    },
    ("two_pointers_same_dir", "move_zeros"): {
        "compare": 2, "swap": 3, "skip": 2, "advance_fast": 1,
    },

    # interval_merging
    ("interval_merging", "default"): {"sort": 0, "emit": 6, "merge": 4},

    # backtracking_subsets
    ("backtracking_subsets", "subsets"):      {"enter": 4, "exit": 3, "leaf": 2},
    ("backtracking_subsets", "permutations"): {"enter": 6, "exit": 7, "leaf": 2},

    # lru_cache
    ("lru_cache", "default"): {"hit": 1, "miss": 2, "update": 4, "insert": 6},

    # grid_traversal
    ("grid_traversal", "bfs"): {"start": 0, "visit": 3, "enqueue": 8, "path": 4, "fail": 4},
    ("grid_traversal", "dfs"): {"start": 0, "visit": 2, "enqueue": 5, "path": 1, "fail": 6},

    # heap_ops
    ("heap_ops", "default"): {
        "push": 1, "pop_top": 3, "replace_root": 4, "swap": 4, "empty": 5,
    },

    # trie_ops
    ("trie_ops", "default"): {
        "walk": 5, "insert_char": 4, "mark_end": 6,
        "miss": 3, "final_hit": 6, "final_miss": 6,
    },

    # union_find
    ("union_find", "default"): {"noop": 7, "linked": 7, "find": 4},

    # dijkstra
    ("dijkstra", "default"): {"settle": 3, "relax": 7},

    # segment_tree (only build pseudocode shown; query falls back to line 5)
    ("segment_tree", "default"): {"build": 5, "query": 5},

    # binary_search_answer — kinds synthesized from step["predicate"]
    ("binary_search_answer", "default"): {"true": 4, "false": 6},

    # dp_2d — kinds synthesized from step["action"] keywords
    ("dp_2d", "lcs"):           {"match": 3, "recur": 5},
    ("dp_2d", "edit_distance"): {"boundary": 3, "match": 5, "recur": 7},
    ("dp_2d", "unique_paths"):  {"boundary": 1, "recur": 4},
}


def _hl_line(code_panel, scene_key: str, algorithm: str, step_kind: str,
             step_lines_override: dict = None):
    """Returns an anim_highlight Animation for the line corresponding to
    step_kind, or None if there's no panel or mapping.

    Lookup order:
      1. `step_lines_override` (passed by scene from params, supplied by
         /api/parse-leetcode for custom pseudocode) — checked FIRST so
         bespoke code gets correct highlighting
      2. `_STEP_LINE_MAPS` (catalog mapping for catalog code) — fallback

    If the panel is `is_custom` AND no override mapping is supplied,
    return None — the catalog mapping won't match the custom code's
    line numbers, so it's safer to leave the panel dim than highlight
    the wrong line.
    """
    if code_panel is None:
        return None

    is_custom = getattr(code_panel, "is_custom", False)

    if step_lines_override:
        line = step_lines_override.get(step_kind)
        if line is not None:
            try:
                return code_panel.anim_highlight(int(line))
            except (TypeError, ValueError):
                pass  # fall through

    if is_custom:
        # Custom code with no usable override → leave it dim
        return None

    table = _STEP_LINE_MAPS.get((scene_key, algorithm))
    if not table:
        return None
    line = table.get(step_kind)
    if line is None:
        return None
    return code_panel.anim_highlight(line)


# ===========================================================================
#  ALGORITHM STEP GENERATORS (pure Python, no Manim imports inside)
# ===========================================================================

# ---------------------------------------------------------------------------
# Two pointers — opposite ends
# ---------------------------------------------------------------------------

def _two_pointers_opposite_steps(arr: list, algorithm: str, target=None) -> tuple:
    """
    Returns (steps: list, result: any).
    Each step: {"L": int, "R": int, "action": str, "match": bool, "kind": str}
    """
    steps = []
    L, R = 0, len(arr) - 1

    if algorithm == "palindrome":
        while L < R:
            if str(arr[L]) == str(arr[R]):
                steps.append({"L": L, "R": R, "match": True,
                               "action": f"'{arr[L]}' == '{arr[R]}'  ✓",
                               "symbol": "==", "kind": "match"})
            else:
                steps.append({"L": L, "R": R, "match": False,
                               "action": f"'{arr[L]}' != '{arr[R]}'  ✗  not a palindrome",
                               "symbol": "!=", "kind": "fail"})
                return steps, False
            L += 1
            R -= 1
        return steps, True

    elif algorithm == "two_sum_sorted":
        tgt = int(target) if target is not None else 0
        while L < R:
            s = arr[L] + arr[R]
            if s == tgt:
                steps.append({"L": L, "R": R, "sum": s, "match": True,
                               "action": f"{arr[L]} + {arr[R]} = {s}  =  target ✓",
                               "symbol": "==", "kind": "match"})
                return steps, (L, R)
            elif s < tgt:
                steps.append({"L": L, "R": R, "sum": s, "match": False,
                               "action": f"{arr[L]} + {arr[R]} = {s}  <  {tgt}, move L right",
                               "symbol": "<", "kind": "advance_l"})
                L += 1
            else:
                steps.append({"L": L, "R": R, "sum": s, "match": False,
                               "action": f"{arr[L]} + {arr[R]} = {s}  >  {tgt}, move R left",
                               "symbol": ">", "kind": "advance_r"})
                R -= 1
        steps.append({"L": L, "R": R, "match": False, "action": "no pair found",
                       "symbol": "!=", "kind": "fail"})
        return steps, None

    elif algorithm == "container_water":
        best = 0
        best_pair = (0, 0)
        while L < R:
            h = min(arr[L], arr[R])
            area = h * (R - L)
            if area > best:
                best = area
                best_pair = (L, R)
            steps.append({"L": L, "R": R, "match": False,
                           "area": area,
                           "action": f"width={R - L}, h={h}, area={area} (best={best})",
                           "symbol": ">", "kind": "compute"})
            if arr[L] < arr[R]:
                L += 1
            else:
                R -= 1
        return steps, best

    elif algorithm == "reverse_array":
        result = list(arr)
        while L < R:
            result[L], result[R] = result[R], result[L]
            steps.append({"L": L, "R": R, "match": True,
                           "action": f"swap {arr[L]} ↔ {arr[R]}",
                           "symbol": "<->", "kind": "swap"})
            L += 1
            R -= 1
        return steps, result

    return steps, None


# ---------------------------------------------------------------------------
# Hashmap iteration
# ---------------------------------------------------------------------------

def _hashmap_iteration_steps(arr: list, algorithm: str, target=None) -> tuple:
    """
    Each step: {"i": int, "action": str, "hashmap_diff": dict, "kind": str, ...}
    hashmap_diff is the operation: {"set": (k, v)} | {"delete": k} | {"flash": k} | {"none": True}
    """
    steps = []

    if algorithm == "frequency_count":
        counts = {}
        for i, v in enumerate(arr):
            new_count = counts.get(str(v), 0) + 1
            counts[str(v)] = new_count
            steps.append({
                "i": i,
                "action": f"see '{v}'  →  count[{v}] = {new_count}",
                "hashmap_diff": {"set": (str(v), new_count)},
                "kind": "increment",
            })
        return steps, counts

    elif algorithm == "two_sum_hashmap":
        tgt = int(target) if target is not None else 0
        seen = {}
        for i, v in enumerate(arr):
            need = tgt - v
            if str(need) in seen:
                steps.append({
                    "i": i,
                    "action": f"see {v}, need {need}  ✓ found at index {seen[str(need)]}",
                    "hashmap_diff": {"flash": str(need)},
                    "kind": "match",
                })
                return steps, (seen[str(need)], i)
            seen[str(v)] = i
            steps.append({
                "i": i,
                "action": f"see {v}, looking for {need}, store {v} → {i}",
                "hashmap_diff": {"set": (str(v), i)},
                "kind": "store",
            })
        return steps, None

    elif algorithm == "anagram_check":
        # Phase 1: count first string. Phase 2: decrement using second string.
        # For visual simplicity, treat arr as a single string and compute self-frequency
        counts = {}
        for i, v in enumerate(arr):
            counts[str(v)] = counts.get(str(v), 0) + 1
            steps.append({
                "i": i,
                "action": f"count '{v}': {counts[str(v)]}",
                "hashmap_diff": {"set": (str(v), counts[str(v)])},
                "kind": "increment",
            })
        return steps, counts

    return steps, None


# ===========================================================================
#  PATTERN SCENES
# ===========================================================================

# ---------------------------------------------------------------------------
# Scene: two_pointers_opposite
# ---------------------------------------------------------------------------

class TwoPointersOppositeScene(Scene):
    """
    L starts left, R starts right, converge inward.
    Algorithms: palindrome, two_sum_sorted, container_water, reverse_array.
    """

    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        arr       = p.get("array") or ["r", "a", "c", "e", "c", "a", "r"]
        algorithm = p.get("algorithm", "palindrome")
        target    = p.get("target")
        cap       = p.get("caption", "")

        # Title
        titles = {
            "palindrome":      "Two Pointers — Palindrome Check",
            "two_sum_sorted":  f"Two Pointers — Two Sum (target={target})",
            "container_water": "Two Pointers — Container with Most Water",
            "reverse_array":   "Two Pointers — Reverse Array",
        }
        title = Text(titles.get(algorithm, algorithm), font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, algorithm, "two_pointers_opposite",
                                      custom_code=p.get("pseudocode", ""))

        # Strip
        strip = ArrayStrip(arr, position=UP * 0.6)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(strip.vgroup), Write(strip.indices))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.wait(0.3)

        # Pointers
        L_ptr = Pointer("L", color=PTR_COLORS["L"]).place_below(strip, 0)
        R_ptr = Pointer("R", color=PTR_COLORS["R"]).place_below(strip, len(arr) - 1)
        self.play(FadeIn(L_ptr.vgroup), FadeIn(R_ptr.vgroup))

        # Run the algorithm
        steps, result = _two_pointers_opposite_steps(arr, algorithm, target)

        # Action text
        act = action_text(steps[0]["action"]) if steps else action_text("...")
        self.play(FadeIn(act))

        for step in steps:
            L, R = step["L"], step["R"]
            kind = step.get("kind", "compute")

            # Highlight the two cells being examined + sync code line
            highlight_color = HILITE
            extra = []
            hl = _hl_line(code_panel, "two_pointers_opposite", algorithm, kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(
                strip.anim_set_fill(L, highlight_color, 0.75),
                strip.anim_set_fill(R, highlight_color, 0.75),
                *extra,
                run_time=0.3,
            )

            # Show comparison marker
            sym = step.get("symbol", "?")
            marker = ComparisonMarker.between(strip, L, R, symbol=sym,
                                                color=KEEP if step.get("match") else
                                                      (REJECT if kind == "fail" else HILITE))
            self.play(FadeIn(marker.vgroup), run_time=0.3)

            # Update action
            new_act = action_text(step["action"])
            self.play(Transform(act, new_act), run_time=0.3)

            # Brief pause to absorb
            self.wait(0.4)

            # Fade marker out, settle cells
            if kind == "match":
                self.play(
                    strip.anim_set_fill(L, KEEP, 0.7),
                    strip.anim_set_fill(R, KEEP, 0.7),
                    FadeOut(marker.vgroup),
                    run_time=0.25,
                )
            elif kind == "fail":
                self.play(
                    strip.anim_set_fill(L, REJECT, 0.8),
                    strip.anim_set_fill(R, REJECT, 0.8),
                    FadeOut(marker.vgroup),
                    run_time=0.3,
                )
                break  # palindrome failure stops here
            elif kind in ("advance_l", "advance_r", "compute", "swap"):
                self.play(
                    strip.anim_set_fill(L, DEFAULT_CELL, 0.7),
                    strip.anim_set_fill(R, DEFAULT_CELL, 0.7),
                    FadeOut(marker.vgroup),
                    run_time=0.2,
                )

            # Move pointers to next positions if there's a next step
            idx = steps.index(step)
            if idx + 1 < len(steps):
                next_step = steps[idx + 1]
                self.play(
                    L_ptr.anim_move_to(strip, next_step["L"]),
                    R_ptr.anim_move_to(strip, next_step["R"]),
                    run_time=0.4,
                    rate_func=smooth,
                )

        # Final "click" — if pointers met successfully, indicate both
        if algorithm == "palindrome" and result is True:
            mid = len(arr) // 2
            self.play(strip.flash(mid - 1 if len(arr) % 2 == 0 else mid, color=KEEP))

        # Result
        verdict_map = {
            "palindrome":      ("Palindrome!", KEEP) if result else ("Not a Palindrome", REJECT),
            "two_sum_sorted":  (f"Found pair: indices {result}", KEEP) if result else ("No pair found", REJECT),
            "container_water": (f"Max area = {result}", KEEP),
            "reverse_array":   (f"Reversed: {result}", KEEP),
        }
        verdict, vcolor = verdict_map.get(algorithm, ("Done", KEEP))
        rb = result_box(verdict, font_size=28).to_edge(DOWN, buff=1.75)
        for sub in rb:
            if hasattr(sub, "set_color"):
                pass
        rb[1].set_color(vcolor)
        self.play(FadeIn(rb), run_time=0.4)
        self.play(Indicate(rb, scale_factor=1.05))

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# Scene: hashmap_iteration
# ---------------------------------------------------------------------------

class HashMapIterationScene(Scene):
    """
    Iterate left to right, updating a hashmap panel.
    Algorithms: frequency_count, two_sum_hashmap, anagram_check.
    """

    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        arr       = p.get("array") or [2, 7, 11, 15]
        algorithm = p.get("algorithm", "frequency_count")
        target    = p.get("target")
        cap       = p.get("caption", "")

        titles = {
            "frequency_count":  "HashMap — Frequency Count",
            "two_sum_hashmap":  f"HashMap — Two Sum (target={target})",
            "anagram_check":    "HashMap — Anagram Frequencies",
        }
        title = Text(titles.get(algorithm, algorithm), font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, algorithm, "hashmap_iteration",
                                      custom_code=p.get("pseudocode", ""))

        # Place array left-of-center to leave room for hashmap on the right
        strip = ArrayStrip(arr, position=LEFT * 2.5 + UP * 0.4)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(strip.vgroup), Write(strip.indices))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        # HashMap panel on the right
        hmap = HashMapPanel(anchor=UR, title="HashMap")
        self.play(FadeIn(hmap.vgroup))

        # Pointer
        i_ptr = Pointer("i", color=PTR_COLORS["i"]).place_below(strip, 0)
        self.play(FadeIn(i_ptr.vgroup))

        # Run algorithm
        steps, result = _hashmap_iteration_steps(arr, algorithm, target)

        act = action_text(steps[0]["action"]) if steps else action_text("...")
        self.play(FadeIn(act))

        for step in steps:
            i = step["i"]
            kind = step.get("kind", "store")

            # Move pointer + highlight current cell + sync code line
            extra = []
            hl = _hl_line(code_panel, "hashmap_iteration", algorithm, kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(
                i_ptr.anim_move_to(strip, i),
                strip.anim_set_fill(i, HILITE, 0.75),
                *extra,
                run_time=0.4,
                rate_func=smooth,
            )
            self.play(strip.flash(i, color=HILITE, scale=1.18), run_time=0.3)

            # Apply hashmap operation
            diff = step.get("hashmap_diff", {})
            anims = []
            if "set" in diff:
                k, v = diff["set"]
                anims.extend(hmap.anim_set(k, v))
            elif "flash" in diff:
                anims.extend(hmap.anim_flash(diff["flash"], color=KEEP))
            elif "delete" in diff:
                anims.extend(hmap.anim_delete(diff["delete"]))

            if anims:
                self.play(*anims, run_time=0.5)

            # Update action
            self.play(Transform(act, action_text(step["action"])), run_time=0.3)

            # Mark cell appropriately
            if kind == "match":
                self.play(strip.anim_set_fill(i, KEEP, 0.8), run_time=0.25)
                self.wait(0.5)
                break
            else:
                self.play(strip.anim_set_fill(i, DEFAULT_CELL, 0.7), run_time=0.2)

        # Final result
        if algorithm == "two_sum_hashmap":
            if result:
                msg = f"Found indices: {result}"
                vc = KEEP
            else:
                msg = "No pair found"
                vc = REJECT
        elif algorithm == "frequency_count":
            msg = f"Final counts: {len(result)} unique"
            vc = KEEP
        else:
            msg = f"{len(result)} unique characters"
            vc = KEEP

        rb = result_box(msg, font_size=24).to_edge(DOWN, buff=1.75)
        rb[1].set_color(vc)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  TwoPointersSameDirScene — slow/fast pointers both starting from left
# ===========================================================================

def _two_pointers_same_dir_steps(arr: list, algorithm: str) -> tuple:
    """slow/fast pointer steps. Each step: {slow, fast, action, kind}."""
    steps = []
    work = list(arr)

    if algorithm == "remove_duplicates":
        if not work:
            return steps, work
        slow = 0
        for fast in range(1, len(work)):
            steps.append({
                "slow": slow, "fast": fast,
                "action": f"compare arr[{slow}]={work[slow]} vs arr[{fast}]={work[fast]}",
                "kind": "compare",
            })
            if work[fast] != work[slow]:
                slow += 1
                work[slow] = work[fast]
                steps.append({
                    "slow": slow, "fast": fast,
                    "action": f"unique → write to arr[{slow}]={work[fast]}",
                    "kind": "write", "write_value": work[fast],
                })
        return steps, work[:slow + 1]

    elif algorithm == "move_zeros":
        slow = 0
        for fast in range(len(work)):
            if work[fast] != 0:
                if slow != fast:
                    work[slow], work[fast] = work[fast], work[slow]
                    steps.append({
                        "slow": slow, "fast": fast,
                        "action": f"swap arr[{slow}] ↔ arr[{fast}]",
                        "kind": "swap",
                    })
                else:
                    steps.append({
                        "slow": slow, "fast": fast,
                        "action": f"arr[{fast}]={work[fast]} non-zero, in place",
                        "kind": "skip",
                    })
                slow += 1
            else:
                steps.append({
                    "slow": slow, "fast": fast,
                    "action": f"arr[{fast}]=0, advance fast",
                    "kind": "advance_fast",
                })
        return steps, work

    return steps, work


class TwoPointersSameDirScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        arr       = p.get("array") or [1, 1, 2, 2, 3, 4, 4, 5]
        algorithm = p.get("algorithm", "remove_duplicates")
        cap       = p.get("caption", "")

        titles = {
            "remove_duplicates": "Two Pointers — Remove Duplicates",
            "move_zeros":        "Two Pointers — Move Zeros to End",
        }
        title = Text(titles.get(algorithm, algorithm), font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, algorithm, "two_pointers_same_dir",
                                      custom_code=p.get("pseudocode", ""))

        strip = ArrayStrip(arr, position=UP * 0.4)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(strip.vgroup), Write(strip.indices))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        slow_p = Pointer("slow", color=PTR_COLORS["slow"], label_size=14).place_below(strip, 0)
        fast_p = Pointer("fast", color=PTR_COLORS["fast"], label_size=14).place_below(strip, 0, extra_down=0.35)
        self.play(FadeIn(slow_p.vgroup), FadeIn(fast_p.vgroup))

        state = StatePanel(anchor=UR, title="State")
        self.play(FadeIn(state.vgroup))
        self.play(*state.anim_set("slow", 0, color=PTR_COLORS["slow"]))
        self.play(*state.anim_set("fast", 0, color=PTR_COLORS["fast"]))

        steps, result = _two_pointers_same_dir_steps(arr, algorithm)
        act = action_text(steps[0]["action"]) if steps else action_text("...")
        self.play(FadeIn(act))

        for step in steps:
            slow, fast = step["slow"], step["fast"]
            kind = step["kind"]

            extra = []
            hl = _hl_line(code_panel, "two_pointers_same_dir", algorithm, kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(
                slow_p.anim_move_to(strip, slow),
                fast_p.anim_move_to(strip, fast, extra_down=0.35),
                *extra,
                run_time=0.4, rate_func=smooth,
            )
            self.play(*state.anim_set("slow", slow, color=PTR_COLORS["slow"]),
                      *state.anim_set("fast", fast, color=PTR_COLORS["fast"]),
                      run_time=0.25)

            if kind in ("compare", "skip", "advance_fast"):
                self.play(strip.anim_set_fill(fast, HILITE, 0.7), run_time=0.2)
                self.play(Transform(act, action_text(step["action"])), run_time=0.25)
                self.wait(0.3)
                self.play(strip.anim_set_fill(fast, DEFAULT_CELL, 0.7), run_time=0.15)
            elif kind == "write":
                self.play(
                    strip.anim_set_value(slow, step["write_value"]),
                    strip.anim_set_fill(slow, KEEP, 0.85),
                    run_time=0.4,
                )
                self.play(strip.flash(slow, color=KEEP, scale=1.2), run_time=0.3)
                self.play(Transform(act, action_text(step["action"])), run_time=0.25)
            elif kind == "swap":
                self.play(
                    strip.anim_set_fill(slow, HILITE, 0.85),
                    strip.anim_set_fill(fast, HILITE, 0.85),
                    run_time=0.2,
                )
                # swap visuals
                a = arr[slow]; b = arr[fast]
                self.play(
                    strip.anim_set_value(slow, b),
                    strip.anim_set_value(fast, a),
                    run_time=0.4,
                )
                arr[slow], arr[fast] = arr[fast], arr[slow]
                self.play(Transform(act, action_text(step["action"])), run_time=0.25)
                self.play(
                    strip.anim_set_fill(slow, KEEP, 0.7),
                    strip.anim_set_fill(fast, DEFAULT_CELL, 0.7),
                    run_time=0.2,
                )

        rb = result_box(f"Result: {result}", font_size=24).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  SlidingWindowVariableScene — expanding/contracting window
# ===========================================================================

def _sliding_window_variable_steps(arr: list, algorithm: str, k=None) -> tuple:
    """Each step: {L, R, action, kind, hashmap_diff, length}."""
    steps = []

    if algorithm == "longest_no_repeat":
        seen = {}
        L = 0
        best = 0
        best_window = (0, -1)
        for R in range(len(arr)):
            ch = str(arr[R])
            steps.append({
                "L": L, "R": R, "kind": "expand",
                "action": f"expand R: include '{ch}'",
                "hashmap_diff": {"set": (ch, 1)} if ch not in seen or seen[ch] < L else {"set": (ch, seen.get(ch, 0) + 1)},
            })
            if ch in seen and seen[ch] >= L:
                # shrink
                while seen.get(ch, -1) >= L:
                    L_ch = str(arr[L])
                    L += 1
                    steps.append({
                        "L": L, "R": R, "kind": "shrink",
                        "action": f"duplicate '{ch}', shrink L past '{L_ch}'",
                        "hashmap_diff": {"delete": L_ch},
                    })
            seen[ch] = R
            length = R - L + 1
            if length > best:
                best = length
                best_window = (L, R)
                steps.append({
                    "L": L, "R": R, "kind": "best",
                    "action": f"new best length = {length}",
                    "hashmap_diff": {"flash": ch},
                    "length": length,
                })
        return steps, (best, best_window)

    elif algorithm == "longest_at_most_k_distinct":
        kk = int(k) if k else 2
        counts = {}
        L = 0
        best = 0
        for R in range(len(arr)):
            ch = str(arr[R])
            counts[ch] = counts.get(ch, 0) + 1
            steps.append({
                "L": L, "R": R, "kind": "expand",
                "action": f"add '{ch}', distinct={len(counts)}",
                "hashmap_diff": {"set": (ch, counts[ch])},
            })
            while len(counts) > kk:
                L_ch = str(arr[L])
                counts[L_ch] -= 1
                if counts[L_ch] == 0:
                    del counts[L_ch]
                    diff = {"delete": L_ch}
                else:
                    diff = {"set": (L_ch, counts[L_ch])}
                L += 1
                steps.append({
                    "L": L, "R": R, "kind": "shrink",
                    "action": f"too many distinct, shrink L past '{L_ch}'",
                    "hashmap_diff": diff,
                })
            length = R - L + 1
            if length > best:
                best = length
                steps.append({
                    "L": L, "R": R, "kind": "best",
                    "action": f"best length so far = {length}",
                    "hashmap_diff": {"none": True}, "length": length,
                })
        return steps, best

    return steps, None


class SlidingWindowVariableScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        arr       = p.get("array") or ["a", "b", "c", "a", "b", "c", "b", "b"]
        algorithm = p.get("algorithm", "longest_no_repeat")
        k         = p.get("k")
        cap       = p.get("caption", "")

        titles = {
            "longest_no_repeat":         "Sliding Window — Longest Without Repeating",
            "longest_at_most_k_distinct": f"Sliding Window — At Most {k or 2} Distinct",
        }
        title = Text(titles.get(algorithm, algorithm), font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, algorithm, "sliding_window_variable",
                                      custom_code=p.get("pseudocode", ""))

        strip = ArrayStrip(arr, position=LEFT * 2.0 + UP * 0.4)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(strip.vgroup), Write(strip.indices))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        zone = HighlightZone(strip, 0, 0, color=YELLOW)
        L_ptr = Pointer("L", color=PTR_COLORS["L"]).place_below(strip, 0)
        R_ptr = Pointer("R", color=PTR_COLORS["R"]).place_below(strip, 0, extra_down=0.35)
        self.play(Create(zone.rect), FadeIn(L_ptr.vgroup), FadeIn(R_ptr.vgroup))

        hmap = HashMapPanel(anchor=UR, title="Counts")
        self.play(FadeIn(hmap.vgroup))

        steps, result = _sliding_window_variable_steps(arr, algorithm, k)
        act = action_text(steps[0]["action"]) if steps else action_text("...")
        self.play(FadeIn(act))

        for step in steps:
            L, R = step["L"], step["R"]
            kind = step["kind"]

            # Sync code line to step kind
            extra = []
            hl = _hl_line(code_panel, "sliding_window_variable", algorithm, kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(
                zone.anim_to(L, R),
                L_ptr.anim_move_to(strip, L),
                R_ptr.anim_move_to(strip, R, extra_down=0.35),
                *extra,
                run_time=0.4, rate_func=smooth,
            )

            for i in range(len(arr)):
                strip.cells[i][0].set_fill(DEFAULT_CELL, opacity=0.5)
            for i in range(L, R + 1):
                strip.cells[i][0].set_fill(YELLOW, opacity=0.55)
            if kind == "best":
                for i in range(L, R + 1):
                    strip.cells[i][0].set_fill(KEEP, opacity=0.65)

            diff = step.get("hashmap_diff", {})
            anims = []
            if "set" in diff:
                anims.extend(hmap.anim_set(*diff["set"]))
            elif "delete" in diff:
                anims.extend(hmap.anim_delete(diff["delete"]))
            elif "flash" in diff:
                anims.extend(hmap.anim_flash(diff["flash"], color=KEEP))

            if anims:
                self.play(*anims, run_time=0.4)
            self.play(Transform(act, action_text(step["action"])), run_time=0.25)
            self.wait(0.25)

        if isinstance(result, tuple):
            best_len = result[0]
        else:
            best_len = result
        rb = result_box(f"Best window length: {best_len}", font_size=26).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  BinarySearchIndexScene — L/M/R on sorted array
# ===========================================================================

def _binary_search_index_steps(arr: list, algorithm: str, target: int) -> tuple:
    """L/M/R steps. {L, R, M, action, kind, found}."""
    steps = []
    L, R = 0, len(arr) - 1
    found = -1

    if algorithm == "find_target":
        while L <= R:
            M = (L + R) // 2
            steps.append({"L": L, "R": R, "M": M,
                           "action": f"check arr[{M}]={arr[M]} vs {target}",
                           "kind": "compare"})
            if arr[M] == target:
                steps.append({"L": L, "R": R, "M": M,
                               "action": f"arr[{M}]={target} ✓ found at index {M}",
                               "kind": "match", "found": True})
                return steps, M
            elif arr[M] < target:
                steps.append({"L": L, "R": R, "M": M,
                               "action": f"arr[{M}]={arr[M]} < {target}, go right",
                               "kind": "go_right"})
                L = M + 1
            else:
                steps.append({"L": L, "R": R, "M": M,
                               "action": f"arr[{M}]={arr[M]} > {target}, go left",
                               "kind": "go_left"})
                R = M - 1
        steps.append({"L": L, "R": R, "M": -1,
                       "action": f"{target} not found", "kind": "not_found"})
        return steps, -1

    elif algorithm == "first_occurrence":
        while L <= R:
            M = (L + R) // 2
            steps.append({"L": L, "R": R, "M": M,
                           "action": f"check arr[{M}]={arr[M]} vs {target}",
                           "kind": "compare"})
            if arr[M] >= target:
                if arr[M] == target:
                    found = M
                R = M - 1
                steps.append({"L": L, "R": R, "M": M,
                               "action": f"arr[{M}]>={target}, search left for first",
                               "kind": "go_left"})
            else:
                L = M + 1
                steps.append({"L": L, "R": R, "M": M,
                               "action": f"arr[{M}]<{target}, go right",
                               "kind": "go_right"})
        if found >= 0:
            steps.append({"L": L, "R": R, "M": found,
                           "action": f"first {target} at index {found}",
                           "kind": "match", "found": True})
        return steps, found

    return steps, -1


class BinarySearchIndexScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        arr       = p.get("array") or [1, 3, 5, 7, 9, 11, 13, 15]
        algorithm = p.get("algorithm", "find_target")
        target    = int(p.get("target", 7))
        cap       = p.get("caption", "")

        titles = {
            "find_target":      f"Binary Search — find {target}",
            "first_occurrence": f"Binary Search — first occurrence of {target}",
        }
        title = Text(titles.get(algorithm, algorithm), font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, algorithm, "binary_search_index",
                                      custom_code=p.get("pseudocode", ""))

        strip = ArrayStrip(arr, position=UP * 0.6)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(strip.vgroup), Write(strip.indices))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        L_p = Pointer("L", color=PTR_COLORS["L"]).place_below(strip, 0)
        R_p = Pointer("R", color=PTR_COLORS["R"]).place_below(strip, len(arr) - 1)
        M_p = Pointer("M", color=PTR_COLORS["M"]).place_below(strip, len(arr) // 2, extra_down=0.35)
        self.play(FadeIn(L_p.vgroup), FadeIn(R_p.vgroup), FadeIn(M_p.vgroup))

        steps, _ = _binary_search_index_steps(arr, algorithm, target)
        act = action_text(steps[0]["action"]) if steps else action_text("...")
        self.play(FadeIn(act))

        for step in steps:
            L, R, M = step["L"], step["R"], step["M"]
            kind = step["kind"]

            anims = [L_p.anim_move_to(strip, L), R_p.anim_move_to(strip, R)]
            if M >= 0:
                anims.append(M_p.anim_move_to(strip, M, extra_down=0.35))
            hl = _hl_line(code_panel, "binary_search_index", algorithm, kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                anims.append(hl)
            self.play(*anims, run_time=0.4, rate_func=smooth)

            if M >= 0:
                self.play(strip.anim_set_fill(M, HILITE, 0.85), run_time=0.25)
                self.play(strip.flash(M, color=HILITE, scale=1.2), run_time=0.25)

            if kind == "match":
                self.play(strip.anim_set_fill(M, KEEP, 0.85))
            elif kind in ("go_right", "go_left"):
                # dim out the eliminated half
                eliminated = list(range(0, L)) + list(range(R + 1, len(arr)))
                if eliminated:
                    self.play(*[strip.anim_set_fill(i, DEFAULT_CELL, 0.25)
                                for i in eliminated], run_time=0.2)
                if M >= 0:
                    self.play(strip.anim_set_fill(M, DEFAULT_CELL, 0.7), run_time=0.15)

            self.play(Transform(act, action_text(step["action"])), run_time=0.25)
            self.wait(0.3)

        self.wait(0.6)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  BinarySearchAnswerScene — search the answer space
# ===========================================================================

def _binary_search_answer_steps(min_v: int, max_v: int, true_at: int) -> list:
    """Find smallest v in [min_v, max_v] such that predicate(v) is True.
       'predicate(v) = True' iff v >= true_at."""
    steps = []
    L, R = min_v, max_v
    while L < R:
        M = (L + R) // 2
        is_true = M >= true_at
        steps.append({"L": L, "R": R, "M": M, "predicate": is_true,
                       "action": f"predicate({M}) = {is_true}"})
        if is_true:
            R = M
        else:
            L = M + 1
    steps.append({"L": L, "R": R, "M": L, "predicate": True,
                   "action": f"smallest valid value: {L}",
                   "found": True})
    return steps


class BinarySearchAnswerScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        min_v   = int(p.get("min_value", 1))
        max_v   = int(p.get("max_value", 16))
        true_at = int(p.get("true_at", 7))
        plabel  = p.get("predicate_label", "feasible(x)")
        cap     = p.get("caption", "")

        title = Text("Binary Search on Answer Space", font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, "default", "binary_search_answer",
                                      custom_code=p.get("pseudocode", ""))
        # Use a virtual array of values [min_v..max_v]
        values = list(range(min_v, max_v + 1))
        strip = ArrayStrip(values, position=UP * 0.4)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(strip.vgroup), Write(strip.indices))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        L_p = Pointer("L", color=PTR_COLORS["L"]).place_below(strip, 0)
        R_p = Pointer("R", color=PTR_COLORS["R"]).place_below(strip, len(values) - 1)
        M_p = Pointer("M", color=PTR_COLORS["M"]).place_below(strip, len(values) // 2, extra_down=0.35)
        self.play(FadeIn(L_p.vgroup), FadeIn(R_p.vgroup), FadeIn(M_p.vgroup))

        state = StatePanel(anchor=UR, title=plabel)
        self.play(FadeIn(state.vgroup))

        steps = _binary_search_answer_steps(min_v, max_v, true_at)
        act = action_text(steps[0]["action"]) if steps else action_text("...")
        self.play(FadeIn(act))

        for step in steps:
            L_idx = step["L"] - min_v
            R_idx = step["R"] - min_v
            M_idx = step["M"] - min_v
            pred  = step["predicate"]

            # Synthesize kind from predicate result for line highlighting
            kind = "true" if pred else "false"
            extra = []
            hl = _hl_line(code_panel, "binary_search_answer", "default", kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(
                L_p.anim_move_to(strip, L_idx),
                R_p.anim_move_to(strip, R_idx),
                M_p.anim_move_to(strip, M_idx, extra_down=0.35),
                *extra,
                run_time=0.4, rate_func=smooth,
            )
            self.play(strip.anim_set_fill(M_idx, HILITE, 0.85), run_time=0.2)
            self.play(*state.anim_set("predicate", "True" if pred else "False",
                                       color=KEEP if pred else REJECT),
                      run_time=0.25)
            self.play(Transform(act, action_text(step["action"])), run_time=0.25)
            self.wait(0.4)

            # Dim eliminated cells
            for i in range(len(values)):
                if i < L_idx or i > R_idx:
                    strip.cells[i][0].set_fill(DEFAULT_CELL, opacity=0.18)

        # Final answer
        ans_idx = steps[-1]["M"] - min_v
        self.play(strip.anim_set_fill(ans_idx, KEEP, 0.95))
        self.play(strip.flash(ans_idx, color=KEEP, scale=1.3))

        rb = result_box(f"Answer: {steps[-1]['M']}", font_size=26).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  MonotonicStackScene — stack maintains monotonic invariant
# ===========================================================================

def _monotonic_stack_steps(arr: list, monotone: str = "decreasing") -> tuple:
    """Returns (steps, result_array). Each step:
       {i, value, action, kind, popped: list, push: bool, stack_after: list}"""
    steps = []
    stack = []  # of indices
    result = [-1] * len(arr)  # next greater element

    for i, v in enumerate(arr):
        popped = []
        if monotone == "decreasing":
            while stack and arr[stack[-1]] < v:
                p = stack.pop()
                popped.append(p)
                result[p] = v
        else:
            while stack and arr[stack[-1]] > v:
                p = stack.pop()
                popped.append(p)
                result[p] = v

        for p in popped:
            steps.append({
                "i": i, "value": v, "kind": "pop",
                "popped_idx": p, "popped_val": arr[p],
                "stack_after": list(stack),
                "action": f"arr[{i}]={v} > arr[{p}]={arr[p]}, pop and resolve {arr[p]}",
            })

        stack.append(i)
        steps.append({
            "i": i, "value": v, "kind": "push",
            "stack_after": list(stack),
            "action": f"push {v} onto stack",
        })

    return steps, result


class MonotonicStackScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        arr       = p.get("array") or [2, 1, 5, 6, 2, 3]
        algorithm = p.get("algorithm", "next_greater")
        monotone  = p.get("monotone", "decreasing")
        cap       = p.get("caption", "")

        titles = {
            "next_greater":        "Monotonic Stack — Next Greater Element",
            "daily_temperatures":  "Monotonic Stack — Daily Temperatures",
        }
        title = Text(titles.get(algorithm, algorithm), font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, algorithm, "monotonic_stack",
                                      custom_code=p.get("pseudocode", ""))

        strip = ArrayStrip(arr, position=LEFT * 1.5 + UP * 0.5)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(strip.vgroup), Write(strip.indices))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        i_ptr = Pointer("i", color=PTR_COLORS["i"]).place_below(strip, 0)
        self.play(FadeIn(i_ptr.vgroup))

        # Stack on the right
        stack_pos = RIGHT * 4 + DOWN * 0.5
        stack_w = StackWidget(position=stack_pos, max_visible=6, cell_w=1.0,
                              title="Stack (idx)")
        self.play(FadeIn(stack_w.vgroup))

        # Result strip below input — kept above the result_box zone (buff=1.75)
        result_strip = ArrayStrip([-1] * len(arr),
                                   position=LEFT * 1.5 + DOWN * 1.0,
                                   with_indices=False)
        result_label = Text("result:", font_size=18, color=GRAY).next_to(result_strip.vgroup, LEFT, buff=0.3)
        self.play(FadeIn(result_strip.vgroup), FadeIn(result_label))

        steps, result = _monotonic_stack_steps(arr, monotone)
        act = action_text(steps[0]["action"]) if steps else action_text("...")
        self.play(FadeIn(act))

        for step in steps:
            i = step["i"]
            kind = step["kind"]

            extra = []
            hl = _hl_line(code_panel, "monotonic_stack", algorithm, kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(i_ptr.anim_move_to(strip, i), *extra,
                      run_time=0.3, rate_func=smooth)
            self.play(strip.anim_set_fill(i, HILITE, 0.7), run_time=0.2)

            if kind == "pop":
                # NOTE: don't reuse `p` here — it shadows the params dict
                # used by the outer step_lines_override=p.get(...) call.
                pop_idx = step["popped_idx"]
                v = step["value"]
                # Update result strip cell
                self.play(strip.flash(pop_idx, color=REJECT, scale=1.2), run_time=0.25)
                val, anims = stack_w.anim_pop()
                if anims:
                    self.play(*anims, run_time=0.4)
                self.play(
                    result_strip.anim_set_value(pop_idx, v),
                    result_strip.anim_set_fill(pop_idx, KEEP, 0.7),
                    run_time=0.3,
                )
            elif kind == "push":
                _, anims = stack_w.anim_push(i, color=BLUE_D)
                if anims:
                    self.play(*anims, run_time=0.4)

            self.play(Transform(act, action_text(step["action"])), run_time=0.25)
            self.wait(0.2)

        rb = result_box(f"Result: {result}", font_size=22).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  PrefixSumScene — cumulative sum overlay
# ===========================================================================

def _prefix_sum_steps(arr: list, algorithm: str, query_range=None, target=None) -> tuple:
    """Steps for building/querying a prefix sum array."""
    steps = []
    prefix = [0] * (len(arr) + 1)

    # Always build the prefix array first
    for i, v in enumerate(arr):
        prefix[i + 1] = prefix[i] + v
        steps.append({
            "i": i + 1, "value": prefix[i + 1], "deps": [i, i + 1],
            "kind": "build",
            "action": f"prefix[{i+1}] = prefix[{i}] + arr[{i}] = {prefix[i]} + {v} = {prefix[i+1]}",
        })

    if algorithm == "build_prefix":
        return steps, prefix

    if algorithm == "range_sum_query":
        l, r = query_range or [0, len(arr) - 1]
        ans = prefix[r + 1] - prefix[l]
        steps.append({
            "kind": "query", "l": l, "r": r, "ans": ans,
            "action": f"sum({l}..{r}) = prefix[{r+1}] - prefix[{l}] = {prefix[r+1]} - {prefix[l]} = {ans}",
        })
        return steps, ans

    return steps, prefix


class PrefixSumScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        arr       = p.get("array") or [3, 1, 4, 1, 5, 9, 2]
        algorithm = p.get("algorithm", "build_prefix")
        query_range = p.get("query_range")
        cap       = p.get("caption", "")

        titles = {
            "build_prefix":      "Prefix Sum — Build Cumulative Array",
            "range_sum_query":   f"Prefix Sum — Range Query [{query_range}]" if query_range else "Prefix Sum — Range Query",
        }
        title = Text(titles.get(algorithm, algorithm), font_size=28).to_edge(UP, buff=0.3)
        # Use UR anchor for the code panel — UL would collide with the in_strip label
        catalog_entry = _PATTERN_CATALOG.get(("prefix_sum", algorithm))
        custom_code = (p.get("pseudocode") or "").strip()
        code_panel = None
        badge_v = None
        if catalog_entry is not None or custom_code:
            if custom_code:
                pseudo = custom_code
                t_complex, s_complex = (catalog_entry[1], catalog_entry[2]) if catalog_entry else ("—", "—")
            else:
                pseudo, t_complex, s_complex = catalog_entry
            code_panel = CodePanel(pseudo, anchor=UR, font_size=14, max_width=4.0)
            code_panel.is_custom = bool(custom_code)
            _badge = ComplexityBadge(time=t_complex, space=s_complex, font_size=14)
            if title.width > 6.0:
                _badge.vgroup.next_to(title, DOWN, buff=0.15)
            else:
                _badge.vgroup.next_to(title, RIGHT, buff=0.3)
            badge_v = _badge.vgroup

        # Input array on top
        in_strip = ArrayStrip(arr, position=UP * 1.4)
        in_lbl = Text("arr:", font_size=18, color=GRAY).next_to(in_strip.vgroup, LEFT, buff=0.25)

        # Prefix array on bottom (length n+1)
        prefix_init = [0] * (len(arr) + 1)
        pre_strip = ArrayStrip(prefix_init, position=DOWN * 0.6)
        pre_lbl = Text("prefix:", font_size=18, color=GRAY).next_to(pre_strip.vgroup, LEFT, buff=0.25)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(in_strip.vgroup), Write(in_strip.indices), FadeIn(in_lbl))
        self.play(FadeIn(pre_strip.vgroup), Write(pre_strip.indices), FadeIn(pre_lbl))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        steps, result = _prefix_sum_steps(arr, algorithm, query_range)
        act = action_text(steps[0]["action"]) if steps else action_text("...")
        self.play(FadeIn(act))

        for step in steps:
            kind = step["kind"]
            extra = []
            hl = _hl_line(code_panel, "prefix_sum", algorithm, kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)

            if kind == "build":
                i = step["i"]   # index into prefix (1..n)
                # Highlight prefix[i-1] (dep) and arr[i-1] (input) + sync code line
                self.play(
                    pre_strip.anim_set_fill(i - 1, HILITE, 0.7),
                    in_strip.anim_set_fill(i - 1, HILITE, 0.7),
                    *extra,
                    run_time=0.25,
                )
                # Update prefix[i]
                self.play(
                    pre_strip.anim_set_value(i, step["value"]),
                    pre_strip.anim_set_fill(i, KEEP, 0.85),
                    run_time=0.4,
                )
                self.play(pre_strip.flash(i, color=KEEP, scale=1.18), run_time=0.25)
                self.play(Transform(act, action_text(step["action"])), run_time=0.25)
                # Reset
                self.play(
                    pre_strip.anim_set_fill(i - 1, DEFAULT_CELL, 0.7),
                    in_strip.anim_set_fill(i - 1, DEFAULT_CELL, 0.7),
                    pre_strip.anim_set_fill(i, DEFAULT_CELL, 0.7),
                    run_time=0.2,
                )

            elif kind == "query":
                l, r = step["l"], step["r"]
                # Highlight prefix[r+1] and prefix[l] simultaneously + code line
                self.play(
                    pre_strip.anim_set_fill(r + 1, HILITE, 0.85),
                    pre_strip.anim_set_fill(l, REJECT, 0.85),
                    *extra,
                    run_time=0.3,
                )
                # Highlight the input range too
                for i in range(l, r + 1):
                    in_strip.cells[i][0].set_fill(KEEP, opacity=0.6)
                self.play(*[in_strip.flash(i, color=KEEP, scale=1.1) for i in range(l, r + 1)],
                          run_time=0.4)
                self.play(Transform(act, action_text(step["action"])), run_time=0.3)

                rb = result_box(f"Range sum = {step['ans']}", font_size=26).to_edge(DOWN, buff=1.75)
                rb[1].set_color(KEEP)
                self.play(FadeOut(act), FadeIn(rb))

        if algorithm == "build_prefix":
            rb = result_box(f"Built: {result}", font_size=22).to_edge(DOWN, buff=1.75)
            rb[1].set_color(KEEP)
            self.play(FadeOut(act), FadeIn(rb))

        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  KadanesScene — maximum subarray sum
# ===========================================================================

def _kadanes_steps(arr: list) -> tuple:
    """Each step: {i, value, current_sum, max_sum, l, r, kind, action}."""
    steps = []
    if not arr:
        return steps, (0, 0, -1)
    cur = arr[0]
    best = arr[0]
    l = r = best_l = best_r = 0
    steps.append({"i": 0, "value": arr[0], "current_sum": cur, "max_sum": best,
                   "l": l, "r": r, "kind": "init",
                   "action": f"start: cur={cur}, best={best}"})
    for i in range(1, len(arr)):
        v = arr[i]
        if cur + v < v:
            cur = v
            l = i
            kind = "reset"
            action = f"arr[{i}]={v}; cur+v < v → reset cur to {v}, l={i}"
        else:
            cur = cur + v
            kind = "extend"
            action = f"arr[{i}]={v}; extend cur to {cur}"
        r = i
        if cur > best:
            best = cur
            best_l, best_r = l, r
            kind = "new_max"
            action = f"new max! cur={cur}, window=[{best_l}..{best_r}]"
        steps.append({"i": i, "value": v, "current_sum": cur, "max_sum": best,
                       "l": l, "r": r, "kind": kind, "action": action})
    return steps, (best, best_l, best_r)


_KADANES_PSEUDOCODE = """
cur = best = arr[0]
for x in arr[1:]:
    cur = max(x, cur + x)
    best = max(best, cur)
return best
""".strip()


class KadanesScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        arr = p.get("array") or [-2, 1, -3, 4, -1, 2, 1, -5, 4]
        cap = p.get("caption", "")

        title = Text("Kadane's — Maximum Subarray Sum", font_size=28).to_edge(UP, buff=0.3)
        strip = ArrayStrip(arr, position=UP * 0.5)
        custom_code = (p.get("pseudocode") or "").strip()
        code_panel = CodePanel(custom_code or _KADANES_PSEUDOCODE,
                               anchor=UL, font_size=16, max_width=3.6)
        code_panel.is_custom = bool(custom_code)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        self.play(FadeIn(strip.vgroup), Write(strip.indices), FadeIn(code_panel.vgroup))
        self.play(code_panel.anim_dim_all(), run_time=0.2)
        # Initialize: highlight line 0 (cur = best = arr[0])
        self.play(code_panel.anim_highlight(0), run_time=0.25)

        i_ptr = Pointer("i", color=PTR_COLORS["i"]).place_below(strip, 0)
        self.play(FadeIn(i_ptr.vgroup))

        state = StatePanel(anchor=UR, title="State")
        self.play(FadeIn(state.vgroup))
        self.play(*state.anim_set("cur", 0, color=YELLOW),
                  *state.anim_set("max", 0, color=GREEN), run_time=0.3)

        steps, (best, bl, br) = _kadanes_steps(arr)
        act = action_text(steps[0]["action"]) if steps else action_text("...")
        self.play(FadeIn(act))

        for step in steps:
            i = step["i"]
            kind = step["kind"]

            # Move pointer + highlight current cell + step into the for-loop body (line 1)
            self.play(
                i_ptr.anim_move_to(strip, i),
                strip.anim_set_fill(i, HILITE, 0.85),
                code_panel.anim_highlight(1),
                run_time=0.35, rate_func=smooth,
            )

            # cur = max(x, cur + x) — line 2
            self.play(code_panel.anim_highlight(2), run_time=0.2)

            if kind == "reset":
                # current_sum dropped — flash red
                self.play(strip.flash(i, color=REJECT, scale=1.2), run_time=0.2)
            elif kind == "new_max":
                self.play(strip.flash(i, color=KEEP, scale=1.25), run_time=0.25)

            # best = max(best, cur) — line 3
            self.play(code_panel.anim_highlight(3),
                      *state.anim_set("cur", step["current_sum"], color=YELLOW),
                      *state.anim_set("max", step["max_sum"], color=GREEN),
                      run_time=0.3)
            self.play(Transform(act, action_text(step["action"])), run_time=0.25)

            # Color the current best window in green
            if step["kind"] == "new_max":
                for k in range(len(arr)):
                    if step["l"] <= k <= step["r"]:
                        strip.cells[k][0].set_fill(KEEP, opacity=0.6)
                    else:
                        strip.cells[k][0].set_fill(DEFAULT_CELL, opacity=0.5)
            else:
                self.play(strip.anim_set_fill(i, DEFAULT_CELL, 0.55), run_time=0.15)

            self.wait(0.2)

        # Final return statement — line 4
        self.play(code_panel.anim_highlight(4), run_time=0.3)

        # Final green-window emphasis
        for k in range(len(arr)):
            strip.cells[k][0].set_fill(KEEP if bl <= k <= br else DEFAULT_CELL,
                                        opacity=0.75 if bl <= k <= br else 0.4)
        self.play(*[strip.flash(k, color=KEEP) for k in range(bl, br + 1)],
                  run_time=0.45)

        rb = result_box(f"Max subarray sum = {best}  [{bl}..{br}]",
                        font_size=24).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  IntervalMergingScene — merge overlapping intervals
# ===========================================================================

def _interval_merging_steps(intervals: list) -> tuple:
    """Each step: {kind: 'sort'|'examine'|'merge'|'emit', ...}."""
    steps = []
    sorted_iv = sorted(range(len(intervals)), key=lambda k: intervals[k][0])
    sorted_pairs = [list(intervals[k]) for k in sorted_iv]
    steps.append({"kind": "sort", "order": sorted_iv,
                   "action": f"sort by start → indices {sorted_iv}"})

    merged = []
    merged_origin = []  # which sorted-position created each merged bar
    for pos, iv in enumerate(sorted_pairs):
        if not merged:
            merged.append(list(iv))
            merged_origin.append(pos)
            steps.append({"kind": "emit", "merged_idx": 0, "src_pos": pos,
                           "interval": list(iv),
                           "action": f"first interval {iv} → start merged"})
            continue
        last = merged[-1]
        if iv[0] <= last[1]:
            new_end = max(last[1], iv[1])
            steps.append({"kind": "merge", "merged_idx": len(merged) - 1,
                           "src_pos": pos, "interval": list(iv),
                           "old_end": last[1], "new_end": new_end,
                           "action": f"{iv} overlaps last; extend end to {new_end}"})
            last[1] = new_end
        else:
            merged.append(list(iv))
            merged_origin.append(pos)
            steps.append({"kind": "emit", "merged_idx": len(merged) - 1,
                           "src_pos": pos, "interval": list(iv),
                           "action": f"{iv} disjoint; emit new merged interval"})
    return steps, merged


class IntervalMergingScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        intervals = p.get("intervals", [[1, 3], [2, 6], [8, 10], [15, 18]])
        cap = p.get("caption", "")

        title = Text("Merge Overlapping Intervals", font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, "default", "interval_merging",
                                      custom_code=p.get("pseudocode", ""))
        bars = IntervalBars(intervals, position=UP * 0.2)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(bars.vgroup))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        steps, merged = _interval_merging_steps(intervals)
        act = action_text(steps[0]["action"]) if steps else action_text("...")
        self.play(FadeIn(act))
        self.wait(0.4)

        for step in steps[1:]:
            kind = step["kind"]
            pos = step["src_pos"]
            extra = []
            hl = _hl_line(code_panel, "interval_merging", "default", kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(Transform(act, action_text(step["action"])), *extra, run_time=0.25)
            if kind == "emit":
                self.play(bars.anim_set_color(pos, KEEP), run_time=0.3)
            elif kind == "merge":
                anims = bars.anim_merge(step["merged_idx"], pos, step["new_end"])
                self.play(*anims, run_time=0.5)
            self.wait(0.4)

        rb = result_box(f"merged: {merged}", font_size=24).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.9)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  UnionFindScene — disjoint set with parent[] visualization
# ===========================================================================

def _union_find_steps(n: int, operations: list) -> tuple:
    """Operations: ['union 0 1', 'union 2 3', 'find 0', ...]
    Each step: {op, a, b?, parent_before, parent_after, root_a?, root_b?, action, kind}.
    """
    parent = list(range(n))
    steps = []

    def find_root(x):
        path = [x]
        while parent[x] != x:
            x = parent[x]
            path.append(x)
        return x, path

    def _maybe_int(s):
        try:
            return int(s)
        except (ValueError, TypeError):
            return None

    for raw in operations:
        parts = raw.strip().split()
        if not parts:
            continue
        op = parts[0]
        if op == "union" and len(parts) >= 3:
            a = _maybe_int(parts[1]); b = _maybe_int(parts[2])
            if a is None or b is None or not (0 <= a < n) or not (0 <= b < n):
                continue   # skip malformed op silently
            ra, _ = find_root(a)
            rb, _ = find_root(b)
            before = list(parent)
            if ra == rb:
                steps.append({"op": "union", "a": a, "b": b,
                               "ra": ra, "rb": rb, "kind": "noop",
                               "parent_before": before, "parent_after": before,
                               "action": f"union({a},{b}): same root {ra}"})
            else:
                parent[ra] = rb  # naive union: a's root → b's root
                after = list(parent)
                steps.append({"op": "union", "a": a, "b": b,
                               "ra": ra, "rb": rb, "kind": "linked",
                               "parent_before": before, "parent_after": after,
                               "action": f"union({a},{b}): root {ra} → {rb}"})
        elif op == "find" and len(parts) >= 2:
            a = _maybe_int(parts[1])
            if a is None or not (0 <= a < n):
                continue
            ra, path = find_root(a)
            steps.append({"op": "find", "a": a, "ra": ra, "kind": "find",
                           "path": path,
                           "parent_before": list(parent), "parent_after": list(parent),
                           "action": f"find({a}) → root {ra}  via path {path}"})
    components = len({find_root(i)[0] for i in range(n)})
    return steps, components


class UnionFindScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        n = int(p.get("n", 6))
        operations = p.get("operations") or ["union 0 1", "union 2 3", "union 4 5", "union 1 3", "find 4"]
        cap = p.get("caption", "")

        title = Text("Union-Find — Disjoint Set Forest", font_size=26).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, "default", "union_find",
                                      custom_code=p.get("pseudocode", ""))
        strip = ArrayStrip(list(range(n)), position=UP * 0.5)
        parent_lbl = Text("parent[]:", font_size=18, color=GRAY).next_to(strip.vgroup, LEFT, buff=0.3)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(strip.vgroup), Write(strip.indices), FadeIn(parent_lbl))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        state = StatePanel(anchor=UR, title="UF")
        self.play(FadeIn(state.vgroup))
        self.play(*state.anim_set("components", n, color=KEEP), run_time=0.25)

        steps, components = _union_find_steps(n, operations)
        if not steps:
            self.wait(0.5)
            return

        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        active_arrows = {}  # i -> Arrow

        for step in steps:
            kind = step["kind"]
            extra = []
            hl = _hl_line(code_panel, "union_find", "default", kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(Transform(act, action_text(step["action"])), *extra, run_time=0.25)

            if kind == "linked":
                ra, rb = step["ra"], step["rb"]
                # Update the parent[] cell visually
                self.play(strip.anim_set_value(ra, rb),
                          strip.anim_set_fill(ra, HILITE, 0.85),
                          run_time=0.4)
                # Draw an arrow from cell ra → cell rb
                arr = Arrow(strip.cell_top(ra) + UP * 0.05,
                            strip.cell_top(rb) + UP * 0.05,
                            color=YELLOW, buff=0.05, stroke_width=3,
                            max_tip_length_to_length_ratio=0.15)
                active_arrows[ra] = arr
                self.play(Create(arr), run_time=0.3)
                self.play(strip.anim_set_fill(ra, KEEP, 0.7), run_time=0.2)
            elif kind == "find":
                # Highlight path of cells
                path = step["path"]
                anims = [strip.anim_set_fill(i, YELLOW, 0.85) for i in path]
                self.play(*anims, run_time=0.3)
                self.play(*[strip.flash(i, color=YELLOW) for i in path], run_time=0.4)
                self.wait(0.2)
                self.play(*[strip.anim_set_fill(i, DEFAULT_CELL, 0.55) for i in path],
                          run_time=0.2)
            elif kind == "noop":
                self.play(strip.flash(step["a"], color=REJECT, scale=1.1), run_time=0.25)

            self.wait(0.25)

        rb = result_box(f"connected components: {components}",
                        font_size=24).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.8)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  LRUCacheScene — hashmap + doubly-linked list
# ===========================================================================

def _lru_cache_steps(operations: list, capacity: int) -> tuple:
    """Operations like 'put 1 100', 'get 1', 'put 2 200'..."""
    steps = []
    order = []          # head -> tail (head = MRU)
    store = {}          # key -> value

    def _to_int(s):
        try:
            return int(s)
        except (ValueError, TypeError):
            return s   # keep as string if not parseable

    for raw in operations:
        parts = raw.strip().split()
        if not parts:
            continue
        op = parts[0]
        if op == "put" and len(parts) >= 3:
            k = _to_int(parts[1]); v = _to_int(parts[2])
            if k in store:
                store[k] = v
                order.remove(k)
                order.insert(0, k)
                steps.append({"op": "put", "kind": "update", "key": k, "val": v,
                               "action": f"put({k},{v}): update + move to head"})
            else:
                evicted = None
                if len(store) >= capacity:
                    evicted = order.pop()
                    store.pop(evicted, None)
                store[k] = v
                order.insert(0, k)
                steps.append({"op": "put", "kind": "insert", "key": k, "val": v,
                               "evicted": evicted,
                               "action": f"put({k},{v})" + (f" — evict {evicted}" if evicted is not None else "")})
        elif op == "get" and len(parts) >= 2:
            k = _to_int(parts[1])
            if k in store:
                order.remove(k); order.insert(0, k)
                steps.append({"op": "get", "kind": "hit", "key": k, "val": store[k],
                               "action": f"get({k}) → {store[k]}  (move to head)"})
            else:
                steps.append({"op": "get", "kind": "miss", "key": k,
                               "action": f"get({k}) → MISS"})
    return steps, {"order": order, "store": dict(store)}


class LRUCacheScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        operations = p.get("operations", ["put 1 100", "put 2 200", "get 1",
                                            "put 3 300", "get 2", "put 4 400"])
        capacity = int(p.get("capacity", 2))
        cap_text = p.get("caption", "")

        title = Text(f"LRU Cache (capacity={capacity})", font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, "default", "lru_cache",
                                      custom_code=p.get("pseudocode", ""))

        if cap_text:
            show_title_card(self, cap_text)
            self.play(FadeIn(caption_strip(cap_text)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)

        dll = DoublyLinkedListPanel(position=ORIGIN + UP * 0.2)
        self.play(FadeIn(dll.vgroup))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        hmap = HashMapPanel(anchor=UR, title="HashMap")
        self.play(FadeIn(hmap.vgroup))

        steps, _ = _lru_cache_steps(operations, capacity)
        if not steps:
            self.wait(0.5)
            return

        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        for step in steps:
            kind = step["kind"]
            extra = []
            hl = _hl_line(code_panel, "lru_cache", "default", kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(Transform(act, action_text(step["action"])), *extra, run_time=0.25)
            k = step["key"]
            if kind == "insert":
                anims = dll.anim_add_to_head(k, step["val"])
                if anims:
                    self.play(*anims, run_time=0.45)
                self.play(*hmap.anim_set(str(k), step["val"]), run_time=0.3)
                if step.get("evicted") is not None:
                    ev = step["evicted"]
                    self.play(*dll.anim_remove(ev), run_time=0.4)
                    self.play(*hmap.anim_delete(str(ev)), run_time=0.3)
            elif kind == "update":
                self.play(*hmap.anim_set(str(k), step["val"]), run_time=0.3)
                self.play(*dll.anim_move_to_head(k), run_time=0.4)
                self.play(*dll.anim_flash(k, color=YELLOW), run_time=0.25)
            elif kind == "hit":
                self.play(*dll.anim_flash(k, color=KEEP), run_time=0.3)
                self.play(*dll.anim_move_to_head(k), run_time=0.4)
                self.play(*hmap.anim_flash(str(k), color=KEEP), run_time=0.3)
            elif kind == "miss":
                self.wait(0.3)
            self.wait(0.25)

        rb = result_box(f"final order (head→tail): {dll.order()}",
                        font_size=22).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.9)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  GridTraversalScene — BFS or DFS on a grid
# ===========================================================================

def _grid_traversal_steps(grid: list, start: list, target: list, algorithm: str) -> tuple:
    """4-connected grid. 0=open, 1=wall."""
    steps = []
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    visited = [[False] * cols for _ in range(rows)]
    parent = {}
    sr, sc = start
    tr, tc = target
    visited[sr][sc] = True
    frontier = [(sr, sc)]
    found = (sr == tr and sc == tc)
    steps.append({"kind": "start", "r": sr, "c": sc,
                   "action": f"start at ({sr},{sc})"})

    def neighbors(r, c):
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc] and grid[nr][nc] == 0:
                yield nr, nc

    while frontier and not found:
        if algorithm == "bfs":
            r, c = frontier.pop(0)
        else:
            r, c = frontier.pop()
        steps.append({"kind": "visit", "r": r, "c": c,
                       "action": f"visit ({r},{c})"})
        for nr, nc in neighbors(r, c):
            visited[nr][nc] = True
            parent[(nr, nc)] = (r, c)
            frontier.append((nr, nc))
            steps.append({"kind": "enqueue", "r": nr, "c": nc,
                           "from_r": r, "from_c": c,
                           "action": f"discover ({nr},{nc}) from ({r},{c})"})
            if (nr, nc) == (tr, tc):
                found = True
                break

    path = []
    if found:
        cur = (tr, tc)
        while cur != (sr, sc):
            path.append(cur)
            cur = parent.get(cur, (sr, sc))
        path.append((sr, sc))
        path.reverse()
        steps.append({"kind": "path", "cells": path,
                       "action": f"path of length {len(path)}"})
    else:
        steps.append({"kind": "fail", "action": "target unreachable"})
    return steps, path


class GridTraversalScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        grid = p.get("grid") or [[0, 0, 1, 0], [0, 0, 0, 0], [1, 0, 1, 0], [0, 0, 0, 0]]
        # Use `or` (not .get default): protects against the param being
        # explicitly null in the JSON, where .get returns None and breaks
        # `start[0]` below.
        start = p.get("start") or [0, 0]
        target = p.get("target") or [len(grid) - 1, len(grid[0]) - 1]
        algorithm = p.get("algorithm") or "bfs"
        cap = p.get("caption", "")

        title = Text(f"Grid {algorithm.upper()} — ({start[0]},{start[1]}) -> ({target[0]},{target[1]})",
                     font_size=26).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, algorithm, "grid_traversal",
                                      custom_code=p.get("pseudocode", ""))

        display = [["·" if c == 0 else "#" for c in row] for row in grid]
        gp = GridPanel(display, position=ORIGIN + DOWN * 0.1)

        for r in range(len(grid)):
            for c in range(len(grid[0])):
                if grid[r][c] == 1:
                    gp.cells[r][c][0].set_fill("#444444", opacity=0.8)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(gp.vgroup))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        steps, path = _grid_traversal_steps(grid, start, target, algorithm)
        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        sr, sc = start; tr, tc = target
        gp.cells[sr][sc][0].set_fill(GREEN, opacity=0.85)
        gp.cells[tr][tc][0].set_fill(RED, opacity=0.5)
        self.wait(0.4)

        for step in steps:
            kind = step["kind"]
            extra = []
            hl = _hl_line(code_panel, "grid_traversal", algorithm, kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(Transform(act, action_text(step["action"])), *extra, run_time=0.2)
            if kind == "visit":
                r, c = step["r"], step["c"]
                if (r, c) != (sr, sc):
                    self.play(gp.anim_set_fill(r, c, "#3a5c8c", 0.85), run_time=0.18)
            elif kind == "enqueue":
                r, c = step["r"], step["c"]
                self.play(gp.anim_set_fill(r, c, HILITE, 0.7), run_time=0.18)
                self.play(gp.flash(r, c, color=HILITE), run_time=0.18)
            elif kind == "path":
                anims = [gp.anim_set_fill(r, c, KEEP, 0.95) for r, c in step["cells"]]
                self.play(LaggedStart(*anims, lag_ratio=0.15), run_time=0.8)
            elif kind == "fail":
                self.wait(0.3)

        rb_msg = f"path: {len(path)} cells" if path else "no path found"
        rb = result_box(rb_msg, font_size=24).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP if path else REJECT)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.9)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  HeapOpsScene — push/pop with sift-up / sift-down
# ===========================================================================

def _heap_ops_steps(operations: list, heap_type: str = "min") -> tuple:
    """Operations: 'push 5', 'push 3', 'pop' ..."""
    steps = []
    heap = []

    def cmp(a, b):
        return (a < b) if heap_type == "min" else (a > b)

    def sift_up(i):
        while i > 0:
            parent = (i - 1) // 2
            if cmp(heap[i], heap[parent]):
                heap[i], heap[parent] = heap[parent], heap[i]
                steps.append({"kind": "swap", "a": i, "b": parent,
                               "snapshot": list(heap),
                               "action": f"sift up: swap idx {i} and {parent}"})
                i = parent
            else:
                break

    def sift_down(i):
        n = len(heap)
        while True:
            l = 2 * i + 1; r = 2 * i + 2
            best = i
            if l < n and cmp(heap[l], heap[best]):
                best = l
            if r < n and cmp(heap[r], heap[best]):
                best = r
            if best == i:
                break
            heap[i], heap[best] = heap[best], heap[i]
            steps.append({"kind": "swap", "a": i, "b": best,
                           "snapshot": list(heap),
                           "action": f"sift down: swap idx {i} and {best}"})
            i = best

    def _maybe_int(s):
        try:
            return int(s)
        except (ValueError, TypeError):
            return None

    for raw in operations:
        parts = raw.strip().split()
        if not parts:
            continue
        op = parts[0]
        if op == "push" and len(parts) >= 2:
            v = _maybe_int(parts[1])
            if v is None:
                continue   # skip malformed push silently
            heap.append(v)
            steps.append({"kind": "push", "value": v, "snapshot": list(heap),
                           "action": f"push {v} at index {len(heap) - 1}"})
            sift_up(len(heap) - 1)
        elif op == "pop":
            if not heap:
                continue
            top = heap[0]
            steps.append({"kind": "pop_top", "value": top, "snapshot": list(heap),
                           "action": f"pop top = {top}"})
            last = heap.pop()
            if heap:
                heap[0] = last
                steps.append({"kind": "replace_root", "value": last, "snapshot": list(heap),
                               "action": f"move last ({last}) to root"})
                sift_down(0)
            else:
                steps.append({"kind": "empty", "snapshot": [], "action": "heap empty"})
    return steps, heap


class HeapOpsScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        operations = p.get("operations", ["push 5", "push 3", "push 8",
                                            "push 1", "push 4", "pop", "pop"])
        heap_type = p.get("heap_type", "min")
        cap = p.get("caption", "")

        title = Text(f"{heap_type.capitalize()}-Heap Operations",
                     font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, "default", "heap_ops",
                                      custom_code=p.get("pseudocode", ""))

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)

        steps, final = _heap_ops_steps(operations, heap_type)

        max_n = max((len(s.get("snapshot", [])) for s in steps), default=1)
        tree = BinaryTreePanel([0] * max(max_n, 1), position=DOWN * 0.2)
        for n in tree.nodes:
            n.set_opacity(0)
        for _, _, e in tree.edges:
            e.set_opacity(0)
        self.play(FadeIn(tree.vgroup))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        state = StatePanel(anchor=UR, title="Heap")
        self.play(FadeIn(state.vgroup))

        if not steps:
            self.wait(0.5)
            return

        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        prev_snapshot = []
        for step in steps:
            kind = step.get("kind", "")
            extra = []
            hl = _hl_line(code_panel, "heap_ops", "default", kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(Transform(act, action_text(step["action"])), *extra, run_time=0.22)
            snap = step.get("snapshot", [])

            anims = []
            for i in range(max_n):
                if i < len(snap):
                    if tree.nodes[i].get_fill_opacity() < 0.5:
                        tree.nodes[i].set_opacity(1)
                        tree.nodes[i][0].set_fill(DEFAULT_CELL, opacity=0.7)
                        anims.append(FadeIn(tree.nodes[i]))
                    if i >= len(prev_snapshot) or prev_snapshot[i] != snap[i]:
                        anims.append(tree.anim_set_value(i, snap[i]))
                else:
                    if tree.nodes[i].get_fill_opacity() > 0.1:
                        anims.append(FadeOut(tree.nodes[i]))
                        tree.nodes[i].set_opacity(0)

            for u, v, e in tree.edges:
                if u < len(snap) and v < len(snap) and e.get_stroke_opacity() < 0.5:
                    e.set_opacity(1)
                    anims.append(FadeIn(e))
                elif (u >= len(snap) or v >= len(snap)) and e.get_stroke_opacity() > 0.1:
                    anims.append(FadeOut(e))
                    e.set_opacity(0)

            if anims:
                self.play(*anims, run_time=0.4)

            kind = step["kind"]
            if kind == "swap":
                a, b = step["a"], step["b"]
                self.play(tree.flash(a, color=YELLOW),
                          tree.flash(b, color=YELLOW), run_time=0.35)
            elif kind == "push":
                self.play(tree.flash(len(snap) - 1, color=KEEP), run_time=0.3)
            elif kind == "pop_top":
                self.play(tree.flash(0, color=REJECT, scale=1.3), run_time=0.35)

            self.play(*state.anim_set("size", len(snap)), run_time=0.18)
            self.wait(0.18)
            prev_snapshot = snap

        rb = result_box(f"final heap: {final}", font_size=22).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.9)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  DP2DScene — fill a 2D DP table with dependencies
# ===========================================================================

def _dp_2d_steps(algorithm: str, input1: str, input2: str) -> tuple:
    """LCS or edit distance or unique paths."""
    steps = []
    if algorithm == "lcs":
        m, n = len(input1), len(input2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if input1[i - 1] == input2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                    steps.append({"r": i, "c": j, "value": dp[i][j],
                                   "deps": [(i - 1, j - 1)],
                                   "action": f"match '{input1[i-1]}' -> dp[{i}][{j}] = {dp[i][j]}"})
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
                    pick = (i - 1, j) if dp[i - 1][j] >= dp[i][j - 1] else (i, j - 1)
                    steps.append({"r": i, "c": j, "value": dp[i][j],
                                   "deps": [pick],
                                   "action": f"no match -> dp[{i}][{j}] = max = {dp[i][j]}"})
        return steps, dp, dp[m][n]

    if algorithm == "edit_distance":
        m, n = len(input1), len(input2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(m + 1):
            dp[i][0] = i
            steps.append({"r": i, "c": 0, "value": i, "deps": [],
                           "action": f"dp[{i}][0] = {i}"})
        for j in range(1, n + 1):
            dp[0][j] = j
            steps.append({"r": 0, "c": j, "value": j, "deps": [],
                           "action": f"dp[0][{j}] = {j}"})
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if input1[i - 1] == input2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                    steps.append({"r": i, "c": j, "value": dp[i][j],
                                   "deps": [(i - 1, j - 1)],
                                   "action": f"match -> carry dp[{i-1}][{j-1}] = {dp[i][j]}"})
                else:
                    dp[i][j] = 1 + min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])
                    steps.append({"r": i, "c": j, "value": dp[i][j],
                                   "deps": [(i - 1, j - 1), (i - 1, j), (i, j - 1)],
                                   "action": f"1 + min(replace,delete,insert) = {dp[i][j]}"})
        return steps, dp, dp[m][n]

    if algorithm == "unique_paths":
        m = max(int(input1) if str(input1).isdigit() else 3, 1)
        n = max(int(input2) if str(input2).isdigit() else 3, 1)
        dp = [[1] * n for _ in range(m)]
        for i in range(m):
            steps.append({"r": i, "c": 0, "value": 1, "deps": [],
                           "action": f"dp[{i}][0] = 1"})
        for j in range(1, n):
            steps.append({"r": 0, "c": j, "value": 1, "deps": [],
                           "action": f"dp[0][{j}] = 1"})
        for i in range(1, m):
            for j in range(1, n):
                dp[i][j] = dp[i - 1][j] + dp[i][j - 1]
                steps.append({"r": i, "c": j, "value": dp[i][j],
                               "deps": [(i - 1, j), (i, j - 1)],
                               "action": f"dp[{i}][{j}] = dp[{i-1}][{j}] + dp[{i}][{j-1}] = {dp[i][j]}"})
        return steps, dp, dp[m - 1][n - 1]

    return steps, [[0]], 0


class DP2DScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        algorithm = p.get("algorithm", "lcs")
        input1 = p.get("input1", "abcde")
        input2 = p.get("input2", "ace")
        cap = p.get("caption", "")

        titles = {
            "lcs": f"LCS - '{input1}' vs '{input2}'",
            "edit_distance": f"Edit Distance - '{input1}' -> '{input2}'",
            "unique_paths": f"Unique Paths - {input1}x{input2} grid",
        }
        title = Text(titles.get(algorithm, algorithm), font_size=26).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, algorithm, "dp_2d",
                                      custom_code=p.get("pseudocode", ""))

        if algorithm == "unique_paths":
            m = max(int(input1) if str(input1).isdigit() else 3, 1)
            n = max(int(input2) if str(input2).isdigit() else 3, 1)
            initial = [[0] * n for _ in range(m)]
        else:
            initial = [[0] * (len(input2) + 1) for _ in range(len(input1) + 1)]

        gp = GridPanel(initial, position=DOWN * 0.4)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        self.play(FadeIn(gp.vgroup))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        steps, table, answer = _dp_2d_steps(algorithm, input1, input2)
        act = action_text(steps[0]["action"]) if steps else action_text("...")
        self.play(FadeIn(act))

        for step in steps:
            r, c = step["r"], step["c"]
            # Synthesize kind from action text + deps shape
            action = step.get("action", "")
            if "match" in action or "carry" in action:
                kind = "match"
            elif not step.get("deps"):
                kind = "boundary"
            else:
                kind = "recur"
            extra = []
            hl = _hl_line(code_panel, "dp_2d", algorithm, kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(Transform(act, action_text(step["action"])), *extra, run_time=0.18)
            dep_anims = []
            for dr, dc in step.get("deps", []):
                if 0 <= dr < gp.rows and 0 <= dc < gp.cols:
                    dep_anims.append(gp.anim_set_fill(dr, dc, HILITE, 0.85))
            if dep_anims:
                self.play(*dep_anims, run_time=0.18)
            self.play(gp.anim_set_value(r, c, step["value"]),
                      gp.anim_set_fill(r, c, KEEP, 0.85),
                      run_time=0.28)
            reset = []
            for dr, dc in step.get("deps", []):
                if 0 <= dr < gp.rows and 0 <= dc < gp.cols:
                    reset.append(gp.anim_set_fill(dr, dc, DEFAULT_CELL, 0.55))
            if reset:
                self.play(*reset, run_time=0.15)

        last_r = gp.rows - 1
        last_c = gp.cols - 1
        self.play(gp.flash(last_r, last_c, color=KEEP, scale=1.3), run_time=0.4)

        rb = result_box(f"answer = {answer}", font_size=24).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.9)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  BacktrackingSubsetsScene — DFS decision tree
# ===========================================================================

def _backtracking_subsets_steps(arr: list, algorithm: str = "subsets") -> tuple:
    """Each step: {kind: 'enter'|'leaf'|'exit', path, parent_node_id, ...}."""
    steps = []
    results = []

    if algorithm == "subsets":
        # next_node_id is local; emit (parent_id, label) per spawn
        next_id = [1]   # 0 is root
        def dfs(idx, path, parent_id):
            steps.append({"kind": "leaf", "path": list(path), "node_id": parent_id,
                           "action": f"record subset {path}"})
            results.append(list(path))
            for i in range(idx, len(arr)):
                child_id = next_id[0]
                next_id[0] += 1
                steps.append({"kind": "enter", "parent_id": parent_id,
                               "child_id": child_id, "value": arr[i],
                               "path": path + [arr[i]],
                               "action": f"include arr[{i}] = {arr[i]}"})
                dfs(i + 1, path + [arr[i]], child_id)
                steps.append({"kind": "exit", "node_id": child_id,
                               "value": arr[i],
                               "action": f"backtrack: pop {arr[i]}"})
        dfs(0, [], 0)
        return steps, results

    if algorithm == "permutations":
        next_id = [1]
        def dfs(used, path, parent_id):
            if len(path) == len(arr):
                steps.append({"kind": "leaf", "path": list(path), "node_id": parent_id,
                               "action": f"record permutation {path}"})
                results.append(list(path))
                return
            for i in range(len(arr)):
                if used & (1 << i):
                    continue
                child_id = next_id[0]
                next_id[0] += 1
                steps.append({"kind": "enter", "parent_id": parent_id,
                               "child_id": child_id, "value": arr[i],
                               "path": path + [arr[i]],
                               "action": f"choose arr[{i}] = {arr[i]}"})
                dfs(used | (1 << i), path + [arr[i]], child_id)
                steps.append({"kind": "exit", "node_id": child_id,
                               "value": arr[i],
                               "action": f"backtrack: undo {arr[i]}"})
        dfs(0, [], 0)
        return steps, results

    return steps, results


class BacktrackingSubsetsScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        arr = p.get("array") or [1, 2, 3]
        algorithm = p.get("algorithm", "subsets")
        cap = p.get("caption", "")

        title_text = "Backtracking — Subsets" if algorithm == "subsets" else "Backtracking — Permutations"
        title = Text(title_text, font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, algorithm, "backtracking_subsets",
                                      custom_code=p.get("pseudocode", ""))

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)

        rt = RecursionTree(root_label="[]", position=DOWN * 0.4,
                           width=10.0, level_gap=0.85, node_radius=0.30)
        self.play(FadeIn(rt.root))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        # Current path strip on the right
        path_lbl = Text("path: []", font_size=18, color=WHITE).to_corner(UR, buff=0.5)
        self.play(FadeIn(path_lbl))

        steps, results = _backtracking_subsets_steps(arr, algorithm)
        if not steps:
            self.wait(0.5)
            return

        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        for step in steps:
            kind = step["kind"]
            extra = []
            hl = _hl_line(code_panel, "backtracking_subsets", algorithm, kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(Transform(act, action_text(step["action"])), *extra, run_time=0.2)
            if kind == "enter":
                _, anims = rt.anim_spawn_child(step["parent_id"],
                                                str(step["path"]))
                if anims:
                    self.play(*anims, run_time=0.4)
                # Update path label
                new_path = Text(f"path: {step['path']}", font_size=18,
                                 color=YELLOW).to_corner(UR, buff=0.5)
                self.play(Transform(path_lbl, new_path), run_time=0.2)
            elif kind == "leaf":
                if step["node_id"] in rt.nodes:
                    self.play(rt.nodes[step["node_id"]][0].animate.set_fill(KEEP, opacity=0.9),
                              run_time=0.25)
            elif kind == "exit":
                self.wait(0.1)

            self.wait(0.15)

        # Show result count
        rb = result_box(f"{len(results)} {algorithm}: {results[:6]}{'...' if len(results) > 6 else ''}",
                        font_size=20).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.9)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  TrieOpsScene — insert + search words
# ===========================================================================

def _trie_ops_steps(words: list, queries: list) -> tuple:
    """Insert each word, then run each query.

    Each insert step emits 'insert_char' for new edges, 'walk' for existing.
    Each query emits 'walk' or 'miss' or 'final_hit'/'final_miss'.
    """
    steps = []
    # Trie as nested dict of {char: child_dict}; '$' marks word-end
    root = {}
    for w in words:
        node = root
        for ch in w:
            kind = "walk" if ch in node else "insert_char"
            steps.append({"kind": kind, "word": w, "char": ch,
                           "action": f"insert '{w}': {kind} on '{ch}'"})
            if ch not in node:
                node[ch] = {}
            node = node[ch]
        node["$"] = True
        steps.append({"kind": "mark_end", "word": w,
                       "action": f"mark end of '{w}'"})

    results = {}
    for q in queries:
        node = root
        ok = True
        for ch in q:
            if ch not in node:
                steps.append({"kind": "miss", "query": q, "char": ch,
                               "action": f"search '{q}': '{ch}' not in trie"})
                ok = False
                break
            steps.append({"kind": "walk", "query": q, "char": ch,
                           "action": f"search '{q}': walk '{ch}'"})
            node = node[ch]
        if ok and node.get("$"):
            results[q] = True
            steps.append({"kind": "final_hit", "query": q,
                           "action": f"'{q}' is a word ✓"})
        elif ok:
            results[q] = False
            steps.append({"kind": "final_miss", "query": q,
                           "action": f"'{q}' prefix exists but no full word"})
        else:
            results[q] = False
    return steps, results


class TrieOpsScene(Scene):
    """Compact trie display: shows nodes as dots and edges as character labels.
    Path of last operation gets highlighted; tree grows over time.
    """
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        words = p.get("words") or ["cat", "car", "card", "care"]
        queries = p.get("queries") or ["car", "care", "cab"]
        cap = p.get("caption", "")

        title = Text("Trie — Insert + Search", font_size=28).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, "default", "trie_ops",
                                      custom_code=p.get("pseudocode", ""))

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        # Build the trie inline as a static layout so we can fade in nodes/edges in order
        # Internal: each node is keyed by its prefix string; root = ""
        root_circle = Circle(radius=0.22, color=WHITE, stroke_width=2,
                              fill_color=DEFAULT_CELL, fill_opacity=0.7)
        root_circle.move_to(UP * 1.6)
        root_label = Text("∅", font_size=14, color=WHITE).move_to(root_circle.get_center())
        root_g = VGroup(root_circle, root_label)
        self.play(FadeIn(root_g))

        # Discover layout: collect all unique prefixes from words, then BFS to assign positions
        prefixes = set([""])
        for w in words:
            for i in range(1, len(w) + 1):
                prefixes.add(w[:i])

        # Build a tree {parent_prefix: [child_prefixes]}
        children = {pre: [] for pre in prefixes}
        for pre in prefixes:
            if pre == "":
                continue
            parent = pre[:-1]
            if pre not in children[parent]:
                children[parent].append(pre)

        # Assign positions: BFS by depth, equally space siblings within parent's x-span
        positions = {"": (0.0, 1.6)}
        x_span = {"": (-5.0, 5.0)}
        depth = {"": 0}
        from collections import deque as _dq
        q = _dq([""])
        while q:
            pre = q.popleft()
            kids = children[pre]
            x_lo, x_hi = x_span[pre]
            for i, k in enumerate(kids):
                slot_w = (x_hi - x_lo) / max(len(kids), 1)
                kx = x_lo + slot_w * (i + 0.5)
                kd = depth[pre] + 1
                ky = 1.6 - kd * 0.85
                positions[k] = (kx, ky)
                x_span[k] = (x_lo + i * slot_w, x_lo + (i + 1) * slot_w)
                depth[k] = kd
                q.append(k)

        # Mobjects: build all nodes and edges (initially invisible)
        node_mobs = {"": root_g}
        edge_mobs = {}    # parent_prefix -> {char: Line}
        char_lbl_mobs = {}
        for pre in prefixes - {""}:
            x, y = positions[pre]
            c = Circle(radius=0.20, color=WHITE, stroke_width=2,
                       fill_color=DEFAULT_CELL, fill_opacity=0.7).move_to([x, y, 0])
            l = Text(pre[-1], font_size=14, color=WHITE).move_to(c.get_center())
            node_mobs[pre] = VGroup(c, l)
            node_mobs[pre].set_opacity(0)
            self.add(node_mobs[pre])

            parent = pre[:-1]
            px, py = positions[parent]
            edge = Line([px, py - 0.20, 0], [x, y + 0.20, 0],
                         color=GRAY, stroke_width=2).set_opacity(0)
            edge_mobs[pre] = edge
            self.add(edge)

        steps, results = _trie_ops_steps(words, queries)
        if not steps:
            self.wait(0.5)
            return

        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        # Track current cursor (start of word being inserted/searched)
        current_prefix = ""
        cursor = Circle(radius=0.30, color=YELLOW, stroke_width=3,
                         fill_opacity=0).move_to(node_mobs[""].get_center())
        self.play(FadeIn(cursor))

        for step in steps:
            kind = step["kind"]
            extra = []
            hl = _hl_line(code_panel, "trie_ops", "default", kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(Transform(act, action_text(step["action"])), *extra, run_time=0.18)

            if kind in ("insert_char", "walk", "miss"):
                # Walk to next prefix (current_prefix + char)
                if kind == "miss":
                    # Don't move cursor; flash red
                    self.play(cursor.animate.set_color(REJECT), run_time=0.2)
                    self.wait(0.2)
                    self.play(cursor.animate.set_color(YELLOW), run_time=0.15)
                    continue
                if "char" in step:
                    next_pref = current_prefix + step["char"]
                    if next_pref in node_mobs:
                        if kind == "insert_char":
                            # Reveal the new node + edge
                            node_mobs[next_pref].set_opacity(1)
                            edge_mobs[next_pref].set_opacity(1)
                            self.play(FadeIn(node_mobs[next_pref]),
                                      Create(edge_mobs[next_pref]),
                                      run_time=0.3)
                        # Move cursor along
                        self.play(cursor.animate.move_to(node_mobs[next_pref].get_center()),
                                  run_time=0.25, rate_func=smooth)
                        current_prefix = next_pref
            elif kind == "mark_end":
                # Reset cursor to root for next word
                self.play(node_mobs[step["word"]][0].animate.set_fill(KEEP, opacity=0.85),
                          run_time=0.25)
                current_prefix = ""
                self.play(cursor.animate.move_to(node_mobs[""].get_center()),
                          run_time=0.25)
            elif kind == "final_hit":
                self.play(cursor.animate.set_color(KEEP), run_time=0.25)
                current_prefix = ""
                self.play(cursor.animate.move_to(node_mobs[""].get_center()),
                          run_time=0.3)
                self.play(cursor.animate.set_color(YELLOW), run_time=0.15)
            elif kind == "final_miss":
                self.play(cursor.animate.set_color(REJECT), run_time=0.25)
                self.wait(0.3)
                current_prefix = ""
                self.play(cursor.animate.move_to(node_mobs[""].get_center()),
                          run_time=0.3)
                self.play(cursor.animate.set_color(YELLOW), run_time=0.15)
            self.wait(0.15)

        rb_text = ", ".join(f"{q}={'✓' if v else '✗'}" for q, v in results.items())
        rb = result_box(rb_text or "no queries", font_size=22).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(1.0)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  DijkstraScene — shortest paths with priority-queue
# ===========================================================================

def _dijkstra_steps(num_nodes: int, edges: list, source: int) -> tuple:
    """Each edge: [u, v, w]. Undirected graph."""
    import heapq
    INF = float('inf')
    adj = {i: [] for i in range(num_nodes)}
    for e in edges:
        u, v, w = e[0], e[1], (e[2] if len(e) > 2 else 1)
        adj[u].append((v, w))
        adj[v].append((u, w))

    dist = [INF] * num_nodes
    dist[source] = 0
    visited = [False] * num_nodes
    steps = [{"kind": "init", "source": source,
               "action": f"start at node {source}, dist[{source}]=0"}]

    pq = [(0, source)]
    while pq:
        d, u = heapq.heappop(pq)
        if visited[u]:
            continue
        visited[u] = True
        steps.append({"kind": "settle", "node": u, "dist": d,
                       "action": f"settle node {u} with dist={d}"})
        for v, w in adj[u]:
            if visited[v]:
                continue
            nd = d + w
            if nd < dist[v]:
                old = dist[v]
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
                steps.append({"kind": "relax", "u": u, "v": v, "old": old, "new": nd,
                               "action": f"relax edge {u}->{v}: {old if old != INF else '∞'} -> {nd}"})
    return steps, dist


class DijkstraScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        num_nodes = int(p.get("num_nodes", 5))
        edges = p.get("edges", [[0, 1, 4], [0, 2, 1], [2, 1, 2],
                                  [1, 3, 1], [2, 3, 5], [3, 4, 3]])
        source = int(p.get("source", 0))
        cap = p.get("caption", "")

        title = Text(f"Dijkstra — shortest paths from {source}", font_size=26).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, "default", "dijkstra",
                                      custom_code=p.get("pseudocode", ""))

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)

        gp = GraphPanel(num_nodes, edges, position=ORIGIN + DOWN * 0.2,
                         radius=2.0, node_radius=0.30)
        self.play(FadeIn(gp.vgroup))
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        dist_panel = HashMapPanel(anchor=UR, title="dist[]")
        self.play(FadeIn(dist_panel.vgroup))

        # Initialize all distances as ∞ except source = 0
        for i in range(num_nodes):
            self.play(*dist_panel.anim_set(str(i), "∞" if i != source else "0"),
                      run_time=0.12)

        steps, dist = _dijkstra_steps(num_nodes, edges, source)
        if not steps:
            self.wait(0.5)
            return

        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))
        self.play(gp.anim_set_node_color(source, KEEP, 0.85), run_time=0.3)

        for step in steps[1:]:
            kind = step["kind"]
            extra = []
            hl = _hl_line(code_panel, "dijkstra", "default", kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(Transform(act, action_text(step["action"])), *extra, run_time=0.2)
            if kind == "settle":
                u = step["node"]
                self.play(gp.anim_set_node_color(u, KEEP, 0.95), run_time=0.3)
                self.play(Indicate(gp.nodes[u][0], color=KEEP), run_time=0.3)
            elif kind == "relax":
                u, v, new = step["u"], step["v"], step["new"]
                anim = gp.anim_flash_edge(u, v, color=YELLOW)
                if anim is not None:
                    self.play(anim, run_time=0.3)
                self.play(*dist_panel.anim_set(str(v), new), run_time=0.3)
                self.play(gp.anim_set_node_color(v, HILITE, 0.7), run_time=0.2)
            self.wait(0.15)

        rb_text = " ".join(f"{i}:{('∞' if d == float('inf') else d)}" for i, d in enumerate(dist))
        rb = result_box(rb_text, font_size=22).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.9)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  SegmentTreeScene — range queries
# ===========================================================================

def _segment_tree_steps(arr: list, queries: list) -> tuple:
    """Build a sum-segment-tree over arr, then run range-sum queries."""
    n = len(arr)
    size = 1
    while size < n:
        size *= 2
    tree = [0] * (2 * size)
    for i, v in enumerate(arr):
        tree[size + i] = v
    steps = []
    for i in range(size - 1, 0, -1):
        tree[i] = tree[2 * i] + tree[2 * i + 1]
        steps.append({"kind": "build", "node": i, "value": tree[i],
                       "action": f"tree[{i}] = tree[{2*i}] + tree[{2*i+1}] = {tree[i]}"})

    def query(l, r):
        l += size; r += size + 1
        result = 0
        path = []
        while l < r:
            if l & 1:
                path.append(l); result += tree[l]; l += 1
            if r & 1:
                r -= 1; path.append(r); result += tree[r]
            l //= 2; r //= 2
        return result, path

    results = []
    for ql in queries:
        l, r = ql[0], ql[1]
        res, path = query(l, r)
        results.append(res)
        steps.append({"kind": "query", "l": l, "r": r, "result": res,
                       "path": path,
                       "action": f"sum({l}..{r}) = {res}  (visit nodes {path})"})
    return steps, results, size, tree


class SegmentTreeScene(Scene):
    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        arr = p.get("array") or [1, 3, 5, 7, 9, 11]
        queries = p.get("queries", [[1, 3], [0, 5], [2, 4]])
        cap = p.get("caption", "")

        title = Text(f"Segment Tree — range sum queries", font_size=26).to_edge(UP, buff=0.3)
        code_panel, badge_v = _polish(self, title, "default", "segment_tree",
                                      custom_code=p.get("pseudocode", ""))

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)

        self.play(Write(title))
        if badge_v is not None:
            self.play(FadeIn(badge_v), run_time=0.25)
        if code_panel is not None:
            self.play(FadeIn(code_panel.vgroup), run_time=0.3)
            self.play(code_panel.anim_dim_all(), run_time=0.2)

        steps, results, size, tree = _segment_tree_steps(arr, queries)

        # The tree array we display has values in indices 1..2*size-1
        # We'll show only the "useful" range: 1 to size + n - 1
        useful = 2 * size
        # Render tree using BinaryTreePanel — index 0 unused, so prepend 0
        # BinaryTreePanel uses 0-indexed children (i -> 2i+1, 2i+2). We need (i -> 2i, 2i+1).
        # Workaround: treat node 1 as our "root", display values shifted.
        display_vals = [tree[i] if i < len(tree) else 0 for i in range(1, useful)]
        # Pad to a complete tree if needed
        bt = BinaryTreePanel(display_vals, position=DOWN * 0.4 + UP * 0.3,
                              node_radius=0.26, level_gap=0.8)
        # But this primitive uses 2i+1, 2i+2 — different from segment tree's 2i, 2i+1.
        # Simpler: show the input array at the bottom and the tree values as text labels.

        # Show input array
        in_strip = ArrayStrip(arr, position=DOWN * 2.3)
        self.play(FadeIn(in_strip.vgroup), Write(in_strip.indices))

        self.play(FadeIn(bt.vgroup))

        if not steps:
            self.wait(0.5)
            return

        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        for step in steps:
            kind = step["kind"]
            extra = []
            hl = _hl_line(code_panel, "segment_tree", "default", kind,
                          step_lines_override=p.get("step_lines"))
            if hl is not None:
                extra.append(hl)
            self.play(Transform(act, action_text(step["action"])), *extra, run_time=0.2)
            if kind == "build":
                n_idx = step["node"] - 1   # display offset
                if 0 <= n_idx < len(bt.nodes):
                    self.play(bt.anim_set_value(n_idx, step["value"]),
                              bt.anim_set_fill(n_idx, KEEP, 0.85), run_time=0.25)
                    self.play(bt.flash(n_idx, color=KEEP), run_time=0.2)
                    self.play(bt.anim_set_fill(n_idx, DEFAULT_CELL, 0.7), run_time=0.15)
            elif kind == "query":
                anims = []
                for n in step["path"]:
                    n_idx = n - 1
                    if 0 <= n_idx < len(bt.nodes):
                        anims.append(bt.anim_set_fill(n_idx, HILITE, 0.85))
                if anims:
                    self.play(*anims, run_time=0.4)
                # Also highlight input range
                for k in range(step["l"], step["r"] + 1):
                    if 0 <= k < len(in_strip.cells):
                        in_strip.cells[k][0].set_fill(KEEP, opacity=0.7)
                self.wait(0.4)
                # Reset
                reset = []
                for n in step["path"]:
                    n_idx = n - 1
                    if 0 <= n_idx < len(bt.nodes):
                        reset.append(bt.anim_set_fill(n_idx, DEFAULT_CELL, 0.7))
                for k in range(step["l"], step["r"] + 1):
                    if 0 <= k < len(in_strip.cells):
                        in_strip.cells[k][0].set_fill(DEFAULT_CELL, opacity=0.55)
                if reset:
                    self.play(*reset, run_time=0.2)

        rb = result_box(f"results: {results}", font_size=22).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.9)


# ===========================================================================
#  Phase 7B Scene 1 — FloydCycleScene
# ===========================================================================
#
#  Floyd's tortoise & hare cycle detection on a linked list.
#  The slow pointer advances by 1 per step, fast by 2. If they meet →
#  cycle detected. If fast reaches null → no cycle.
# ---------------------------------------------------------------------------

def _floyd_cycle_steps(values: list, cycle_at) -> tuple:
    """
    Returns (steps: list[dict], has_cycle: bool).

    `cycle_at` is the index where the tail loops back to (None for no cycle).
    Each step: {kind: 'init'|'move'|'meet'|'no_cycle', slow: int|None,
                fast: int|None, action: str}
    """
    n = len(values)
    if n == 0:
        return [], False

    def nxt(i):
        if i is None:
            return None
        if i + 1 < n:
            return i + 1
        return cycle_at  # may be None for "tail → null"

    steps = [{"kind": "init", "slow": 0, "fast": 0,
              "action": "slow = fast = head (index 0)"}]

    slow, fast = 0, 0
    safety = 0
    while True:
        safety += 1
        if safety > 200:  # bound — should never trigger for valid inputs
            return steps, False

        new_slow = nxt(slow)
        f1 = nxt(fast)
        new_fast = nxt(f1) if f1 is not None else None

        # Walk the fast pointer two hops; if either hop hits null, no cycle.
        if f1 is None or new_fast is None:
            steps.append({"kind": "no_cycle", "slow": new_slow, "fast": None,
                          "action": "fast reached null → no cycle"})
            return steps, False

        slow, fast = new_slow, new_fast
        steps.append({"kind": "move", "slow": slow, "fast": fast,
                      "action": f"slow→{slow}, fast→{fast}"})

        if slow == fast:
            steps.append({"kind": "meet", "slow": slow, "fast": fast,
                          "action": f"slow == fast at index {slow} → cycle"})
            return steps, True


_FLOYD_PSEUDOCODE = """
slow = fast = head
while fast and fast.next:
    slow = slow.next
    fast = fast.next.next
    if slow == fast: return True
return False
""".strip()


class FloydCycleScene(Scene):
    """Floyd's tortoise-and-hare cycle detection.

    Schema: {values: List[int], cycle_at: int|null, caption: str}
    """

    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        values    = p.get("values") or [1, 2, 3, 4, 5]
        cycle_at  = p.get("cycle_at", 1)   # default: cycle back to index 1
        cap       = p.get("caption",  "")

        title = Text("Floyd's Cycle Detection", font_size=28).to_edge(UP, buff=0.3)
        badge = ComplexityBadge(time="O(n)", space="O(1)", font_size=14)
        if title.width > 6.0:
            badge.vgroup.next_to(title, DOWN, buff=0.15)
        else:
            badge.vgroup.next_to(title, RIGHT, buff=0.3)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)
        self.play(Write(title), FadeIn(badge.vgroup))

        # Build the chain horizontally
        n = len(values)
        spacing = min(1.6, 9.5 / max(n, 1))
        start_x = -(n - 1) * spacing / 2
        nodes = []
        for i, v in enumerate(values):
            cx = start_x + i * spacing
            circle = Circle(radius=0.32, color=WHITE, fill_color="#1f2937",
                            fill_opacity=0.9, stroke_width=2)
            label  = Text(str(v), font_size=18, color=WHITE)
            node   = VGroup(circle, label).move_to(np.array([cx, 0.4, 0]))
            nodes.append(node)

        arrows = []
        for i in range(n - 1):
            arr = Arrow(nodes[i].get_right(), nodes[i + 1].get_left(),
                        buff=0.05, color=GRAY, stroke_width=2,
                        max_tip_length_to_length_ratio=0.25)
            arrows.append(arr)

        # null label and tail arrow OR cycle-back arc
        cycle_arc = None
        null_lbl, null_arr = None, None
        if cycle_at is None:
            null_lbl = Text("null", font_size=14, color=GRAY).next_to(nodes[-1], RIGHT, buff=0.3)
            null_arr = Arrow(nodes[-1].get_right(), null_lbl.get_left(),
                             buff=0.05, color=GRAY, stroke_width=2,
                             max_tip_length_to_length_ratio=0.2)
        else:
            # Curved arc from tail back up over the chain to nodes[cycle_at]
            cycle_arc = CurvedArrow(
                start_point=nodes[-1].get_top() + UP * 0.05,
                end_point=nodes[cycle_at].get_top() + UP * 0.05,
                color="#f59e0b", stroke_width=2.5, angle=-PI * 0.65,
                tip_length=0.18,
            )

        # Code panel (UL) and state panel (UR) — prefer user-specific
        # pseudocode from /api/parse-leetcode if present
        _custom = (p.get("pseudocode") or "").strip()
        code_panel = CodePanel(_custom or _FLOYD_PSEUDOCODE, anchor=UL,
                               font_size=14, max_width=3.8)
        code_panel.is_custom = bool(_custom)
        state = StatePanel(anchor=UR, title="State")

        chain_grp = VGroup(*nodes, *arrows)
        if null_lbl is not None:
            chain_grp.add(null_lbl, null_arr)
        if cycle_arc is not None:
            chain_grp.add(cycle_arc)

        self.play(FadeIn(chain_grp), FadeIn(code_panel.vgroup), FadeIn(state.vgroup))
        self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.play(code_panel.anim_highlight(0), run_time=0.25)

        # Pointer arrows (small triangles below the active node)
        slow_lbl = Text("slow", font_size=14, color=PTR_COLORS["slow"], weight=BOLD)
        fast_lbl = Text("fast", font_size=14, color=PTR_COLORS["fast"], weight=BOLD)
        slow_arrow = Triangle(color=PTR_COLORS["slow"], fill_opacity=1.0).scale(0.16).rotate(PI)
        fast_arrow = Triangle(color=PTR_COLORS["fast"], fill_opacity=1.0).scale(0.16).rotate(PI)
        slow_grp = VGroup(slow_arrow, slow_lbl).arrange(DOWN, buff=0.05)
        fast_grp = VGroup(fast_arrow, fast_lbl).arrange(DOWN, buff=0.05)

        def _place(grp, idx, extra=0.0):
            grp.next_to(nodes[idx], DOWN, buff=0.18 + extra)

        _place(slow_grp, 0)
        _place(fast_grp, 0, extra=0.5)   # offset fast below slow when at same node
        self.play(FadeIn(slow_grp), FadeIn(fast_grp))

        self.play(*state.anim_set("slow", 0, color=PTR_COLORS["slow"]),
                  *state.anim_set("fast", 0, color=PTR_COLORS["fast"]),
                  run_time=0.3)

        steps, has_cycle = _floyd_cycle_steps(values, cycle_at)
        if not steps:
            return
        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        for step in steps[1:]:   # skip init (already shown)
            kind = step["kind"]

            if kind == "no_cycle":
                self.play(code_panel.anim_highlight(1), run_time=0.3)  # while-cond fails
                self.play(FadeOut(fast_grp), run_time=0.3)
                self.play(Transform(act, action_text(step["action"])), run_time=0.25)
                break

            slow_i, fast_i = step["slow"], step["fast"]
            # line 2: slow = slow.next  (highlight then move)
            self.play(code_panel.anim_highlight(2), run_time=0.2)
            new_slow_grp = slow_grp.copy()
            _place(new_slow_grp, slow_i)
            move_slow = Transform(slow_grp, new_slow_grp)

            # line 3: fast = fast.next.next
            self.play(move_slow, run_time=0.4, rate_func=smooth)
            self.play(code_panel.anim_highlight(3), run_time=0.2)
            new_fast_grp = fast_grp.copy()
            _place(new_fast_grp, fast_i,
                   extra=0.5 if slow_i == fast_i else 0.0)
            self.play(Transform(fast_grp, new_fast_grp), run_time=0.45, rate_func=smooth)

            self.play(*state.anim_set("slow", slow_i, color=PTR_COLORS["slow"]),
                      *state.anim_set("fast", fast_i, color=PTR_COLORS["fast"]),
                      run_time=0.25)

            self.play(Transform(act, action_text(step["action"])), run_time=0.25)

            if kind == "meet":
                # line 4: if slow == fast: return True
                self.play(code_panel.anim_highlight(4), run_time=0.2)
                self.play(
                    Indicate(nodes[slow_i][0], color=KEEP, scale_factor=1.4),
                    Indicate(slow_grp, color=KEEP, scale_factor=1.3),
                    Indicate(fast_grp, color=KEEP, scale_factor=1.3),
                    run_time=0.6,
                )
                # Highlight cycle arc green
                if cycle_arc is not None:
                    self.play(cycle_arc.animate.set_color(KEEP), run_time=0.3)
                break

            self.wait(0.15)

        # Result + brute force comparison
        if has_cycle:
            result_text = f"Cycle detected at index {steps[-1]['slow']}"
            cmp = BruteForceComparison(
                brute=("Hashset of seen nodes", "O(n) space"),
                optimal=("Tortoise & hare", "O(1) space"),
            )
        else:
            self.play(code_panel.anim_highlight(5), run_time=0.25)  # return False
            result_text = "No cycle (fast reached null)"
            cmp = BruteForceComparison(
                brute=("Mark each node visited", "O(n) extra space"),
                optimal=("Tortoise & hare", "O(1) extra space"),
            )

        rb = result_box(result_text, font_size=22).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP if has_cycle else REJECT)
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.3)
        self.play(FadeIn(cmp.vgroup), run_time=0.4)
        self.wait(1.0)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  Phase 7B Scene 7 — RecursionTreeDCScene
# ===========================================================================
#
#  Divide-and-conquer recursion tree for merge_sort. The tree builds
#  top-down in BFS order during the SPLIT phase, then collapses
#  bottom-up during the MERGE phase. Each leaf is a single element
#  (already sorted); merges combine two sorted children into one.
# ---------------------------------------------------------------------------

def _merge_sort_steps(arr: list) -> tuple:
    """Returns (steps, sorted_arr, nodes_meta).

    nodes_meta[i] = (parent_index, slice_list, l, r)
    Step kinds: 'split' (spawn child node), 'merge' (combine two children
                into parent's sorted result), 'done'
    """
    if not arr:
        return [], [], []

    nodes = [(None, list(arr), 0, len(arr) - 1)]
    children_of = {0: []}

    # BFS to build the full tree
    queue = [0]
    while queue:
        cur = queue.pop(0)
        _, _, l, r = nodes[cur]
        if l >= r:
            continue
        m = (l + r) // 2
        left_idx  = len(nodes)
        right_idx = left_idx + 1
        nodes.append((cur, list(arr[l:m + 1]),    l, m))
        nodes.append((cur, list(arr[m + 1:r + 1]), m + 1, r))
        children_of[cur].extend([left_idx, right_idx])
        children_of[left_idx]  = []
        children_of[right_idx] = []
        queue.append(left_idx)
        queue.append(right_idx)

    steps = []
    # Split phase in BFS order (skip root which already exists)
    for idx in range(1, len(nodes)):
        parent_idx, slc, _, _ = nodes[idx]
        steps.append({"kind": "split", "node_idx": idx,
                      "parent_idx": parent_idx, "label": str(slc),
                      "action": f"split → {slc}"})

    # Merge phase in reverse-BFS order (leaves first, then up)
    sorted_at = {}
    for idx in range(len(nodes) - 1, -1, -1):
        _, _, l, r = nodes[idx]
        if l == r:
            sorted_at[idx] = [arr[l]]
        else:
            kids = children_of[idx]
            left_sorted  = sorted_at[kids[0]]
            right_sorted = sorted_at[kids[1]]
            merged = []
            i = j = 0
            while i < len(left_sorted) and j < len(right_sorted):
                if left_sorted[i] <= right_sorted[j]:
                    merged.append(left_sorted[i]); i += 1
                else:
                    merged.append(right_sorted[j]); j += 1
            merged.extend(left_sorted[i:])
            merged.extend(right_sorted[j:])
            sorted_at[idx] = merged
            steps.append({"kind": "merge", "node_idx": idx,
                          "label": str(merged),
                          "action": f"merge → {merged}"})

    steps.append({"kind": "done", "label": str(sorted_at[0]),
                  "action": f"sorted = {sorted_at[0]}"})
    return steps, sorted_at[0], nodes


_MERGE_SORT_PSEUDOCODE = """
def merge_sort(a):
    if len(a) <= 1: return a
    m = len(a) // 2
    left  = merge_sort(a[:m])
    right = merge_sort(a[m:])
    return merge(left, right)
""".strip()


class RecursionTreeDCScene(Scene):
    """Divide-and-conquer recursion tree (merge_sort).

    Schema: {array: List[int], algorithm: "merge_sort", caption: str}
    """

    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        array = p.get("array") or [3, 1, 4, 1, 5]
        cap   = p.get("caption", "")

        title = Text("Merge Sort — Recursion Tree",
                     font_size=28).to_edge(UP, buff=0.3)
        badge = ComplexityBadge(time="O(n log n)", space="O(n)", font_size=14)
        if title.width > 6.0:
            badge.vgroup.next_to(title, DOWN, buff=0.15)
        else:
            badge.vgroup.next_to(title, RIGHT, buff=0.3)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)
        self.play(Write(title), FadeIn(badge.vgroup))

        # Input array shown above the recursion tree
        in_strip = ArrayStrip(array, position=UP * 2.4)
        # Recursion tree centered, taking most of the lower screen
        rt = RecursionTree(root_label=str(array),
                           position=DOWN * 0.4,
                           width=8.5, level_gap=0.85, node_radius=0.34)

        _custom = (p.get("pseudocode") or "").strip()
        code_panel = CodePanel(_custom or _MERGE_SORT_PSEUDOCODE, anchor=UL,
                               font_size=12, max_width=4.0)
        code_panel.is_custom = bool(_custom)

        self.play(FadeIn(in_strip.vgroup), Write(in_strip.indices),
                  FadeIn(rt.vgroup), FadeIn(code_panel.vgroup))
        self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.play(code_panel.anim_highlight(0), run_time=0.2)

        steps, sorted_arr, nodes_meta = _merge_sort_steps(array)
        if not steps:
            return
        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        # Map nodes_meta index → tree node id (root is 0; children get IDs as spawned)
        meta_to_tree = {0: 0}

        for step in steps:
            kind = step["kind"]

            if kind == "split":
                self.play(code_panel.anim_highlight(3), run_time=0.15)
                parent_meta = step["parent_idx"]
                parent_tree = meta_to_tree[parent_meta]
                new_id, anims = rt.anim_spawn_child(parent_tree, step["label"])
                meta_to_tree[step["node_idx"]] = new_id
                if anims:
                    self.play(*anims, run_time=0.45, rate_func=smooth)

                # Mark single-element nodes (leaves) green = sorted base case
                meta_idx = step["node_idx"]
                _, slc, l, r = nodes_meta[meta_idx]
                if l == r:
                    leaf_node = rt.nodes[new_id]
                    self.play(leaf_node[0].animate.set_fill(KEEP, opacity=0.85),
                              run_time=0.2)

            elif kind == "merge":
                self.play(code_panel.anim_highlight(5), run_time=0.15)
                meta_idx = step["node_idx"]
                tree_id  = meta_to_tree[meta_idx]
                node = rt.nodes[tree_id]

                # Update the node's label to the sorted slice
                font = max(13, int(18 * (rt.node_radius / 0.30)))
                new_label = Text(step["label"], font_size=font, color=WHITE)
                if new_label.width > 2 * rt.node_radius - 0.05:
                    new_label.scale((2 * rt.node_radius - 0.05) / max(new_label.width, 0.001))
                new_label.move_to(node[1].get_center())

                # Flash both children green to show they're being merged
                child_anims = []
                for cid in [c for (p, c) in rt.edges if p == tree_id]:
                    child_anims.append(Indicate(rt.nodes[cid], color=KEEP,
                                                scale_factor=1.15))
                if child_anims:
                    self.play(*child_anims, run_time=0.35)
                self.play(Transform(node[1], new_label),
                          node[0].animate.set_fill(KEEP, opacity=0.7),
                          run_time=0.4)

            elif kind == "done":
                # Final result: highlight all root cells in green
                self.play(rt.nodes[0][0].animate.set_fill(KEEP, opacity=0.9),
                          Indicate(rt.nodes[0], color=KEEP, scale_factor=1.25),
                          run_time=0.45)
                rb = result_box(f"sorted = {sorted_arr}",
                                font_size=22).to_edge(DOWN, buff=1.75)
                if rb.width > 13:
                    rb.scale(13 / rb.width)
                rb[1].set_color(KEEP)
                cmp = BruteForceComparison(
                    brute=("Bubble / insertion sort", "O(n²)"),
                    optimal=("Divide & conquer + merge", "O(n log n)"),
                )
                self.play(FadeOut(act), FadeIn(rb))
                self.wait(0.3)
                self.play(FadeIn(cmp.vgroup), run_time=0.4)
                break

            self.play(Transform(act, action_text(step["action"])), run_time=0.2)
            self.wait(0.1)

        self.wait(0.6)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  Phase 7B Scene 6 — MatrixRotationScene
# ===========================================================================
#
#  rotate_90 : transpose then reverse each row
#  spiral    : trace the spiral path from outside in
# ---------------------------------------------------------------------------

def _matrix_rotate_90_steps(matrix: list) -> tuple:
    """Returns (steps, rotated_matrix). Each step is one swap during the
    transpose phase or one row-reversal during the reverse phase.

    Step kinds: 'phase'|'swap'|'reverse_row'|'done'.
    """
    n = len(matrix)
    if n == 0:
        return [], []
    # Work on a copy
    m = [row[:] for row in matrix]

    steps = [{"kind": "phase", "phase": "transpose",
              "matrix": [r[:] for r in m],
              "action": "Phase 1: transpose"}]

    for i in range(n):
        for j in range(i + 1, len(m[0])):
            m[i][j], m[j][i] = m[j][i], m[i][j]
            steps.append({"kind": "swap", "i": i, "j": j,
                          "matrix": [r[:] for r in m],
                          "action": f"swap ({i},{j}) ↔ ({j},{i})"})

    steps.append({"kind": "phase", "phase": "reverse",
                  "matrix": [r[:] for r in m],
                  "action": "Phase 2: reverse each row"})

    for r in range(n):
        m[r] = m[r][::-1]
        steps.append({"kind": "reverse_row", "row": r,
                      "matrix": [row[:] for row in m],
                      "action": f"reverse row {r}"})

    steps.append({"kind": "done", "matrix": [r[:] for r in m],
                  "action": "rotated 90°"})
    return steps, m


def _matrix_spiral_steps(matrix: list) -> tuple:
    """Returns (steps, order). order is the sequence of values visited.

    Each step is one cell-visit during spiral traversal.
    """
    if not matrix or not matrix[0]:
        return [], []
    rows, cols = len(matrix), len(matrix[0])
    visited = [[False] * cols for _ in range(rows)]
    dr = [0, 1, 0, -1]
    dc = [1, 0, -1, 0]
    r = c = d = 0
    order = []
    steps = []
    for _ in range(rows * cols):
        visited[r][c] = True
        order.append(matrix[r][c])
        steps.append({"kind": "visit", "r": r, "c": c,
                      "value": matrix[r][c], "order": order[:],
                      "action": f"visit ({r},{c}) = {matrix[r][c]}"})
        nr, nc = r + dr[d], c + dc[d]
        if not (0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc]):
            d = (d + 1) % 4
            nr, nc = r + dr[d], c + dc[d]
        r, c = nr, nc
    steps.append({"kind": "done", "order": order[:],
                  "action": f"order = {order}"})
    return steps, order


_ROTATE_PSEUDOCODE = """
# Phase 1: transpose
for i in range(n):
    for j in range(i+1, n):
        a[i][j], a[j][i] = a[j][i], a[i][j]
# Phase 2: reverse rows
for r in range(n):
    a[r] = a[r][::-1]
""".strip()


_SPIRAL_PSEUDOCODE = """
dr = [0, 1, 0, -1]; dc = [1, 0, -1, 0]
r = c = d = 0
for _ in range(rows*cols):
    visit(a[r][c]); visited[r][c] = True
    nr, nc = r+dr[d], c+dc[d]
    if out_of_bounds or visited[nr][nc]:
        d = (d+1) % 4
    r, c = r+dr[d], c+dc[d]
""".strip()


class MatrixRotationScene(Scene):
    """rotate_90 / spiral on a 2D matrix.

    Schema: {matrix: List[List[int]], operation: "rotate_90"|"spiral", caption}
    """

    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        matrix    = p.get("matrix",   [[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        operation = p.get("operation", "rotate_90")
        cap       = p.get("caption",   "")

        title_map = {"rotate_90": "Rotate Matrix 90°",
                     "spiral":    "Spiral Matrix Traversal"}
        title = Text(title_map.get(operation, operation),
                     font_size=28).to_edge(UP, buff=0.3)
        badge = ComplexityBadge(time="O(n²)", space="O(1)", font_size=14)
        if title.width > 6.0:
            badge.vgroup.next_to(title, DOWN, buff=0.15)
        else:
            badge.vgroup.next_to(title, RIGHT, buff=0.3)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)
        self.play(Write(title), FadeIn(badge.vgroup))

        custom_code = (p.get("pseudocode") or "").strip()
        if operation == "rotate_90":
            self._run_rotate(matrix, custom_code)
        else:
            self._run_spiral(matrix, custom_code)

        self.wait(0.4)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)

    # ─── rotate_90 ──────────────────────────────────────────────────────────

    def _run_rotate(self, matrix, custom_code=""):
        grid = GridPanel(matrix, position=RIGHT * 0.5)
        code_panel = CodePanel(custom_code or _ROTATE_PSEUDOCODE, anchor=UL,
                               font_size=14, max_width=4.0)
        code_panel.is_custom = bool(custom_code)

        self.play(FadeIn(grid.vgroup), Write(grid.row_idx), Write(grid.col_idx),
                  FadeIn(code_panel.vgroup))
        self.play(code_panel.anim_dim_all(), run_time=0.2)

        steps, _ = _matrix_rotate_90_steps(matrix)
        if not steps:
            return
        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        for step in steps[1:]:
            kind = step["kind"]
            if kind == "phase":
                line_idx = 1 if step["phase"] == "transpose" else 6
                self.play(code_panel.anim_highlight(line_idx), run_time=0.25)
                self.play(Transform(act, action_text(step["action"])),
                          run_time=0.25)

            elif kind == "swap":
                i, j = step["i"], step["j"]
                self.play(code_panel.anim_highlight(3), run_time=0.15)
                # Highlight both cells
                self.play(grid.flash(i, j, color=YELLOW, scale=1.2),
                          grid.flash(j, i, color=YELLOW, scale=1.2),
                          run_time=0.3)
                # Update values to reflect swap
                self.play(grid.anim_set_value(i, j, step["matrix"][i][j]),
                          grid.anim_set_value(j, i, step["matrix"][j][i]),
                          grid.anim_set_fill(i, j, KEEP, 0.6),
                          grid.anim_set_fill(j, i, KEEP, 0.6),
                          run_time=0.4)
                self.play(Transform(act, action_text(step["action"])),
                          run_time=0.2)

            elif kind == "reverse_row":
                r = step["row"]
                self.play(code_panel.anim_highlight(7), run_time=0.15)
                # Flash whole row
                cols = len(step["matrix"][0])
                self.play(*[grid.flash(r, c, color=HILITE, scale=1.1)
                            for c in range(cols)],
                          run_time=0.35)
                # Update each cell to new (reversed) values
                self.play(*[grid.anim_set_value(r, c, step["matrix"][r][c])
                            for c in range(cols)],
                          run_time=0.4)
                self.play(Transform(act, action_text(step["action"])),
                          run_time=0.2)

            elif kind == "done":
                # Final green highlight everywhere
                rows = len(step["matrix"])
                cols = len(step["matrix"][0])
                self.play(*[grid.anim_set_fill(r, c, KEEP, 0.7)
                            for r in range(rows) for c in range(cols)],
                          run_time=0.45)
                rb = result_box("Rotation complete", font_size=24).to_edge(DOWN, buff=1.75)
                rb[1].set_color(KEEP)
                cmp = BruteForceComparison(
                    brute=("Allocate new n×n matrix", "O(n²) extra space"),
                    optimal=("In-place transpose + reverse", "O(1) extra space"),
                )
                self.play(FadeOut(act), FadeIn(rb))
                self.wait(0.3)
                self.play(FadeIn(cmp.vgroup), run_time=0.4)
                return

            self.wait(0.1)

    # ─── spiral ─────────────────────────────────────────────────────────────

    def _run_spiral(self, matrix, custom_code=""):
        grid = GridPanel(matrix, position=LEFT * 1.0)
        code_panel = CodePanel(custom_code or _SPIRAL_PSEUDOCODE, anchor=UR,
                               font_size=14, max_width=4.5)
        code_panel.is_custom = bool(custom_code)
        # Order display below
        order_lbl = Text("order: [ ]", font_size=18, color=KEEP).to_edge(DOWN, buff=2.6)

        self.play(FadeIn(grid.vgroup), Write(grid.row_idx), Write(grid.col_idx),
                  FadeIn(code_panel.vgroup), FadeIn(order_lbl))
        self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.play(code_panel.anim_highlight(0), run_time=0.25)

        steps, order = _matrix_spiral_steps(matrix)
        if not steps:
            return
        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        for step in steps:
            if step["kind"] == "done":
                break
            r, c = step["r"], step["c"]
            self.play(code_panel.anim_highlight(3), run_time=0.15)
            self.play(grid.flash(r, c, color=HILITE, scale=1.25),
                      grid.anim_set_fill(r, c, KEEP, 0.7),
                      run_time=0.3, rate_func=smooth)
            new_order_lbl = Text(f"order: {step['order']}",
                                 font_size=16, color=KEEP).to_edge(DOWN, buff=2.6)
            if new_order_lbl.width > 12:
                new_order_lbl.scale(12 / new_order_lbl.width)
            self.play(Transform(order_lbl, new_order_lbl),
                      Transform(act, action_text(step["action"])),
                      run_time=0.25)
            self.wait(0.1)

        rb = result_box(f"order = {order}", font_size=20).to_edge(DOWN, buff=1.75)
        if rb.width > 13:
            rb.scale(13 / rb.width)
        rb[1].set_color(KEEP)
        cmp = BruteForceComparison(
            brute=("Track 4 boundaries explicitly", "O(rc), longer code"),
            optimal=("Direction vector + turn-on-blocked", "O(rc), 6 lines"),
        )
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.3)
        self.play(FadeIn(cmp.vgroup), run_time=0.4)


# ===========================================================================
#  Phase 7B Scene 5 — TopologicalSortScene (Kahn's algorithm)
# ===========================================================================
#
#  Compute in_degree[] for every node, enqueue nodes with in_degree 0,
#  pop one at a time and decrement neighbors. Result is a valid topo order.
# ---------------------------------------------------------------------------

def _topological_sort_steps(num_nodes: int, edges: list) -> tuple:
    """Returns (steps, order). Order is a list[int]. Each step:
        {kind: 'init'|'enqueue'|'pop'|'decrement'|'cycle'|'done',
         node?: int, in_degree: list[int], queue: list[int],
         order: list[int], action: str}
    """
    in_deg = [0] * num_nodes
    adj = [[] for _ in range(num_nodes)]
    for e in edges:
        u, v = e[0], e[1]
        adj[u].append(v)
        in_deg[v] += 1

    steps = [{"kind": "init", "in_degree": list(in_deg),
              "queue": [], "order": [],
              "action": f"in_degree = {in_deg}"}]

    queue = [i for i in range(num_nodes) if in_deg[i] == 0]
    if queue:
        steps.append({"kind": "enqueue", "node": queue[:],
                      "in_degree": list(in_deg), "queue": list(queue),
                      "order": [],
                      "action": f"enqueue zero-in-degree nodes: {queue}"})

    order = []
    safety = 0
    while queue:
        safety += 1
        if safety > num_nodes * 4:  # cycle safeguard
            steps.append({"kind": "cycle", "in_degree": list(in_deg),
                          "queue": list(queue), "order": list(order),
                          "action": "cycle detected"})
            return steps, order

        u = queue.pop(0)
        order.append(u)
        steps.append({"kind": "pop", "node": u,
                      "in_degree": list(in_deg), "queue": list(queue),
                      "order": list(order),
                      "action": f"pop {u} → order = {order}"})

        for v in adj[u]:
            in_deg[v] -= 1
            if in_deg[v] == 0:
                queue.append(v)
                steps.append({"kind": "decrement", "node": v,
                              "in_degree": list(in_deg), "queue": list(queue),
                              "order": list(order),
                              "action": f"in_deg[{v}] → 0, enqueue"})
            else:
                steps.append({"kind": "decrement", "node": v,
                              "in_degree": list(in_deg), "queue": list(queue),
                              "order": list(order),
                              "action": f"in_deg[{v}] → {in_deg[v]}"})

    if any(d > 0 for d in in_deg):
        steps.append({"kind": "cycle", "in_degree": list(in_deg),
                      "queue": [], "order": list(order),
                      "action": "remaining in_degrees > 0 → cycle"})
        return steps, order

    steps.append({"kind": "done", "in_degree": list(in_deg),
                  "queue": [], "order": list(order),
                  "action": f"order = {order}"})
    return steps, order


_TOPO_SORT_PSEUDOCODE = """
in_deg = [count incoming]
queue = [v for in_deg[v]==0]
while queue:
    u = queue.popleft()
    order.append(u)
    for v in adj[u]:
        in_deg[v] -= 1
        if in_deg[v]==0: queue.append(v)
""".strip()


class TopologicalSortScene(Scene):
    """Kahn's topological sort on a directed graph.

    Schema: {num_nodes: int, edges: List[[u,v]], caption: str}
    """

    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        num_nodes = p.get("num_nodes", 5)
        edges     = p.get("edges",     [[0, 1], [0, 2], [1, 3], [2, 3], [3, 4]])
        cap       = p.get("caption",   "")

        title = Text("Topological Sort — Kahn's Algorithm",
                     font_size=26).to_edge(UP, buff=0.3)
        badge = ComplexityBadge(time="O(V+E)", space="O(V+E)", font_size=14)
        if title.width > 6.0:
            badge.vgroup.next_to(title, DOWN, buff=0.15)
        else:
            badge.vgroup.next_to(title, RIGHT, buff=0.3)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)
        self.play(Write(title), FadeIn(badge.vgroup))

        # Graph centered slightly left so right side has room for queue/order
        graph = GraphPanel(num_nodes, edges, position=LEFT * 1.6,
                           radius=1.8, node_radius=0.28, directed=True)

        # in_degree strip below the graph
        in_deg_init = [0] * num_nodes
        for e in edges:
            in_deg_init[e[1]] += 1
        in_strip = ArrayStrip(in_deg_init, position=DOWN * 2.1 + LEFT * 1.6,
                              cell_size=0.45)
        in_lbl = Text("in_degree", font_size=14, color=GRAY).next_to(
            in_strip.vgroup, LEFT, buff=0.2)

        # Queue (StackWidget reused as queue — push/pop from one end)
        queue_w = StackWidget(position=RIGHT * 3.5 + UP * 0.8,
                              cell_w=0.85, cell_h=0.45, max_visible=6,
                              title="queue")
        # StackWidget already has its own title; no separate label needed
        queue_lbl = VGroup()

        # Order display (text that grows as we add)
        order_lbl = Text("order: [ ]", font_size=18, color=KEEP).to_edge(DOWN, buff=2.6)

        _custom = (p.get("pseudocode") or "").strip()
        code_panel = CodePanel(_custom or _TOPO_SORT_PSEUDOCODE, anchor=UL,
                               font_size=13, max_width=4.0)
        code_panel.is_custom = bool(_custom)

        self.play(FadeIn(graph.vgroup), FadeIn(in_strip.vgroup),
                  Write(in_strip.indices), FadeIn(in_lbl),
                  FadeIn(queue_w.vgroup), FadeIn(queue_lbl),
                  FadeIn(code_panel.vgroup), FadeIn(order_lbl))
        self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.play(code_panel.anim_highlight(0), run_time=0.25)

        steps, order = _topological_sort_steps(num_nodes, edges)
        if not steps:
            return
        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        for step in steps[1:]:
            kind = step["kind"]

            if kind == "enqueue":
                self.play(code_panel.anim_highlight(1), run_time=0.2)
                # Glow each zero-in-degree node green and push to queue
                for nid in step["node"]:
                    self.play(
                        graph.anim_set_node_color(nid, KEEP, opacity=0.85),
                        run_time=0.25,
                    )
                    item, anims = queue_w.anim_push(nid, color=KEEP)
                    if anims:
                        self.play(*anims, run_time=0.25)

            elif kind == "pop":
                self.play(code_panel.anim_highlight(3), run_time=0.2)
                u = step["node"]
                # Remove from queue widget (returns (popped_val, anims_list))
                _, pop_anims = queue_w.anim_pop()
                if pop_anims:
                    self.play(*pop_anims, run_time=0.3)
                # Glow + dim popped node
                self.play(graph.anim_set_node_color(u, "#475569", opacity=0.5),
                          run_time=0.3)
                # Update order label
                new_order_lbl = Text(f"order: {step['order']}",
                                     font_size=18, color=KEEP).to_edge(DOWN, buff=2.6)
                self.play(Transform(order_lbl, new_order_lbl), run_time=0.25)

            elif kind == "decrement":
                v = step["node"]
                self.play(code_panel.anim_highlight(6), run_time=0.15)
                anims = [in_strip.anim_set_value(v, step["in_degree"][v]),
                         in_strip.flash(v, color=YELLOW, scale=1.2)]
                if step["order"]:
                    edge_anim = graph.anim_flash_edge(step["order"][-1], v,
                                                      color=YELLOW)
                    if edge_anim is not None:
                        anims.append(edge_anim)
                self.play(*anims, run_time=0.35)
                if step["in_degree"][v] == 0:
                    self.play(code_panel.anim_highlight(7), run_time=0.15)
                    self.play(graph.anim_set_node_color(v, KEEP, opacity=0.85),
                              run_time=0.2)
                    item, anims = queue_w.anim_push(v, color=KEEP)
                    if anims:
                        self.play(*anims, run_time=0.25)

            elif kind == "cycle":
                self.play(Transform(act, action_text(step["action"])), run_time=0.25)
                rb = result_box("Cycle detected — no valid order",
                                font_size=22).to_edge(DOWN, buff=1.75)
                rb[1].set_color(REJECT)
                self.play(FadeIn(rb))
                self.wait(1.0)
                self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)
                return

            elif kind == "done":
                break

            self.play(Transform(act, action_text(step["action"])), run_time=0.25)
            self.wait(0.15)

        rb = result_box(f"order = {order}", font_size=22).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        cmp = BruteForceComparison(
            brute=("DFS + post-order", "O(V+E) (more nuanced)"),
            optimal=("Kahn's BFS w/ in_degree", "O(V+E)"),
        )
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.3)
        self.play(FadeIn(cmp.vgroup), run_time=0.4)
        self.wait(1.0)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ===========================================================================
#  Phase 7B Scene 4 — BitManipulationScene
# ===========================================================================
#
#  Three classic bit-manipulation patterns:
#    single_number  : XOR-fold to find the value appearing once (LC 136)
#    count_bits     : Brian-Kernighan (n & (n-1)) loop (LC 191)
#    reverse_bits   : MSB↔LSB reversal of an 8-bit word (LC 190)
# ---------------------------------------------------------------------------

def _single_number_steps(values: list, num_bits: int = 8) -> tuple:
    """Returns (steps, result). Each step: {kind, value, result, action}."""
    steps = [{"kind": "init", "value": 0, "result": 0,
              "action": "result = 0"}]
    result = 0
    for v in values:
        old = result
        result ^= v
        steps.append({"kind": "xor", "value": v, "result": result, "old": old,
                      "action": f"{old} ^ {v} = {result}"})
    steps.append({"kind": "done", "value": 0, "result": result,
                  "action": f"answer = {result}"})
    return steps, result


def _count_bits_steps(value: int, num_bits: int = 8) -> tuple:
    """Brian-Kernighan: while n: n &= (n-1); count += 1.
    Returns (steps, count). Each step: {kind, n, count, action}.
    """
    steps = [{"kind": "init", "n": value, "count": 0,
              "action": f"n = {value}, count = 0"}]
    n, count = value, 0
    while n:
        n_after = n & (n - 1)
        count += 1
        steps.append({"kind": "clear", "n": n_after, "count": count,
                      "action": f"n & (n-1) = {n_after}, count = {count}"})
        n = n_after
    steps.append({"kind": "done", "n": 0, "count": count,
                  "action": f"answer = {count} bits"})
    return steps, count


_SINGLE_NUMBER_PSEUDOCODE = """
result = 0
for v in nums:
    result ^= v
return result
""".strip()


_COUNT_BITS_PSEUDOCODE = """
count = 0
while n:
    n = n & (n - 1)
    count += 1
return count
""".strip()


class BitManipulationScene(Scene):
    """Bit manipulation: single_number / count_bits.

    Schema: {values: List[int], operation: str, caption: str}
       For single_number: values is the input list, result is the XOR of all.
       For count_bits:    values[0] is the number to count bits in.
    """

    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        values    = p.get("values") or [4, 1, 2, 1, 2]
        operation = p.get("operation", "single_number")
        cap       = p.get("caption",   "")

        title_map = {"single_number": "Single Number — XOR Fold",
                     "count_bits":    "Count Bits — Brian-Kernighan"}
        title = Text(title_map.get(operation, operation),
                     font_size=28).to_edge(UP, buff=0.3)
        badge = ComplexityBadge(time="O(n)", space="O(1)", font_size=14)
        if title.width > 6.0:
            badge.vgroup.next_to(title, DOWN, buff=0.15)
        else:
            badge.vgroup.next_to(title, RIGHT, buff=0.3)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)
        self.play(Write(title), FadeIn(badge.vgroup))

        custom_code = (p.get("pseudocode") or "").strip()
        if operation == "single_number":
            self._run_single_number(values, custom_code)
        else:
            self._run_count_bits(values[0] if values else 0, custom_code)

        self.wait(0.4)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)

    # ─── single_number ──────────────────────────────────────────────────────

    def _run_single_number(self, values, custom_code=""):
        num_bits = 8
        result_reg = BinaryRegister(value=0, num_bits=num_bits, label="result",
                                    position=UP * 0.6, cell_size=0.55)
        next_reg = BinaryRegister(value=0, num_bits=num_bits, label="v",
                                  position=DOWN * 0.5, cell_size=0.55)

        code_panel = CodePanel(custom_code or _SINGLE_NUMBER_PSEUDOCODE, anchor=UL,
                               font_size=15, max_width=4.0)
        code_panel.is_custom = bool(custom_code)
        state = StatePanel(anchor=UR, title="State")

        self.play(FadeIn(result_reg.vgroup), FadeIn(next_reg.vgroup),
                  FadeIn(code_panel.vgroup), FadeIn(state.vgroup))
        self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.play(code_panel.anim_highlight(0), run_time=0.25)
        self.play(*state.anim_set("result", 0, color=KEEP), run_time=0.25)

        steps, ans = _single_number_steps(values, num_bits)
        if not steps:
            return
        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        # Walk steps[1:] (skip init) — each is an XOR step except the last (done)
        for step in steps[1:]:
            if step["kind"] == "done":
                break
            v = step["value"]
            self.play(code_panel.anim_highlight(2), run_time=0.2)

            # Update next_reg to display the next value v, then XOR into result
            new_v_reg = BinaryRegister(
                value=v, num_bits=num_bits, label="v",
                position=next_reg.vgroup.get_center(), cell_size=0.55,
            )
            self.play(Transform(next_reg.vgroup, new_v_reg.vgroup), run_time=0.4)
            next_reg.value = v
            next_reg.bits = [(v >> (num_bits - 1 - i)) & 1 for i in range(num_bits)]

            # XOR bit by bit — flash differing bits
            target_bits = [a ^ b for a, b in zip(result_reg.bits, next_reg.bits)]
            flash_anims = []
            set_anims = []
            for j, target_bit in enumerate(target_bits):
                bit_idx = num_bits - 1 - j  # LSB convention
                cur_bit = result_reg.bits[j]
                if cur_bit != target_bit:
                    flash_anims.append(result_reg.flash(bit_idx, color=YELLOW, scale=1.3))
                    set_anim = result_reg.anim_set_bit(bit_idx, target_bit)
                    if set_anim is not None:
                        set_anims.append(set_anim)

            if flash_anims:
                self.play(*flash_anims, run_time=0.4)
            if set_anims:
                self.play(*set_anims, run_time=0.4)

            self.play(*state.anim_set("result", step["result"], color=KEEP),
                      run_time=0.2)
            self.play(Transform(act, action_text(step["action"])), run_time=0.25)
            self.wait(0.2)

        # Final
        self.play(code_panel.anim_highlight(3), run_time=0.25)
        rb = result_box(f"Single number = {ans}", font_size=24).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        cmp = BruteForceComparison(
            brute=("Hashmap of counts", "O(n) space"),
            optimal=("XOR-fold (a ^ a = 0)", "O(1) space"),
        )
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.3)
        self.play(FadeIn(cmp.vgroup), run_time=0.4)

    # ─── count_bits (Brian-Kernighan) ───────────────────────────────────────

    def _run_count_bits(self, value, custom_code=""):
        num_bits = 8
        n_reg = BinaryRegister(value=value, num_bits=num_bits, label="n",
                               position=UP * 0.5, cell_size=0.55)

        code_panel = CodePanel(custom_code or _COUNT_BITS_PSEUDOCODE, anchor=UL,
                               font_size=15, max_width=4.0)
        code_panel.is_custom = bool(custom_code)
        state = StatePanel(anchor=UR, title="State")

        self.play(FadeIn(n_reg.vgroup),
                  FadeIn(code_panel.vgroup), FadeIn(state.vgroup))
        self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.play(code_panel.anim_highlight(0), run_time=0.25)
        self.play(*state.anim_set("count", 0, color=KEEP), run_time=0.25)

        steps, count = _count_bits_steps(value, num_bits)
        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        for step in steps[1:]:
            if step["kind"] == "done":
                break
            self.play(code_panel.anim_highlight(2), run_time=0.2)

            target_bits = [(step["n"] >> (num_bits - 1 - i)) & 1 for i in range(num_bits)]
            flash_anims = []
            set_anims = []
            for j, tb in enumerate(target_bits):
                bit_idx = num_bits - 1 - j
                if n_reg.bits[j] != tb:
                    flash_anims.append(n_reg.flash(bit_idx, color=REJECT, scale=1.3))
                    sa = n_reg.anim_set_bit(bit_idx, tb)
                    if sa is not None:
                        set_anims.append(sa)
            if flash_anims:
                self.play(*flash_anims, run_time=0.4)
            if set_anims:
                self.play(*set_anims, run_time=0.4)

            self.play(*state.anim_set("count", step["count"], color=KEEP),
                      run_time=0.2)
            self.play(Transform(act, action_text(step["action"])), run_time=0.25)
            self.wait(0.15)

        self.play(code_panel.anim_highlight(4), run_time=0.25)
        rb = result_box(f"Set bits = {count}", font_size=24).to_edge(DOWN, buff=1.75)
        rb[1].set_color(KEEP)
        cmp = BruteForceComparison(
            brute=("Check each bit (32 iters)", "O(num_bits)"),
            optimal=("Brian-Kernighan trick", "O(set_bits)"),
        )
        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.3)
        self.play(FadeIn(cmp.vgroup), run_time=0.4)


# ===========================================================================
#  Phase 7B Scene 3 — GreedyIntervalScene
# ===========================================================================
#
#  Greedy "reach"-based decisions for jump_game and gas_station.
#  jump_game: max_reach = max(max_reach, i + nums[i]); fail if max_reach < i.
#  gas_station: track running tank; reset start when it goes negative.
# ---------------------------------------------------------------------------

def _greedy_jump_game_steps(values: list) -> tuple:
    """Returns (steps, can_reach_end). Each step:
        {kind: 'examine'|'success'|'fail', i: int, max_reach: int,
         action: str}
    """
    n = len(values)
    if n == 0:
        return [], True  # vacuous
    steps = [{"kind": "examine", "i": 0, "max_reach": 0,
              "action": "max_reach = 0"}]
    max_reach = 0
    for i in range(n):
        if i > max_reach:
            steps.append({"kind": "fail", "i": i, "max_reach": max_reach,
                          "action": f"i={i} > max_reach={max_reach} → STUCK"})
            return steps, False
        max_reach = max(max_reach, i + values[i])
        steps.append({"kind": "examine", "i": i, "max_reach": max_reach,
                      "action": f"i={i}, jump≤{values[i]}, max_reach={max_reach}"})
        if max_reach >= n - 1:
            steps.append({"kind": "success", "i": i, "max_reach": max_reach,
                          "action": f"max_reach {max_reach} ≥ {n-1} → REACHABLE"})
            return steps, True
    return steps, False


def _greedy_gas_station_steps(values: list) -> tuple:
    """Returns (steps, start_index_or_-1). values is gas - cost per station.
    Each step: {kind: 'examine'|'reset'|'done', i: int, tank: int,
                start: int, total: int, action: str}
    """
    n = len(values)
    if n == 0:
        return [], -1
    total = 0
    tank = 0
    start = 0
    steps = [{"kind": "examine", "i": 0, "tank": 0, "start": 0, "total": 0,
              "action": "tank=0, start=0"}]
    for i in range(n):
        diff = values[i]
        total += diff
        tank  += diff
        if tank < 0:
            steps.append({"kind": "reset", "i": i, "tank": 0,
                          "start": i + 1, "total": total,
                          "action": f"tank<0 at {i} → start ← {i+1}"})
            tank = 0
            start = i + 1
        else:
            steps.append({"kind": "examine", "i": i, "tank": tank,
                          "start": start, "total": total,
                          "action": f"i={i}, +{diff} → tank={tank}"})
    if total < 0:
        steps.append({"kind": "done", "i": n - 1, "tank": tank,
                      "start": -1, "total": total,
                      "action": "total<0 → impossible"})
        return steps, -1
    steps.append({"kind": "done", "i": n - 1, "tank": tank,
                  "start": start, "total": total,
                  "action": f"answer = {start}"})
    return steps, start


_JUMP_GAME_PSEUDOCODE = """
max_reach = 0
for i in range(n):
    if i > max_reach: return False
    max_reach = max(max_reach, i + a[i])
    if max_reach >= n-1: return True
return False
""".strip()


_GAS_STATION_PSEUDOCODE = """
tank = total = 0
start = 0
for i in range(n):
    tank  += diff[i]
    total += diff[i]
    if tank < 0:
        start = i + 1
        tank = 0
return start if total >= 0 else -1
""".strip()


class GreedyIntervalScene(Scene):
    """Jump Game (LC 55) or Gas Station (LC 134) — greedy with reach state.

    Schema: {values: List[int], algorithm: "jump_game"|"gas_station", caption}
    """

    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        values    = p.get("values") or [2, 3, 1, 1, 4]
        algorithm = p.get("algorithm", "jump_game")
        cap       = p.get("caption",   "")

        title_map = {"jump_game": "Jump Game — Greedy Reach",
                     "gas_station": "Gas Station — Running Tank"}
        title = Text(title_map.get(algorithm, algorithm),
                     font_size=28).to_edge(UP, buff=0.3)
        badge = ComplexityBadge(time="O(n)", space="O(1)", font_size=14)
        if title.width > 6.0:
            badge.vgroup.next_to(title, DOWN, buff=0.15)
        else:
            badge.vgroup.next_to(title, RIGHT, buff=0.3)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)
        self.play(Write(title), FadeIn(badge.vgroup))

        strip = ArrayStrip(values, position=UP * 0.4)

        _custom = (p.get("pseudocode") or "").strip()
        pseudo = _custom or (_JUMP_GAME_PSEUDOCODE if algorithm == "jump_game"
                             else _GAS_STATION_PSEUDOCODE)
        code_panel = CodePanel(pseudo, anchor=UL, font_size=14, max_width=4.0)
        code_panel.is_custom = bool(_custom)
        state = StatePanel(anchor=UR, title="State")

        self.play(FadeIn(strip.vgroup), Write(strip.indices),
                  FadeIn(code_panel.vgroup), FadeIn(state.vgroup))
        self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.play(code_panel.anim_highlight(0), run_time=0.25)

        i_ptr = Pointer("i", color=PTR_COLORS["i"]).place_below(strip, 0)
        self.play(FadeIn(i_ptr.vgroup))

        if algorithm == "jump_game":
            self._run_jump_game(values, strip, code_panel, state, i_ptr)
        else:
            self._run_gas_station(values, strip, code_panel, state, i_ptr)

        self.wait(0.4)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)

    # ─── jump_game ──────────────────────────────────────────────────────────

    def _run_jump_game(self, values, strip, code_panel, state, i_ptr):
        n = len(values)
        steps, ok = _greedy_jump_game_steps(values)
        if not steps:
            return

        self.play(*state.anim_set("max_reach", 0, color=KEEP), run_time=0.25)

        # Reach zone — a translucent bar above the strip showing max_reach
        reach_zone = Rectangle(
            width=strip.cell_size * 0.95, height=0.18,
            stroke_width=0, fill_color=KEEP, fill_opacity=0.55,
        )
        reach_zone.next_to(strip.cell_top(0), UP, buff=0.08)
        self.play(FadeIn(reach_zone), run_time=0.25)

        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        for step in steps[1:]:
            kind = step["kind"]
            i = step["i"]
            mr = step["max_reach"]

            self.play(i_ptr.anim_move_to(strip, i),
                      strip.anim_set_fill(i, HILITE, 0.85),
                      code_panel.anim_highlight(2),
                      run_time=0.35, rate_func=smooth)

            if kind == "fail":
                self.play(code_panel.anim_highlight(2), run_time=0.15)
                self.play(strip.flash(i, color=REJECT, scale=1.25), run_time=0.3)
                self.play(Transform(act, action_text(step["action"])), run_time=0.25)
                rb = result_box("Cannot reach end", font_size=24).to_edge(DOWN, buff=1.75)
                rb[1].set_color(REJECT)
                self.play(FadeIn(rb))
                return

            # Update reach zone width to span [0..mr]
            new_w = strip.cell_size * (mr - 0 + 1)
            new_w = min(new_w, strip.cell_size * n)
            new_x = strip.cell_top(0)[0] + (mr * strip.cell_size) / 2
            new_zone = Rectangle(
                width=new_w * 0.95, height=0.18,
                stroke_width=0, fill_color=KEEP, fill_opacity=0.55,
            ).move_to(np.array([new_x, reach_zone.get_center()[1], 0]))
            self.play(Transform(reach_zone, new_zone),
                      code_panel.anim_highlight(3),
                      run_time=0.35)

            self.play(*state.anim_set("max_reach", mr, color=KEEP), run_time=0.2)
            self.play(Transform(act, action_text(step["action"])), run_time=0.25)
            self.play(strip.anim_set_fill(i, KEEP, 0.55), run_time=0.15)

            if kind == "success":
                self.play(code_panel.anim_highlight(4), run_time=0.2)
                self.play(strip.flash(n - 1, color=KEEP, scale=1.3), run_time=0.4)
                rb = result_box("Reachable", font_size=24).to_edge(DOWN, buff=1.75)
                rb[1].set_color(KEEP)
                cmp = BruteForceComparison(
                    brute=("DFS over all jumps", "O(2^n)"),
                    optimal=("Greedy max_reach", "O(n)"),
                )
                self.play(FadeOut(act), FadeIn(rb))
                self.wait(0.3)
                self.play(FadeIn(cmp.vgroup), run_time=0.4)
                return

            self.wait(0.15)

    # ─── gas_station ────────────────────────────────────────────────────────

    def _run_gas_station(self, values, strip, code_panel, state, i_ptr):
        n = len(values)
        steps, ans = _greedy_gas_station_steps(values)
        if not steps:
            return

        self.play(*state.anim_set("tank", 0, color=KEEP),
                  *state.anim_set("start", 0, color=PTR_COLORS["L"]),
                  *state.anim_set("total", 0, color=BLUE),
                  run_time=0.3)

        # start_marker — small triangle above strip
        start_marker = Triangle(color=PTR_COLORS["L"], fill_opacity=1.0).scale(0.14)
        start_marker.next_to(strip.cell_top(0), UP, buff=0.05)
        self.play(FadeIn(start_marker), run_time=0.25)

        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        for step in steps[1:]:
            kind = step["kind"]
            i = step["i"]

            self.play(i_ptr.anim_move_to(strip, i),
                      code_panel.anim_highlight(3),
                      run_time=0.3, rate_func=smooth)

            if kind == "reset":
                self.play(code_panel.anim_highlight(5), run_time=0.2)
                self.play(strip.flash(i, color=REJECT, scale=1.25), run_time=0.3)
                # move start_marker to i+1
                if step["start"] < n:
                    new_marker = start_marker.copy().next_to(
                        strip.cell_top(step["start"]), UP, buff=0.05)
                    self.play(Transform(start_marker, new_marker), run_time=0.35)
                self.play(*state.anim_set("tank", 0, color=KEEP),
                          *state.anim_set("start", step["start"], color=PTR_COLORS["L"]),
                          *state.anim_set("total", step["total"], color=BLUE),
                          run_time=0.25)
            elif kind == "examine":
                self.play(strip.flash(i, color=HILITE, scale=1.15), run_time=0.2)
                self.play(*state.anim_set("tank", step["tank"], color=KEEP),
                          *state.anim_set("total", step["total"], color=BLUE),
                          run_time=0.25)
            elif kind == "done":
                self.play(code_panel.anim_highlight(8), run_time=0.2)
                if ans == -1:
                    rb = result_box("Impossible (total < 0)", font_size=24).to_edge(DOWN, buff=1.75)
                    rb[1].set_color(REJECT)
                else:
                    rb = result_box(f"Start at index {ans}", font_size=24).to_edge(DOWN, buff=1.75)
                    rb[1].set_color(KEEP)
                cmp = BruteForceComparison(
                    brute=("Try every start", "O(n²)"),
                    optimal=("Single pass + reset", "O(n)"),
                )
                self.play(FadeOut(act), FadeIn(rb))
                self.wait(0.3)
                self.play(FadeIn(cmp.vgroup), run_time=0.4)
                return

            self.play(Transform(act, action_text(step["action"])), run_time=0.25)
            self.wait(0.1)


# ===========================================================================
#  Phase 7B Scene 2 — TrappingRainWaterScene
# ===========================================================================
#
#  Two-pointer water trapping on a histogram of heights. At each step,
#  the pointer at the smaller side moves inward; water[i] accumulates
#  as min(left_max, right_max) - height[i] for the cell being processed.
# ---------------------------------------------------------------------------

def _trapping_rain_water_steps(heights: list) -> tuple:
    """Returns (steps, total_water).

    Each step: {kind: 'init'|'move'|'fill'|'done', l: int, r: int,
                left_max: int, right_max: int, water_at: int|null,
                total: int, action: str}
    """
    n = len(heights)
    if n < 2:
        return [], 0

    l, r = 0, n - 1
    left_max = right_max = 0
    total = 0
    steps = [{"kind": "init", "l": l, "r": r, "left_max": 0, "right_max": 0,
              "water_at": None, "total": 0,
              "action": f"l=0, r={n-1}"}]

    while l < r:
        if heights[l] < heights[r]:
            if heights[l] >= left_max:
                left_max = heights[l]
                steps.append({"kind": "move", "l": l, "r": r,
                              "left_max": left_max, "right_max": right_max,
                              "water_at": None, "total": total,
                              "action": f"left_max ← {left_max} (h[{l}])"})
            else:
                w = left_max - heights[l]
                total += w
                steps.append({"kind": "fill", "l": l, "r": r,
                              "left_max": left_max, "right_max": right_max,
                              "water_at": l, "total": total,
                              "action": f"water at {l}: {left_max}-{heights[l]} = {w}"})
            l += 1
        else:
            if heights[r] >= right_max:
                right_max = heights[r]
                steps.append({"kind": "move", "l": l, "r": r,
                              "left_max": left_max, "right_max": right_max,
                              "water_at": None, "total": total,
                              "action": f"right_max ← {right_max} (h[{r}])"})
            else:
                w = right_max - heights[r]
                total += w
                steps.append({"kind": "fill", "l": l, "r": r,
                              "left_max": left_max, "right_max": right_max,
                              "water_at": r, "total": total,
                              "action": f"water at {r}: {right_max}-{heights[r]} = {w}"})
            r -= 1

    steps.append({"kind": "done", "l": l, "r": r,
                  "left_max": left_max, "right_max": right_max,
                  "water_at": None, "total": total,
                  "action": f"total water = {total}"})
    return steps, total


_TRAP_PSEUDOCODE = """
l, r = 0, n - 1
while l < r:
    if h[l] < h[r]:
        if h[l] >= L: L = h[l]
        else: total += L - h[l]
        l += 1
    else:
        if h[r] >= R: R = h[r]
        else: total += R - h[r]
        r -= 1
""".strip()


class TrappingRainWaterScene(Scene):
    """Trapping Rain Water (LC 42) — two-pointer with running max.

    Schema: {heights: List[int], caption: str}
    """

    def construct(self):
        self.camera.background_color = "#0d1117"
        p = load_params()
        heights = p.get("heights") or [0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1]
        cap     = p.get("caption", "")

        title = Text("Trapping Rain Water", font_size=28).to_edge(UP, buff=0.3)
        badge = ComplexityBadge(time="O(n)", space="O(1)", font_size=14)
        if title.width > 6.0:
            badge.vgroup.next_to(title, DOWN, buff=0.15)
        else:
            badge.vgroup.next_to(title, RIGHT, buff=0.3)

        if cap:
            show_title_card(self, cap)
            self.play(FadeIn(caption_strip(cap)), run_time=0.3)
        self.play(Write(title), FadeIn(badge.vgroup))

        # Build histogram bars (variable-height rectangles)
        n = len(heights)
        max_h = max(max(heights), 1)
        bar_width = min(0.7, 9.5 / n)
        unit_h = 2.0 / max_h  # total bar area is 2 units tall
        baseline_y = -0.8
        start_x = -(n - 1) * bar_width / 2

        bars = []
        for i, h in enumerate(heights):
            cx = start_x + i * bar_width
            bar_h = max(h * unit_h, 0.05)  # tiny stub for height=0
            bar = Rectangle(
                width=bar_width * 0.92, height=bar_h,
                stroke_color=WHITE, stroke_width=1,
                fill_color="#94a3b8", fill_opacity=0.85,
            )
            bar.move_to(np.array([cx, baseline_y + bar_h / 2, 0]))
            bars.append(bar)

        # Index labels under each bar
        idx_lbls = VGroup(*[
            Text(str(i), font_size=14, color=GRAY).move_to(
                np.array([start_x + i * bar_width, baseline_y - 0.18, 0]))
            for i in range(n)
        ])

        bars_grp = VGroup(*bars, idx_lbls)

        _custom = (p.get("pseudocode") or "").strip()
        code_panel = CodePanel(_custom or _TRAP_PSEUDOCODE, anchor=UL,
                               font_size=14, max_width=4.0)
        code_panel.is_custom = bool(_custom)
        state = StatePanel(anchor=UR, title="State")

        self.play(FadeIn(bars_grp), FadeIn(code_panel.vgroup), FadeIn(state.vgroup))
        self.play(code_panel.anim_dim_all(), run_time=0.2)
        self.play(code_panel.anim_highlight(0), run_time=0.25)

        # Pointer triangles below bars
        def _ptr(label, color):
            arrow = Triangle(color=color, fill_opacity=1.0).scale(0.16).rotate(PI)
            lbl   = Text(label, font_size=14, color=color, weight=BOLD)
            return VGroup(arrow, lbl).arrange(DOWN, buff=0.05)

        l_ptr = _ptr("L", PTR_COLORS["L"])
        r_ptr = _ptr("R", PTR_COLORS["R"])

        def _place_ptr(ptr, idx):
            ptr.next_to(bars[idx], DOWN, buff=0.32)

        _place_ptr(l_ptr, 0)
        _place_ptr(r_ptr, n - 1)
        self.play(FadeIn(l_ptr), FadeIn(r_ptr))

        self.play(*state.anim_set("L", 0, color=PTR_COLORS["L"]),
                  *state.anim_set("R", 0, color=PTR_COLORS["R"]),
                  *state.anim_set("water", 0, color=BLUE),
                  run_time=0.3)

        steps, total_water = _trapping_rain_water_steps(heights)
        if not steps:
            return
        act = action_text(steps[0]["action"])
        self.play(FadeIn(act))

        water_blocks = {}  # i → Rectangle covering water[i]

        for step in steps[1:]:  # skip init
            kind = step["kind"]
            if kind == "done":
                break

            l_i, r_i = step["l"], step["r"]
            self.play(code_panel.anim_highlight(1), run_time=0.15)

            # Move the pointer that didn't advance yet — actually both might shift
            # depending on the previous iteration. We just place each at l_i, r_i
            # of the current step.
            new_l = l_ptr.copy(); _place_ptr(new_l, l_i)
            new_r = r_ptr.copy(); _place_ptr(new_r, r_i)
            self.play(Transform(l_ptr, new_l), Transform(r_ptr, new_r),
                      run_time=0.35, rate_func=smooth)

            if kind == "fill":
                # Animate water filling above the bar
                idx = step["water_at"]
                bar = bars[idx]
                wall_max = step["left_max"] if idx <= (l_i + r_i) // 2 else step["right_max"]
                water_top_y = baseline_y + wall_max * unit_h
                water_h = water_top_y - (bar.get_top()[1])
                if water_h > 0:
                    water = Rectangle(
                        width=bar.width, height=water_h,
                        stroke_width=0, fill_color="#06b6d4", fill_opacity=0.55,
                    )
                    water.move_to(np.array([bar.get_center()[0],
                                            bar.get_top()[1] + water_h / 2, 0]))
                    water_blocks[idx] = water
                    # Highlight the relevant code line(s)
                    line_to_hl = 5 if idx == l_i else 9
                    self.play(code_panel.anim_highlight(line_to_hl), run_time=0.2)
                    self.play(FadeIn(water, shift=DOWN * 0.2), run_time=0.4)
                    self.play(Indicate(water, color="#67e8f9", scale_factor=1.05),
                              run_time=0.3)
            else:  # move (running max updated)
                # Highlight the wall on the side that updated
                idx = l_i if step["left_max"] > 0 and l_i > 0 else r_i
                # Simpler: just check which max changed
                self.play(code_panel.anim_highlight(4 if l_i < r_i else 8),
                          Indicate(bars[step["l"] if step["left_max"] >= step["right_max"] else step["r"]],
                                   color=YELLOW, scale_factor=1.1),
                          run_time=0.35)

            self.play(*state.anim_set("L", step["left_max"], color=PTR_COLORS["L"]),
                      *state.anim_set("R", step["right_max"], color=PTR_COLORS["R"]),
                      *state.anim_set("water", step["total"], color=BLUE),
                      run_time=0.25)
            self.play(Transform(act, action_text(step["action"])), run_time=0.25)
            self.wait(0.15)

        # Final result + brute force comparison
        rb = result_box(f"Total trapped water = {total_water}",
                        font_size=24).to_edge(DOWN, buff=1.75)
        rb[1].set_color("#06b6d4")
        cmp = BruteForceComparison(
            brute=("Per-cell scan for max", "O(n²)"),
            optimal=("Two-pointer with running max", "O(n)"),
        )

        self.play(FadeOut(act), FadeIn(rb))
        self.wait(0.3)
        self.play(FadeIn(cmp.vgroup), run_time=0.4)
        self.wait(1.0)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


# ---------------------------------------------------------------------------
# DP family — 2D table scenes (Phase 2 of DP interview-prep batch)
# ---------------------------------------------------------------------------

class Knapsack01Scene(Scene):
    """0/1 Knapsack: dp[i][w] = max value using first i items, capacity w.

    Animates the (N+1) × (W+1) table row by row. For each cell, highlights
    the two predecessor cells (dp[i-1][w] for "skip item" and dp[i-1][w-wi]
    for "take item"), draws arrows, then writes the max.

    Params:
        items: list of {"weight": int, "value": int}
        capacity: int
    """

    def construct(self):
        params = load_params()
        items = params.get("items", [{"weight": 2, "value": 3},
                                       {"weight": 3, "value": 4},
                                       {"weight": 4, "value": 5}])
        capacity = int(params.get("capacity", 5))
        items = items[:5]              # cap render time
        capacity = min(capacity, 8)

        show_title_card(self, "0/1 Knapsack")

        N = len(items)
        W = capacity
        dp = [[0] * (W + 1) for _ in range(N + 1)]

        grid_values = [[str(0) for _ in range(W + 1)] for _ in range(N + 1)]
        grid = GridPanel(grid_values, cell_size=0.6)
        self.play(FadeIn(grid.vgroup), run_time=0.4)

        item_lines = [Text(f"#{i+1}: w={it['weight']}, v={it['value']}",
                             font_size=14, color=GRAY)
                       for i, it in enumerate(items)]
        items_vg = VGroup(*item_lines).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
        items_vg.next_to(grid.vgroup, LEFT, buff=0.5)
        self.play(FadeIn(items_vg), run_time=0.3)

        cap_text = Text(f"capacity = {capacity}", font_size=14, color=YELLOW)
        cap_text.next_to(grid.vgroup, UP, buff=0.3)
        self.play(FadeIn(cap_text), run_time=0.2)

        arrows: list = []
        for i in range(1, N + 1):
            wi = items[i - 1]["weight"]
            vi = items[i - 1]["value"]
            for w in range(W + 1):
                self.play(grid.anim_set_fill(i, w, YELLOW), run_time=0.10)
                for old in arrows:
                    self.remove(old)
                arrows = []
                if wi > w:
                    dp[i][w] = dp[i - 1][w]
                    a = GridArrow.between(grid, (i - 1, w), (i, w), color=TEAL)
                    self.play(Create(a), run_time=0.15)
                    arrows.append(a)
                else:
                    skip = dp[i - 1][w]
                    take = dp[i - 1][w - wi] + vi
                    dp[i][w] = max(skip, take)
                    self.play(grid.anim_set_fill(i - 1, w, BLUE, 0.5),
                              grid.anim_set_fill(i - 1, w - wi, GREEN, 0.5),
                              run_time=0.15)
                    a1 = GridArrow.between(grid, (i - 1, w), (i, w), color=BLUE)
                    a2 = GridArrow.between(grid, (i - 1, w - wi), (i, w),
                                             color=GREEN)
                    self.play(Create(a1), Create(a2), run_time=0.15)
                    arrows.extend([a1, a2])
                self.play(grid.anim_set_value(i, w, str(dp[i][w])),
                          grid.anim_set_fill(i, w, DEFAULT_CELL, 0.7),
                          run_time=0.10)

        for old in arrows:
            self.remove(old)
        rb = result_box(f"Max value = {dp[N][W]}", font_size=24)
        rb.to_edge(DOWN, buff=0.6)
        self.play(grid.anim_set_fill(N, W, GREEN, 0.85), run_time=0.4)
        self.play(FadeIn(rb), run_time=0.4)
        self.wait(1.0)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


def _fill_2d_dp(scene, grid, dp, *, predecessor_fn, color="GREEN",
                 highlight_color=YELLOW, run_time=0.10):
    """Shared 2D-DP fill loop used by LCS / EditDistance / CoinChange2D.

    For each cell (i, j) in row-major order, the caller-supplied
    ``predecessor_fn(i, j, dp)`` returns:
      - the new dp[i][j] value (str), and
      - a list of ((from_r, from_c), arrow_color) tuples to draw.

    The base row (i=0) and base column (j=0) are skipped — they're
    expected to be initialized before calling.
    """
    arrows: list = []
    rows = len(dp)
    cols = len(dp[0]) if rows else 0
    for i in range(1, rows):
        for j in range(1, cols):
            scene.play(grid.anim_set_fill(i, j, highlight_color),
                       run_time=run_time)
            for old in arrows:
                scene.remove(old)
            arrows = []
            new_val, deps = predecessor_fn(i, j, dp)
            dp[i][j] = new_val
            for (fr, fc), col in deps:
                a = GridArrow.between(grid, (fr, fc), (i, j), color=col)
                arrows.append(a)
            if arrows:
                scene.play(*[Create(a) for a in arrows], run_time=run_time)
            scene.play(grid.anim_set_value(i, j, str(dp[i][j])),
                       grid.anim_set_fill(i, j, DEFAULT_CELL, 0.7),
                       run_time=run_time)
    for old in arrows:
        scene.remove(old)


class LCSScene(Scene):
    """Longest Common Subsequence: dp[i][j] = LCS length of s1[:i], s2[:j].

    Renders the (|s1|+1) × (|s2|+1) table with diagonal-match / max-of-
    neighbors arrows. Header row + column show the two strings.
    """

    def construct(self):
        params = load_params()
        s1 = str(params.get("s1", "AGC"))[:8]
        s2 = str(params.get("s2", "GAC"))[:8]

        show_title_card(self, f"LCS — '{s1}' vs '{s2}'")

        N, M = len(s1), len(s2)
        dp = [[0] * (M + 1) for _ in range(N + 1)]
        # Header row labels: row 0 = "", col 0 = "", then chars of s2/s1
        values = [["·"] + list(s2)]
        for i in range(N):
            values.append([s1[i]] + ["0"] * M)
        # Pre-pad row 0 with 0s after the header (won't be animated)
        values[0] = ["·"] + [c for c in s2]
        for r in range(1, N + 1):
            for c in range(1, M + 1):
                values[r][c] = "0"

        grid = GridPanel(values, cell_size=0.55, with_indices=False)
        self.play(FadeIn(grid.vgroup), run_time=0.4)

        def predecessor_fn(i, j, dp_local):
            # Skip the "header" row 0 and column 0 (they're labels here,
            # not dp values) — adjust to dp[i-1][j-1] semantics.
            ci, cj = i - 1, j - 1
            if s1[ci] == s2[cj]:
                val = dp_local[i - 1][j - 1] + 1
                return val, [((i - 1, j - 1), GREEN)]
            a, b = dp_local[i - 1][j], dp_local[i][j - 1]
            if a >= b:
                return a, [((i - 1, j), TEAL)]
            return b, [((i, j - 1), BLUE)]

        _fill_2d_dp(self, grid, dp, predecessor_fn=predecessor_fn)

        rb = result_box(f"LCS length = {dp[N][M]}", font_size=24)
        rb.to_edge(DOWN, buff=0.6)
        self.play(grid.anim_set_fill(N, M, GREEN, 0.85), run_time=0.4)
        self.play(FadeIn(rb), run_time=0.4)
        self.wait(1.0)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


class EditDistanceScene(Scene):
    """Edit Distance (Levenshtein): dp[i][j] = min ops to transform
    s1[:i] → s2[:j]. Each cell picks min of insert/delete/replace."""

    def construct(self):
        params = load_params()
        s1 = str(params.get("s1", "cat"))[:6]
        s2 = str(params.get("s2", "bat"))[:6]

        show_title_card(self, f"Edit distance — '{s1}' → '{s2}'")

        N, M = len(s1), len(s2)
        dp = [[0] * (M + 1) for _ in range(N + 1)]
        for i in range(N + 1):
            dp[i][0] = i
        for j in range(M + 1):
            dp[0][j] = j
        values = [[str(dp[r][c]) for c in range(M + 1)] for r in range(N + 1)]
        grid = GridPanel(values, cell_size=0.6, with_indices=False)
        self.play(FadeIn(grid.vgroup), run_time=0.4)

        def predecessor_fn(i, j, dp_local):
            ci, cj = i - 1, j - 1
            if s1[ci] == s2[cj]:
                return dp_local[i - 1][j - 1], [((i - 1, j - 1), GREEN)]
            insert = dp_local[i][j - 1]
            delete = dp_local[i - 1][j]
            replace = dp_local[i - 1][j - 1]
            best = min(insert, delete, replace) + 1
            deps = []
            if insert <= delete and insert <= replace:
                deps.append(((i, j - 1), BLUE))
            elif delete <= replace:
                deps.append(((i - 1, j), TEAL))
            else:
                deps.append(((i - 1, j - 1), PURPLE))
            return best, deps

        _fill_2d_dp(self, grid, dp, predecessor_fn=predecessor_fn)

        rb = result_box(f"Edit distance = {dp[N][M]}", font_size=24)
        rb.to_edge(DOWN, buff=0.6)
        self.play(grid.anim_set_fill(N, M, GREEN, 0.85), run_time=0.4)
        self.play(FadeIn(rb), run_time=0.4)
        self.wait(1.0)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


class CoinChange2DScene(Scene):
    """Coin Change (number of ways): dp[i][w] = number of ways to make
    amount w using the first i coins."""

    def construct(self):
        params = load_params()
        coins = list(params.get("coins", [1, 2, 5]))[:4]
        amount = int(params.get("amount", 5))
        amount = min(amount, 10)

        show_title_card(self, f"Coin Change — amount={amount}")

        N = len(coins)
        dp = [[0] * (amount + 1) for _ in range(N + 1)]
        for i in range(N + 1):
            dp[i][0] = 1   # one way to make 0: pick nothing
        values = [[str(dp[r][c]) for c in range(amount + 1)]
                    for r in range(N + 1)]
        grid = GridPanel(values, cell_size=0.6, with_indices=False)
        self.play(FadeIn(grid.vgroup), run_time=0.4)

        coin_lines = [Text(f"coin {i}: {c}", font_size=14, color=GRAY)
                       for i, c in enumerate(coins)]
        coins_vg = VGroup(*coin_lines).arrange(DOWN, aligned_edge=LEFT, buff=0.10)
        coins_vg.next_to(grid.vgroup, LEFT, buff=0.4)
        self.play(FadeIn(coins_vg), run_time=0.3)

        def predecessor_fn(i, j, dp_local):
            coin = coins[i - 1]
            skip = dp_local[i - 1][j]
            deps = [((i - 1, j), TEAL)]
            take = 0
            if j >= coin:
                take = dp_local[i][j - coin]
                deps.append(((i, j - coin), GREEN))
            return skip + take, deps

        _fill_2d_dp(self, grid, dp, predecessor_fn=predecessor_fn)

        rb = result_box(f"Ways = {dp[N][amount]}", font_size=24)
        rb.to_edge(DOWN, buff=0.6)
        self.play(grid.anim_set_fill(N, amount, GREEN, 0.85), run_time=0.4)
        self.play(FadeIn(rb), run_time=0.4)
        self.wait(1.0)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


class LISScene(Scene):
    """Longest Increasing Subsequence (O(n²) DP).
    dp[i] = longest IS ending at index i. For each i, iterate j < i,
    arrow from j → i if nums[j] < nums[i] and dp[j]+1 > dp[i]."""

    def construct(self):
        params = load_params()
        nums = list(params.get("nums", [3, 1, 4, 1, 5, 9, 2, 6]))[:8]

        show_title_card(self, f"LIS — {nums}")

        N = len(nums)
        # Top row: input nums; bottom row: dp values (start at 1 each).
        values = [[str(v) for v in nums],
                  ["1"] * N]
        grid = GridPanel(values, cell_size=0.7, with_indices=False)
        self.play(FadeIn(grid.vgroup), run_time=0.4)

        dp = [1] * N
        # Label the rows
        row_lbl_top = Text("nums", font_size=14, color=GRAY)
        row_lbl_top.next_to(grid.vgroup, LEFT, buff=0.2)
        row_lbl_top.shift(UP * grid.cell_size * 0.5)
        row_lbl_bot = Text("dp", font_size=14, color=GRAY)
        row_lbl_bot.next_to(grid.vgroup, LEFT, buff=0.2)
        row_lbl_bot.shift(DOWN * grid.cell_size * 0.5)
        self.play(FadeIn(row_lbl_top), FadeIn(row_lbl_bot), run_time=0.2)

        arrows: list = []
        for i in range(1, N):
            self.play(grid.anim_set_fill(1, i, YELLOW), run_time=0.10)
            for old in arrows:
                self.remove(old)
            arrows = []
            best_j = -1
            for j in range(i):
                if nums[j] < nums[i] and dp[j] + 1 > dp[i]:
                    dp[i] = dp[j] + 1
                    best_j = j
            if best_j >= 0:
                a = GridArrow.between(grid, (1, best_j), (1, i), color=GREEN)
                arrows.append(a)
                self.play(Create(a), run_time=0.15)
            self.play(grid.anim_set_value(1, i, str(dp[i])),
                      grid.anim_set_fill(1, i, DEFAULT_CELL, 0.7),
                      run_time=0.10)
        for old in arrows:
            self.remove(old)

        rb = result_box(f"LIS length = {max(dp)}", font_size=24)
        rb.to_edge(DOWN, buff=0.6)
        self.play(FadeIn(rb), run_time=0.4)
        self.wait(1.0)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)


class DPProgressionScene(Scene):
    """Recursion → memoization → tabulation triptych.

    Shows the same problem (default: fibonacci(n)) in three regions:
      1. Naive recursion tree (exponential, duplicate subcalls)
      2. Memoized recursion (table fills, dupes are cache hits)
      3. Bottom-up tabulation (table fills in iteration order)

    For the hackathon scope, the recursion-tree panel is symbolic — the
    other two panels are real fills of a 1D `dp[]` table.
    """

    def construct(self):
        params = load_params()
        problem = str(params.get("problem", "fibonacci"))
        n = int(params.get("n", 5))
        n = min(max(n, 2), 8)

        show_title_card(self, f"Why DP works — {problem}(n={n})")

        # Region 1 — Recursion tree (symbolic; just shows duplicate calls)
        tree_title = Text("1. Naïve recursion", font_size=20, color=YELLOW)
        tree_title.to_edge(UP, buff=0.8)
        self.play(FadeIn(tree_title), run_time=0.3)

        dup_text = Text(f"fib({n-1}) and fib({n-2}) recompute fib({n-3}) twice",
                          font_size=16, color=GRAY)
        dup_text.next_to(tree_title, DOWN, buff=0.3)
        self.play(FadeIn(dup_text), run_time=0.3)

        complexity_bad = Text(f"Time: O(2^n) — exponential",
                                font_size=16, color="#fca5a5")
        complexity_bad.next_to(dup_text, DOWN, buff=0.2)
        self.play(FadeIn(complexity_bad), run_time=0.3)
        self.wait(1.5)
        self.play(FadeOut(tree_title), FadeOut(dup_text),
                  FadeOut(complexity_bad), run_time=0.3)

        # Region 2 — Memoization (table fills, deduped subcalls)
        memo_title = Text("2. Memoized recursion", font_size=20, color=YELLOW)
        memo_title.to_edge(UP, buff=0.8)
        memo_values = [["·"] + [str(i) for i in range(n + 1)],
                       ["·"] + ["—"] * (n + 1)]
        memo_grid = GridPanel(memo_values, cell_size=0.6, with_indices=False)
        self.play(FadeIn(memo_title), FadeIn(memo_grid.vgroup), run_time=0.4)

        memo_table = {0: 0, 1: 1}
        # Visually seed dp[0] = 0, dp[1] = 1
        self.play(memo_grid.anim_set_value(1, 1, "0"),
                  memo_grid.anim_set_value(1, 2, "1"),
                  memo_grid.anim_set_fill(1, 1, GREEN, 0.7),
                  memo_grid.anim_set_fill(1, 2, GREEN, 0.7),
                  run_time=0.3)
        for k in range(2, n + 1):
            memo_table[k] = memo_table[k - 1] + memo_table[k - 2]
            self.play(memo_grid.anim_set_fill(1, k + 1, YELLOW), run_time=0.10)
            self.play(memo_grid.anim_set_value(1, k + 1, str(memo_table[k])),
                      memo_grid.anim_set_fill(1, k + 1, GREEN, 0.7),
                      run_time=0.10)

        complexity_good = Text(f"Time: O(n) — each subproblem solved once",
                                 font_size=16, color="#10b981")
        complexity_good.next_to(memo_grid.vgroup, DOWN, buff=0.4)
        self.play(FadeIn(complexity_good), run_time=0.3)
        self.wait(1.5)
        self.play(FadeOut(memo_title), FadeOut(memo_grid.vgroup),
                  FadeOut(complexity_good), run_time=0.3)

        # Region 3 — Tabulation (canonical bottom-up)
        tab_title = Text("3. Bottom-up tabulation", font_size=20, color=YELLOW)
        tab_title.to_edge(UP, buff=0.8)
        tab_values = [["·"] + [str(i) for i in range(n + 1)],
                      ["·"] + ["—"] * (n + 1)]
        tab_grid = GridPanel(tab_values, cell_size=0.6, with_indices=False)
        self.play(FadeIn(tab_title), FadeIn(tab_grid.vgroup), run_time=0.4)

        tab = [0] * (n + 1)
        tab[0], tab[1] = 0, 1
        arrows: list = []
        self.play(tab_grid.anim_set_value(1, 1, "0"),
                  tab_grid.anim_set_value(1, 2, "1"),
                  run_time=0.3)
        for k in range(2, n + 1):
            tab[k] = tab[k - 1] + tab[k - 2]
            self.play(tab_grid.anim_set_fill(1, k + 1, YELLOW), run_time=0.10)
            for old in arrows:
                self.remove(old)
            arrows = []
            a1 = GridArrow.between(tab_grid, (1, k), (1, k + 1), color=BLUE)
            a2 = GridArrow.between(tab_grid, (1, k - 1), (1, k + 1), color=GREEN)
            arrows.extend([a1, a2])
            self.play(Create(a1), Create(a2), run_time=0.15)
            self.play(tab_grid.anim_set_value(1, k + 1, str(tab[k])),
                      tab_grid.anim_set_fill(1, k + 1, DEFAULT_CELL, 0.7),
                      run_time=0.10)
        for old in arrows:
            self.remove(old)

        rb = result_box(f"{problem}({n}) = {tab[n]}", font_size=22)
        rb.to_edge(DOWN, buff=0.6)
        self.play(FadeIn(rb), run_time=0.3)
        self.wait(1.5)
        self.play(*[FadeOut(mob) for mob in self.mobjects], run_time=0.5)
