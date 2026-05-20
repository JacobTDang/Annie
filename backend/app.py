import json
import os
import secrets
import string
import threading

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from google.genai import types as genai_types

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from agent.classifier import classify_domain
from agent.dsa_planner import plan_dsa
from agent.explainer import explain_problem
from agent.gemini_client import call_gemini
from agent.leetcode_parser import parse_problem as parse_leetcode_problem
from agent.math_parser import parse_math
from agent.planner import plan as plan_math
from renderer.worker import (
    get_job, submit_direct_lesson, submit_lesson, submit_render,
    pin_video, unpin_video,
)
from schemas.types import StepPlan

_TOPICS = [
    # ── DSA: sorting ──────────────────────────────────────────────
    {"id": "bubble-sort", "name": "Bubble Sort", "category": "dsa",
     "keywords": ["bubble sort", "bubblesort"],
     "description": "Pairwise compare-and-swap until the array is sorted."},
    {"id": "merge-sort", "name": "Merge Sort", "category": "dsa",
     "keywords": ["merge sort", "mergesort", "divide and conquer sort"],
     "description": "Recursive divide-and-merge visualization with comparison highlights."},
    {"id": "quick-sort", "name": "Quick Sort", "category": "dsa",
     "keywords": ["quick sort", "quicksort", "partition"],
     "description": "Pivot-based Lomuto partitioning shown step by step."},
    # ── DSA: searching ─────────────────────────────────────────────
    {"id": "binary-search", "name": "Binary Search", "category": "dsa",
     "keywords": ["binary search", "log n search"],
     "description": "Halving the search space on a sorted array via L/M/R pointers."},
    {"id": "binary-search-answer", "name": "Binary Search on Answer", "category": "dsa",
     "keywords": ["binary search on answer", "search the answer", "koko bananas", "capacity to ship"],
     "description": "Search a numeric answer space, not array indices (e.g. minimum eating speed)."},
    # ── DSA: two pointers ─────────────────────────────────────────
    {"id": "two-pointers", "name": "Two Pointers (Opposite Ends)", "category": "dsa",
     "keywords": ["two pointers", "two-pointer", "left right pointer"],
     "description": "L from the left, R from the right, converge inward."},
    {"id": "two-pointers-fast-slow", "name": "Two Pointers (Same Direction)", "category": "dsa",
     "keywords": ["fast slow pointer", "fast and slow", "remove duplicates", "move zeros"],
     "description": "Slow + fast pointers both starting from the left."},
    {"id": "palindrome", "name": "Palindrome Check", "category": "dsa",
     "keywords": ["palindrome"],
     "description": "Two pointers converging from each end of a string."},
    {"id": "container-water", "name": "Container With Most Water", "category": "dsa",
     "keywords": ["container with most water", "container water", "max water"],
     "description": "Two-pointer sweep to find the rectangle of maximum area."},
    # ── DSA: sliding window ───────────────────────────────────────
    {"id": "sliding-window", "name": "Sliding Window", "category": "dsa",
     "keywords": ["sliding window", "longest substring", "longest no repeat", "longest unique"],
     "description": "Expanding/contracting window with a hashmap counter."},
    # ── DSA: hashing ──────────────────────────────────────────────
    {"id": "two-sum", "name": "Two Sum (HashMap)", "category": "dsa",
     "keywords": ["two sum", "twosum", "2 sum", "pair sum"],
     "description": "Iterate the array; for each value v, check if (target − v) is already in the hashmap."},
    {"id": "frequency-count", "name": "Frequency Count", "category": "dsa",
     "keywords": ["frequency count", "frequency map", "count occurrences", "majority element"],
     "description": "Walk the array, accumulating counts of each value in a hashmap."},
    {"id": "anagram-check", "name": "Anagram Check", "category": "dsa",
     "keywords": ["anagram", "valid anagram"],
     "description": "Increment for letters in s, decrement for letters in t — all zero means anagram."},
    # ── DSA: stacks & queues ──────────────────────────────────────
    {"id": "monotonic-stack", "name": "Monotonic Stack", "category": "dsa",
     "keywords": ["monotonic stack", "next greater element", "daily temperatures"],
     "description": "Stack maintains a monotonic invariant; pops on new violations."},
    {"id": "stack-queue", "name": "Stack & Queue", "category": "dsa",
     "keywords": ["stack operations", "queue operations", "lifo", "fifo", "valid parentheses"],
     "description": "Animated push/pop or enqueue/dequeue operations."},
    # ── DSA: prefix / running sums ────────────────────────────────
    {"id": "prefix-sum", "name": "Prefix Sum", "category": "dsa",
     "keywords": ["prefix sum", "cumulative sum", "running total"],
     "description": "Build a cumulative array; subarray sums become O(1) range queries."},
    {"id": "kadanes", "name": "Kadane's Algorithm", "category": "dsa",
     "keywords": ["kadane", "kadanes", "maximum subarray", "max subarray sum", "largest contiguous"],
     "description": "Running max-subarray sum — keep a current sum and a best-so-far."},
    # ── DSA: linked lists ─────────────────────────────────────────
    {"id": "reverse-linked-list", "name": "Reverse Linked List", "category": "dsa",
     "keywords": ["reverse linked list", "reverse list", "reverse a linked list"],
     "description": "Three-pointer walk: prev, curr, next — flip each pointer in turn."},
    {"id": "linked-list-middle", "name": "Find Middle of Linked List", "category": "dsa",
     "keywords": ["middle of linked list", "find middle", "fast slow linked list"],
     "description": "Slow + fast pointer technique for finding the middle node."},
    {"id": "merge-sorted-lists", "name": "Merge Two Sorted Lists", "category": "dsa",
     "keywords": ["merge two sorted lists", "merge sorted lists", "merge linked lists"],
     "description": "Stitch two sorted linked lists together with a single pass."},
    # ── DSA: trees ────────────────────────────────────────────────
    {"id": "tree-bfs", "name": "Tree BFS (Level Order)", "category": "dsa",
     "keywords": ["tree bfs", "level order traversal", "breadth first tree"],
     "description": "Visit nodes level by level using a queue."},
    {"id": "tree-dfs", "name": "Tree DFS", "category": "dsa",
     "keywords": ["tree dfs", "depth first tree", "depth-first tree"],
     "description": "Recursive depth-first walk through a binary tree."},
    {"id": "tree-inorder", "name": "Inorder Traversal", "category": "dsa",
     "keywords": ["inorder traversal", "in-order traversal"],
     "description": "Left subtree → root → right subtree."},
    {"id": "trie", "name": "Trie", "category": "dsa",
     "keywords": ["trie", "prefix tree", "autocomplete"],
     "description": "Character-by-character insert and lookup in a prefix tree."},
    # ── DSA: graphs ───────────────────────────────────────────────
    {"id": "graph-bfs", "name": "Graph BFS", "category": "dsa",
     "keywords": ["graph bfs", "breadth first search", "shortest path unweighted"],
     "description": "BFS frontier expansion across a graph from a source node."},
    {"id": "graph-dfs", "name": "Graph DFS", "category": "dsa",
     "keywords": ["graph dfs", "depth first search graph"],
     "description": "DFS stack-based traversal through a graph."},
    {"id": "dijkstra", "name": "Dijkstra's Shortest Path", "category": "dsa",
     "keywords": ["dijkstra", "shortest path", "weighted shortest path", "network delay"],
     "description": "Greedy edge-relaxation on a weighted graph."},
    {"id": "union-find", "name": "Union Find (Disjoint Set)", "category": "dsa",
     "keywords": ["union find", "union-find", "disjoint set", "connected components"],
     "description": "Parent[] array + union/find operations on a disjoint-set forest."},
    # ── DSA: grid ─────────────────────────────────────────────────
    {"id": "grid-bfs", "name": "Grid BFS", "category": "dsa",
     "keywords": ["grid bfs", "shortest path on grid", "flood fill", "number of islands", "matrix bfs"],
     "description": "BFS over a 2D grid — frontier expands from start until target is reached."},
    # ── DSA: heaps ────────────────────────────────────────────────
    {"id": "heap-ops", "name": "Heap (Priority Queue)", "category": "dsa",
     "keywords": ["heap", "priority queue", "min heap", "max heap", "k largest", "k smallest", "top k"],
     "description": "Push/pop with sift up/down on a binary heap."},
    # ── DSA: intervals ────────────────────────────────────────────
    {"id": "merge-intervals", "name": "Merge Intervals", "category": "dsa",
     "keywords": ["merge intervals", "interval merging", "overlapping intervals", "meeting rooms"],
     "description": "Sort by start, sweep left-to-right merging overlaps."},
    # ── DSA: dynamic programming (1D) ─────────────────────────────
    {"id": "fibonacci-dp", "name": "Fibonacci (DP)", "category": "dsa",
     "keywords": ["fibonacci dp", "fibonacci dynamic", "fib dp"],
     "description": "Bottom-up Fibonacci: each cell = sum of the previous two."},
    {"id": "climbing-stairs", "name": "Climbing Stairs", "category": "dsa",
     "keywords": ["climbing stairs", "climb stairs", "staircase ways"],
     "description": "Number of distinct paths to step n: dp[i] = dp[i-1] + dp[i-2]."},
    {"id": "house-robber", "name": "House Robber", "category": "dsa",
     "keywords": ["house robber", "rob houses"],
     "description": "dp[i] = max(dp[i-1], dp[i-2] + nums[i]) — non-adjacent maximum."},
    # ── DSA: dynamic programming (2D) ─────────────────────────────
    {"id": "lcs", "name": "Longest Common Subsequence", "category": "dsa",
     "keywords": ["longest common subsequence", "lcs"],
     "description": "2D DP table over two strings; arrows show dependencies."},
    {"id": "edit-distance", "name": "Edit Distance", "category": "dsa",
     "keywords": ["edit distance", "levenshtein"],
     "description": "Min insert/delete/replace operations to transform one string into another."},
    {"id": "unique-paths", "name": "Unique Paths", "category": "dsa",
     "keywords": ["unique paths", "grid paths", "robot paths"],
     "description": "Count distinct paths from top-left to bottom-right of a grid."},
    # ── DSA: backtracking ─────────────────────────────────────────
    {"id": "subsets", "name": "Subsets", "category": "dsa",
     "keywords": ["subsets", "power set", "all subsets"],
     "description": "Decision tree: include or skip each element."},
    {"id": "permutations", "name": "Permutations", "category": "dsa",
     "keywords": ["permutations", "all permutations"],
     "description": "Decision tree exploring every ordering of the input set."},
    # ── DSA: design ───────────────────────────────────────────────
    {"id": "lru-cache", "name": "LRU Cache", "category": "dsa",
     "keywords": ["lru cache", "least recently used", "design lru"],
     "description": "HashMap + doubly-linked list with eviction on capacity overflow."},
    {"id": "segment-tree", "name": "Segment Tree", "category": "dsa",
     "keywords": ["segment tree", "range query tree", "range sum tree"],
     "description": "Build + range query on a segment tree."},
    # ── Calculus ──────────────────────────────────────────────────
    {"id": "chain-rule", "name": "Chain Rule", "category": "calculus",
     "keywords": ["chain rule", "composite derivative", "f(g(x))"],
     "description": "Derivative of nested functions, layer by layer."},
    {"id": "derivative-power-rule", "name": "Power Rule", "category": "calculus",
     "keywords": ["power rule", "derivative of x^n"],
     "description": "Why d/dx[x^n] = n·x^(n-1)."},
    {"id": "limit", "name": "Limit", "category": "calculus",
     "keywords": ["limit of f", "limit as x approaches", "lim x", "one-sided limit"],
     "description": "Watch f(x) approach a limit point from both sides."},
    {"id": "critical-points", "name": "Critical Points", "category": "calculus",
     "keywords": ["critical points", "critical point", "maxima minima", "extrema", "local max"],
     "description": "Local max, min, and inflection points marked on a curve."},
    {"id": "riemann-sum", "name": "Riemann Sum", "category": "calculus",
     "keywords": ["riemann sum", "rectangles under curve", "left riemann", "right riemann"],
     "description": "Approximate area under a curve with N rectangles."},
    {"id": "ftc", "name": "Fundamental Theorem of Calculus", "category": "calculus",
     "keywords": ["fundamental theorem of calculus", "ftc", "first fundamental theorem"],
     "description": "The connection between differentiation and integration."},
    {"id": "area-between-curves", "name": "Area Between Curves", "category": "calculus",
     "keywords": ["area between curves", "area between two curves", "region between curves"],
     "description": "Area enclosed between two curves over an interval."},
    {"id": "average-value", "name": "Average Value of a Function", "category": "calculus",
     "keywords": ["average value of a function", "mean value of a function", "function average"],
     "description": "Mean value of f over [a, b] shown as a horizontal line."},
    {"id": "arc-length", "name": "Arc Length", "category": "calculus",
     "keywords": ["arc length", "length of a curve"],
     "description": "Length of a curve approximated by line segments."},
    {"id": "u-substitution", "name": "u-Substitution", "category": "calculus",
     "keywords": ["u substitution", "u-substitution", "u sub", "integration by substitution"],
     "description": "Integration by substitution, walked through step by step."},
    {"id": "integration-by-parts", "name": "Integration by Parts", "category": "calculus",
     "keywords": ["integration by parts", "by parts", "ibp"],
     "description": "Integration by parts: ∫u dv = uv − ∫v du."},
    {"id": "improper-integral", "name": "Improper Integral", "category": "calculus",
     "keywords": ["improper integral", "infinite integral", "integral to infinity"],
     "description": "Integrals with infinite bounds or discontinuities."},
    {"id": "volume-revolution", "name": "Volume of Revolution (Disk)", "category": "calculus",
     "keywords": ["volume of revolution", "disk method", "solid of revolution"],
     "description": "Volume of a solid formed by rotating f(x) around the x-axis."},
    {"id": "washer-method", "name": "Washer Method", "category": "calculus",
     "keywords": ["washer method", "disk method"],
     "description": "Volume of solids of revolution using stacked washers."},
    {"id": "shell-method", "name": "Cylindrical Shell Method", "category": "calculus",
     "keywords": ["cylindrical shell", "shell method", "shells"],
     "description": "Volume by unwrapping concentric cylindrical shells."},
    {"id": "cross-section", "name": "Volume by Cross Sections", "category": "calculus",
     "keywords": ["volume by cross sections", "cross section", "known cross sections"],
     "description": "Volume of a solid built from known cross-sections."},
    {"id": "taylor-series", "name": "Taylor Series", "category": "calculus",
     "keywords": ["taylor series", "taylor polynomial", "maclaurin series"],
     "description": "Polynomial approximation of f(x) centered at a point."},
    {"id": "sequence", "name": "Recursive Sequence", "category": "calculus",
     "keywords": ["recursive sequence", "iteration sequence", "recurrence relation"],
     "description": "Plot terms of a recursive sequence aₙ = f(aₙ₋₁)."},
    {"id": "cobweb", "name": "Cobweb Diagram", "category": "calculus",
     "keywords": ["cobweb diagram", "cobweb plot", "fixed point iteration"],
     "description": "Visualize fixed-point iteration on a single function."},
    # ── Algebra ───────────────────────────────────────────────────
    {"id": "linear-function", "name": "Linear Function", "category": "calculus",
     "keywords": ["linear function", "y = mx + b", "slope intercept"],
     "description": "Plot a linear function with slope and intercept."},
    {"id": "quadratic", "name": "Quadratic Function", "category": "calculus",
     "keywords": ["quadratic function", "parabola", "vertex form", "ax^2 + bx + c"],
     "description": "Parabola with vertex, axis of symmetry, and roots marked."},
    {"id": "inequality", "name": "Inequality", "category": "calculus",
     "keywords": ["graph inequality", "linear inequality", "polynomial inequality"],
     "description": "Region of x satisfying an inequality."},
    {"id": "exponential-function", "name": "Exponential Function", "category": "calculus",
     "keywords": ["exponential function", "exponential growth", "exponential decay", "e^x"],
     "description": "Exponential growth or decay with key points highlighted."},
    {"id": "function-transformation", "name": "Function Transformation", "category": "calculus",
     "keywords": ["function transformation", "graph transformation", "shift scale reflect"],
     "description": "Side-by-side comparison of base and transformed functions."},
    # ── Arithmetic ────────────────────────────────────────────────
    {"id": "fraction", "name": "Fractions", "category": "arithmetic",
     "keywords": ["fractions", "compare fractions", "add fractions", "fraction strip"],
     "description": "Fraction visualization: represent, compare, add, or subtract."},
    # ── Trig ──────────────────────────────────────────────────────
    {"id": "trig-unit-circle", "name": "Trig Unit Circle", "category": "calculus",
     "keywords": ["unit circle", "trig unit circle", "sine cosine projection"],
     "description": "Unit circle with rotating angle and sine/cosine projections."},
    # ── 3D / Multivariable ────────────────────────────────────────
    {"id": "surface-plot", "name": "3D Surface Plot", "category": "calculus",
     "keywords": ["3d surface", "surface plot", "z = f(x,y)", "two variable function"],
     "description": "3D surface plot of z = f(x, y)."},
    {"id": "contour", "name": "Contour Map", "category": "calculus",
     "keywords": ["contour map", "contour plot", "level curves"],
     "description": "Contour map of a 2D function with level curves."},
    {"id": "vector-field", "name": "Vector Field", "category": "calculus",
     "keywords": ["vector field", "vector flow"],
     "description": "2D vector field with arrows showing direction at each point."},
    {"id": "partial-derivative", "name": "Partial Derivative", "category": "calculus",
     "keywords": ["partial derivative", "partial derivatives", "∂f/∂x", "df/dx of f(x,y)"],
     "description": "Partial derivative shown as a slice of the surface."},
]

_MIME_FROM_EXT = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "png": "image/png", "webp": "image/webp",
    "pdf": "application/pdf",
}
_ALLOWED_MIMES = frozenset(_MIME_FROM_EXT.values())

# ── Share storage (file-backed dict keyed by 8-char base62 short codes) ──
_SHARES_PATH = os.path.join(os.path.dirname(__file__), "shares.json")
_SHARES_LOCK = threading.Lock()
_SHARE_ALPHABET = string.ascii_letters + string.digits  # base62
_SHARE_CODE_LEN = 8


def _load_shares() -> dict:
    if not os.path.exists(_SHARES_PATH):
        return {}
    try:
        with open(_SHARES_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _save_shares(shares: dict) -> None:
    tmp = _SHARES_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(shares, fh)
    os.replace(tmp, _SHARES_PATH)  # atomic on both POSIX and Windows


def _new_share_code(existing: dict) -> str:
    while True:
        code = "".join(secrets.choice(_SHARE_ALPHABET) for _ in range(_SHARE_CODE_LEN))
        if code not in existing:
            return code


_TARGET_MINUTES_MIN = 0.5
_TARGET_MINUTES_MAX = 10.0
_TARGET_MINUTES_DEFAULT = 1.5


def _parse_target_minutes(body: dict):
    """Read body['target_minutes'] with default + bounds.

    Returns the float on success, or a (jsonify, status) tuple on validation
    failure so the caller can `return` it directly.
    """
    raw = body.get("target_minutes", _TARGET_MINUTES_DEFAULT)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return jsonify({"error": "target_minutes must be a number"}), 400
    if not (_TARGET_MINUTES_MIN <= value <= _TARGET_MINUTES_MAX):
        return jsonify({
            "error": f"target_minutes must be in [{_TARGET_MINUTES_MIN}, {_TARGET_MINUTES_MAX}]"
        }), 400
    return value


def _init_sentry() -> None:
    """Initialize Sentry if SENTRY_DSN is set AND sentry-sdk is installed.

    Both conditions must hold — keeps Sentry strictly opt-in: dev runs and CI
    don't need the package, prod opts in by setting the env var.
    """
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
    except ImportError:
        print("[sentry] SENTRY_DSN set but sentry-sdk not installed; skipping init")
        return
    try:
        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_RATE", "0.1")),
            environment=os.environ.get("LUMEN_ENV", "dev"),
            send_default_pii=False,
        )
        print("[sentry] initialized backend SDK")
    except Exception as exc:
        print(f"[sentry] init failed: {exc}")


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = testing
    _init_sentry()
    CORS(app)

    # Item #18 — per-IP rate limit on heavy endpoints. 10/day anonymous per
    # IP by default; disabled in tests so the existing suite isn't perturbed.
    # Override via LUMEN_RATE_LIMIT="0" to disable, or any integer to override.
    _rate_limit_max = 0 if testing else int(
        os.environ.get("LUMEN_RATE_LIMIT", "10"),
    )
    _rate_limit_window = int(
        os.environ.get("LUMEN_RATE_LIMIT_WINDOW_SECONDS", "86400"),
    )

    def _enforce_rate_limit():
        """Decorator-less guard returning 429 when exceeded; else None to continue.

        Heavy endpoints call this at the top of their handler. We don't use a
        before_request hook because most endpoints (health, status polls,
        media) should NOT be limited.
        """
        from rate_limit import check_rate_limit
        ip = (request.headers.get("X-Forwarded-For", request.remote_addr) or
              "unknown").split(",")[0].strip()
        allowed, retry_after = check_rate_limit(
            key=f"ip:{ip}",
            max_requests=_rate_limit_max,
            window_seconds=_rate_limit_window,
        )
        if allowed:
            return None
        resp = jsonify({
            "error": "rate limit exceeded",
            "retry_after_seconds": retry_after,
        })
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry_after)
        return resp

    # ── existing endpoints ────────────────────────────────────────

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/openapi.json")
    def openapi_json():
        """OpenAPI 3.1 schema — feed to `openapi-typescript` for typed clients."""
        from openapi_spec import build_openapi_spec
        return jsonify(build_openapi_spec())

    @app.get("/topics")
    def topics():
        return jsonify({"topics": _TOPICS})

    @app.post("/breakdown")
    def breakdown():
        body = request.get_json(silent=True) or {}
        topic_name = body.get("topicName", "").strip()
        topic_description = body.get("topicDescription", "").strip()
        problem = body.get("problem", "").strip()
        if not topic_name:
            return jsonify({"error": "topicName is required"}), 400
        sections = explain_problem(problem, topic_name, topic_description)
        return jsonify({"sections": sections})

    @app.post("/ask")
    def ask():
        limited = _enforce_rate_limit()
        if limited is not None:
            return limited
        body = request.get_json(silent=True) or {}
        question = body.get("question", "").strip()
        if not question:
            return jsonify({"error": "question is required"}), 400
        domain = classify_domain(question)
        try:
            lesson = plan_dsa(question) if domain == "dsa" else plan_math(question)
        except ValueError as e:
            app.logger.warning("planner ValueError on q=%r: %s", question[:120], e)
            return jsonify({"error": "Could not understand the question. Try rephrasing it."}), 422
        except Exception:
            app.logger.exception("planner unexpected error on q=%r", question[:120])
            return jsonify({"error": "Internal planning error. Please try again."}), 422
        job_id = submit_lesson(lesson.steps)
        return jsonify({
            "job_id":      job_id,
            "concept":     lesson.concept,
            "domain":      domain,
            "scene_count": len(lesson.steps),
        }), 202

    @app.post("/render")
    def render():
        # NOTE: /render is intentionally NOT rate-limited — the frontend's
        # prerender warmer hits it ~10× on first page load. The expensive
        # LLM-backed endpoints (/ask, /api/direct-lesson*) carry the quota.
        body = request.get_json(silent=True) or {}
        scene = body.get("scene")
        params = body.get("params", {})
        if not scene:
            return jsonify({"error": "scene is required"}), 400
        # Route through submit_lesson so single-scene renders share the
        # content-hash cache (so /prerender on boot warms /render too).
        step = StepPlan(tool=scene, params=params, caption=params.get("caption", ""))
        job_id = submit_lesson([step])
        return jsonify({"job_id": job_id}), 202

    @app.post("/api/render-lesson")
    def api_render_lesson():
        """Submit a multi-scene lesson. Each step gets rendered (in parallel)
        and the outputs are stitched into one video by submit_lesson(). The
        frontend gets back one job_id, polls /status, and receives one
        stitched video URL — the multi-scene-ness is opaque to playback.
        """
        body = request.get_json(silent=True) or {}
        steps_data = body.get("steps", [])
        if not isinstance(steps_data, list) or not steps_data:
            return jsonify({"error": "steps (non-empty list) required"}), 400
        if len(steps_data) > 6:
            return jsonify({"error": "max 6 steps per lesson"}), 400

        try:
            steps = []
            for s in steps_data:
                scene_key = s.get("scene")
                params = s.get("params", {}) or {}
                if not scene_key:
                    return jsonify({"error": "each step requires a scene"}), 400
                steps.append(StepPlan(
                    tool=scene_key,
                    params=params,
                    caption=s.get("caption", "") or params.get("caption", ""),
                ))
        except Exception as exc:
            app.logger.warning("render-lesson bad shape: %s", exc)
            return jsonify({"error": "invalid step shape", "detail": str(exc)}), 400

        job_id = submit_lesson(steps)
        return jsonify({"job_id": job_id}), 202

    @app.get("/status/<job_id>")
    def status(job_id):
        job = get_job(job_id)
        if job is None:
            return jsonify({"error": "job not found"}), 404
        return jsonify(job)

    @app.get("/media/<path:filename>")
    def serve_media(filename):
        media_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), "media"))
        target = os.path.realpath(os.path.join(media_dir, filename))
        if not target.startswith(media_dir + os.sep):
            return jsonify({"error": "forbidden"}), 403
        response = send_from_directory(media_dir, filename)
        # Lesson MP4s are content-addressable (uuid in filename) — they never
        # change once written, so we can mark them immutable for a year. This
        # lets any CDN in front (Cloudflare etc.) cache them aggressively. Job
        # temp files under /jobs/ are short-lived; just don't cache.
        if filename.startswith("lessons/"):
            response.headers["Cache-Control"] = (
                "public, max-age=31536000, immutable"
            )
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response

    # ── Gemini-backed /api/* endpoints ───────────────────────────

    @app.get("/api/topics")
    def api_topics():
        return jsonify({"topics": _TOPICS})

    @app.post("/api/ocr")
    def api_ocr():
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files["file"]
        if not file.filename:
            return jsonify({"error": "No file selected"}), 400

        mime_type = file.mimetype or "application/octet-stream"
        if mime_type == "application/octet-stream":
            ext = (file.filename or "").rsplit(".", 1)[-1].lower()
            mime_type = _MIME_FROM_EXT.get(ext, mime_type)
        if mime_type not in _ALLOWED_MIMES:
            return jsonify({"error": f"Unsupported file type: {mime_type}"}), 400

        try:
            file_bytes = file.read()
            prompt = (
                "Extract all text from this image or document exactly as it appears. "
                "Preserve line breaks. Do not summarize, do not add commentary, just transcribe."
            )
            contents = [prompt, genai_types.Part.from_bytes(data=file_bytes, mime_type=mime_type)]
            response = call_gemini(contents)
            return jsonify({"text": response.text})
        except Exception as exc:
            app.logger.exception("OCR failed")
            return jsonify({"error": "OCR failed", "detail": str(exc)}), 500

    @app.post("/api/format-note")
    def api_format_note():
        body = request.get_json(silent=True) or {}
        raw_text = body.get("rawText", "").strip()
        if not raw_text:
            return jsonify({"error": "rawText is required"}), 400

        schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "html":  {"type": "string"},
            },
            "required": ["title", "html"],
        }
        prompt = (
            "You are turning a raw note transcription into a clean, well-structured "
            "study note. Return a JSON object with:\n"
            "- title: a short descriptive title (max 60 characters)\n"
            "- html: well-structured semantic HTML\n\n"
            "HTML rules:\n"
            "- Allowed tags ONLY: <h2>, <h3>, <p>, <ul>, <ol>, <li>, <strong>, <em>\n"
            "- No CSS, no scripts, no inline styles, no class attributes, no <div>/<span>.\n"
            "- Structure with clear visual hierarchy:\n"
            "    * Open with one short overview paragraph (1–2 sentences).\n"
            "    * Use <h2> for major sections (e.g. Definitions, Examples, Steps, Notes).\n"
            "    * Use <h3> for sub-sections inside a major section.\n"
            "    * Keep prose paragraphs short — 2 to 4 sentences max — so the note "
            "      is scannable.\n"
            "- Use <strong> liberally to highlight:\n"
            "    * Key terms on first definition (e.g. <strong>derivative</strong>).\n"
            "    * Names of theorems, methods, formulas, or rules.\n"
            "    * Important numerical values, results, and final answers.\n"
            "    * Anything the reader should remember.\n"
            "- Use <em> sparingly for emphasis or contrast within a sentence.\n"
            "- Use <ul> for unordered lists (properties, characteristics, examples).\n"
            "- Use <ol> for ordered lists (steps, procedures, sequential reasoning).\n"
            "- Wrap each list item in its own <li>; do NOT merge multiple steps into one <li>.\n"
            "- Each section should have its own heading + content; do not pile everything "
            "  into one <h2> block. Aim for 2–5 sections.\n"
            "- Preserve the original meaning; reorganize and clarify, but do not invent "
            "  facts or add content not present in the source.\n\n"
            f"Source text:\n{raw_text}"
        )
        try:
            response = call_gemini(prompt, response_schema=schema)
            return jsonify(json.loads(response.text))
        except Exception as exc:
            app.logger.exception("format-note failed")
            return jsonify({"error": "format-note failed", "detail": str(exc)}), 500

    @app.post("/api/parse-problem")
    def api_parse_problem():
        body = request.get_json(silent=True) or {}
        raw_text = body.get("rawText", "").strip()
        topics_list = body.get("topics", [])
        if not raw_text:
            return jsonify({"error": "rawText is required"}), 400

        schema = {
            "type": "object",
            "properties": {
                "problem": {"type": "string"},
                "topicId": {"type": ["string", "null"]},
            },
            "required": ["problem", "topicId"],
        }
        topics_summary = "\n".join(
            f'- id: {t.get("id")}, name: {t.get("name")}, '
            f'keywords: {", ".join(t.get("keywords", []))}'
            for t in topics_list
        )
        prompt = (
            "Identify which of the available animation topics best matches this student problem. "
            "Return a JSON object with:\n"
            "- problem: cleaned-up problem statement\n"
            "- topicId: the id of the matching topic, or null if none match\n\n"
            f"Problem:\n{raw_text}\n\n"
            f"Available topics:\n{topics_summary or '(none provided)'}"
        )
        try:
            response = call_gemini(prompt, response_schema=schema)
            return jsonify(json.loads(response.text))
        except Exception as exc:
            app.logger.exception("parse-problem failed")
            return jsonify({"error": "parse-problem failed", "detail": str(exc)}), 500

    @app.post("/api/parse-problem-v2")
    def api_parse_problem_v2():
        """Universal paste-to-render parser. Classifies the input as math or
        DSA and routes to the matching parser. Returns a unified shape with
        a `domain` field; math results include `steps`, DSA results include
        `pseudocode` + `step_lines`.
        """
        body = request.get_json(silent=True) or {}
        raw_text = body.get("rawText", "").strip()
        if not raw_text:
            return jsonify({"error": "rawText is required"}), 400

        try:
            domain = classify_domain(raw_text)
        except Exception:
            app.logger.exception("classifier failed; defaulting to dsa")
            domain = "dsa"

        try:
            if domain == "math":
                parsed = parse_math(raw_text)
            else:
                parsed = parse_leetcode_problem(raw_text)
        except ValueError as exc:
            app.logger.warning("parse-problem-v2 rejected (%s): %s", domain, exc)
            return jsonify({"error": "could not parse problem", "detail": str(exc)}), 422
        except Exception as exc:
            app.logger.exception("parse-problem-v2 failed (%s)", domain)
            return jsonify({"error": "parse-problem-v2 failed", "detail": str(exc)}), 500

        payload = parsed.model_dump()
        payload["domain"] = domain
        return jsonify(payload)

    @app.post("/api/fetch-leetcode")
    def api_fetch_leetcode():
        """Fetch a LeetCode problem statement by URL via their public GraphQL.
        Frontend can paste a leetcode.com/problems/<slug>/ URL and skip the
        copy-paste-the-prose dance.
        """
        import re as _re
        import requests as _requests
        from bs4 import BeautifulSoup as _BS

        body = request.get_json(silent=True) or {}
        url = (body.get("url") or "").strip()
        m = _re.match(r"https?://(?:www\.)?leetcode\.com/problems/([a-z0-9-]+)/?",
                      url, _re.IGNORECASE)
        if not m:
            return jsonify({"error": "not a LeetCode problem URL"}), 400
        slug = m.group(1).lower()

        gql = {
            "query": """query questionData($titleSlug: String!) {
                question(titleSlug: $titleSlug) {
                    title
                    content
                    sampleTestCase
                    difficulty
                }
            }""",
            "variables": {"titleSlug": slug},
            "operationName": "questionData",
        }
        try:
            resp = _requests.post(
                "https://leetcode.com/graphql",
                json=gql,
                headers={
                    "Content-Type": "application/json",
                    # LeetCode rejects requests with default Python user-agent
                    "User-Agent": "Mozilla/5.0 (compatible; Lumen/1.0)",
                    "Referer": f"https://leetcode.com/problems/{slug}/",
                },
                timeout=10,
            )
            data = resp.json().get("data", {}).get("question")
            if not data:
                return jsonify({"error": f"problem '{slug}' not found"}), 404
            # `content` is HTML; strip tags to plain text the parser can chew
            text = _BS(data["content"] or "", "html.parser").get_text("\n")
            # Collapse runs of blank lines for readability
            text = _re.sub(r"\n\n\n+", "\n\n", text).strip()
            return jsonify({
                "title":       data.get("title", slug),
                "rawText":     text,
                "sampleInput": data.get("sampleTestCase", ""),
                "difficulty":  data.get("difficulty", ""),
            })
        except _requests.Timeout:
            return jsonify({"error": "LeetCode timed out"}), 504
        except Exception as exc:
            app.logger.exception("fetch-leetcode failed")
            return jsonify({"error": "fetch failed", "detail": str(exc)}), 502

    @app.post("/api/parse-followup")
    def api_parse_followup():
        """Conversational follow-up parsing. Frontend sends:
            { prior: ParsedProblem, followUp: str }
        Backend stitches `prior` into a context-rich preamble + the
        follow-up, classifies the combined text, routes to the matching
        parser. Stateless — frontend keeps the conversation array.
        """
        body = request.get_json(silent=True) or {}
        prior = body.get("prior") or {}
        follow_up = (body.get("followUp") or "").strip()
        if not follow_up:
            return jsonify({"error": "followUp is required"}), 400

        # Build a rich raw_text that the existing parsers can consume.
        # We expose: prior title, scene, params (json), and any pseudocode/
        # steps so the model can re-derive a focused follow-up.
        prior_lines = []
        if prior.get("title"):
            prior_lines.append(f"Previous title: {prior['title']}")
        if prior.get("scene"):
            prior_lines.append(f"Previous scene: {prior['scene']}")
        if prior.get("params"):
            try:
                prior_lines.append(f"Previous params: {json.dumps(prior['params'])}")
            except (TypeError, ValueError):
                pass
        if prior.get("pseudocode"):
            prior_lines.append(f"Previous pseudocode:\n{prior['pseudocode']}")
        if prior.get("steps"):
            steps_str = "; ".join(str(s) for s in prior["steps"][:5])
            prior_lines.append(f"Previous steps: {steps_str}")

        preamble = ""
        if prior_lines:
            preamble = (
                "The user already saw this problem visualized:\n"
                + "\n".join(f"  - {ln}" for ln in prior_lines)
                + "\n\nThey now ask:\n"
            )
        rich_text = preamble + follow_up + (
            "\n\nCommon follow-up patterns:\n"
            "- 'Now with [array]' / 'Try [values]' → same scene, replace inputs\n"
            "- 'Show me with X' / 'Compare with X' → switch scene/algorithm\n"
            "- 'Slower' / 'Step by step' → emit lesson_steps for finer breakdown\n"
            "- 'Explain step N' → keep scene, focus that segment\n"
            "- 'What if target was Y' → replace target, re-derive\n"
            "Re-parse with the follow-up applied. Return the same JSON shape."
        )

        try:
            domain = classify_domain(rich_text)
        except Exception:
            app.logger.exception("classifier failed; defaulting to dsa")
            domain = "dsa"

        try:
            if domain == "math":
                parsed = parse_math(rich_text)
            else:
                parsed = parse_leetcode_problem(rich_text)
        except ValueError as exc:
            app.logger.warning("parse-followup rejected (%s): %s", domain, exc)
            return jsonify({"error": "could not parse follow-up", "detail": str(exc)}), 422
        except Exception as exc:
            app.logger.exception("parse-followup failed (%s)", domain)
            return jsonify({"error": "parse-followup failed", "detail": str(exc)}), 500

        payload = parsed.model_dump()
        payload["domain"] = domain
        return jsonify(payload)

    @app.post("/api/parse-leetcode")
    def api_parse_leetcode():
        """Parse a pasted LeetCode problem into a renderable {scene, params}.

        Frontend can POST the returned scene+params straight to /render, skipping
        the planner. Use this when the user pastes a full problem statement
        (with example inputs) rather than a short conversational question.
        """
        body = request.get_json(silent=True) or {}
        raw_text = body.get("rawText", "").strip()
        if not raw_text:
            return jsonify({"error": "rawText is required"}), 400
        try:
            parsed = parse_leetcode_problem(raw_text)
        except ValueError as exc:
            app.logger.warning("parse-leetcode rejected: %s", exc)
            return jsonify({"error": "could not parse problem", "detail": str(exc)}), 422
        except Exception as exc:
            app.logger.exception("parse-leetcode failed")
            return jsonify({"error": "parse-leetcode failed", "detail": str(exc)}), 500
        return jsonify(parsed.model_dump())

    @app.post("/api/breakdown")
    def api_breakdown():
        body = request.get_json(silent=True) or {}
        problem = body.get("problem", "").strip()
        topic = body.get("topic") or {}
        topic_name = topic.get("name", "").strip()
        topic_description = topic.get("description", "").strip()
        if not topic_name:
            return jsonify({"error": "topic.name is required"}), 400

        schema = {
            "type": "object",
            "properties": {
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "body":  {"type": "string"},
                        },
                        "required": ["label", "body"],
                    },
                },
            },
            "required": ["sections"],
        }
        prompt = (
            f"Break down this problem step by step in the context of {topic_name}.\n"
            f"Topic: {topic_name} — {topic_description}\n"
            f"Problem: {problem or '(general explanation of the topic)'}\n\n"
            "Return a JSON object with a 'sections' array of 3-5 objects, each with:\n"
            "- label: short title (1-4 words)\n"
            "- body: 1-2 sentence explanation\n\n"
            f"Be specific about what each part represents in the context of {topic_name}."
        )
        try:
            response = call_gemini(prompt, response_schema=schema)
            return jsonify(json.loads(response.text))
        except Exception as exc:
            app.logger.exception("api/breakdown failed")
            return jsonify({"error": "breakdown failed", "detail": str(exc)}), 500

    @app.post("/api/quiz")
    def api_quiz():
        """Generate 1-2 multiple-choice questions testing comprehension of a
        problem the user just watched visualized. Frontend posts the prior
        ParsedProblem; we return:
            { questions: [{q, options: [4 strings], correct: int, why: str}] }
        """
        body = request.get_json(silent=True) or {}
        prior = body.get("prior") or {}
        title = (prior.get("title") or "").strip()
        scene = (prior.get("scene") or "").strip()
        if not title and not scene:
            return jsonify({"error": "prior.title or prior.scene is required"}), 400

        # Build a description of what the student just saw
        context_lines = []
        if title:
            context_lines.append(f"Title: {title}")
        if scene:
            context_lines.append(f"Scene type: {scene}")
        if prior.get("params"):
            try:
                context_lines.append(f"Inputs: {json.dumps(prior['params'])[:400]}")
            except (TypeError, ValueError):
                pass
        if prior.get("pseudocode"):
            context_lines.append(f"Pseudocode:\n{prior['pseudocode']}")
        if prior.get("steps"):
            steps_str = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(prior["steps"][:6]))
            context_lines.append(f"Solution steps:\n{steps_str}")
        if prior.get("explanation"):
            context_lines.append(f"Explanation: {prior['explanation'][:400]}")

        schema = {
            "type": "object",
            "properties": {
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "q": {"type": "string"},
                            "options": {"type": "array", "items": {"type": "string"}},
                            "correct": {"type": "integer"},
                            "why": {"type": "string"},
                        },
                        "required": ["q", "options", "correct", "why"],
                    },
                },
            },
            "required": ["questions"],
        }

        prompt = (
            "You are writing a brief comprehension quiz for a student who just\n"
            "watched a visualization of the following problem:\n\n"
            + "\n".join(context_lines)
            + "\n\nGenerate exactly 2 multiple-choice questions that test whether\n"
            "the student understood the *key insight* of this algorithm or concept.\n"
            "Each question must have:\n"
            "- q: a clear question (one sentence)\n"
            "- options: exactly 4 plausible answer choices\n"
            "- correct: the 0-indexed position of the correct option\n"
            "- why: a 1-2 sentence explanation of why that answer is correct\n\n"
            "Make the questions test conceptual understanding (why does this work?\n"
            "what would change if X?), NOT trivia about specific values."
        )

        try:
            response = call_gemini(prompt, response_schema=schema)
            return jsonify(json.loads(response.text))
        except Exception as exc:
            app.logger.exception("api/quiz failed")
            return jsonify({"error": "quiz failed", "detail": str(exc)}), 500

    @app.post("/api/share")
    def api_share():
        """Persist a parsed problem under a short code so it can be re-opened
        via a shareable URL. Returns: {shareCode}."""
        body = request.get_json(silent=True) or {}
        parsed = body.get("parsed")
        if not isinstance(parsed, dict) or not parsed.get("scene"):
            return jsonify({"error": "parsed.scene is required"}), 400

        try:
            payload_size = len(json.dumps(parsed))
        except (TypeError, ValueError):
            return jsonify({"error": "parsed is not JSON-serializable"}), 400
        if payload_size > 50_000:
            return jsonify({"error": "payload too large (max 50 kB)"}), 413

        with _SHARES_LOCK:
            shares = _load_shares()
            code = _new_share_code(shares)
            shares[code] = parsed
            try:
                _save_shares(shares)
            except OSError as exc:
                app.logger.exception("share write failed")
                return jsonify({"error": "share storage unavailable",
                                "detail": str(exc)}), 500
        return jsonify({"shareCode": code})

    @app.get("/api/share/<code>")
    def api_share_get(code: str):
        """Look up a previously-shared parsed problem by short code."""
        if not code or len(code) != _SHARE_CODE_LEN:
            return jsonify({"error": "invalid share code"}), 400
        with _SHARES_LOCK:
            shares = _load_shares()
            parsed = shares.get(code)
        if parsed is None:
            return jsonify({"error": "share not found"}), 404
        return jsonify({"parsed": parsed})

    @app.post("/api/direct-lesson")
    def api_direct_lesson():
        """Lesson Director agent: async two-phase LLM → tool calls → DynamicScene render.

        Returns a job_id immediately; the agent runs in a background thread.
        Stage progression visible via /status/<id>:
            planning_narrative → building_scenes → queued → rendering_X_of_N
                              → stitching → done

        Request:  {
            "question": "Explain the sliding window technique",
            "style": "intuition_first"  # optional: intuition_first | rigor_first |
                                        #           socratic | speedrun
        }
        Response: { "job_id": "..." }   (202)
        """
        limited = _enforce_rate_limit()
        if limited is not None:
            return limited
        from agent.lesson_director import VALID_STYLES
        body = request.get_json(silent=True) or {}
        question = (body.get("question") or "").strip()
        if not question:
            return jsonify({"error": "question is required"}), 400
        style = body.get("style")
        if style is not None and style not in VALID_STYLES:
            return jsonify({
                "error": f"invalid style '{style}'",
                "valid": sorted(VALID_STYLES),
            }), 400
        target_minutes = _parse_target_minutes(body)
        if isinstance(target_minutes, tuple):
            return target_minutes  # (jsonify, status)
        job_id = submit_direct_lesson(question, style=style,
                                       target_minutes=target_minutes)
        return jsonify({"job_id": job_id}), 202

    @app.post("/api/direct-lesson-stream")
    def api_direct_lesson_stream():
        """SSE variant of /api/direct-lesson: streams progress events while
        the agent plans, then hands off to submit_lesson and returns a job_id
        for the frontend to poll /status on for the actual render.

        Item #11 regression target. Events emitted (text/event-stream):
            event: stage      data: planning_narrative
            event: narrative  data: <NarrativePlan JSON>
            event: stage      data: building_scenes
            event: scene_done data: {"index": N, "title": "..."}   (per scene)
            event: stage      data: queued
            event: job_id     data: <lesson_id>
            event: done       data: {}
            event: error      data: {"error": "..."}                 (on failure)
        """
        limited = _enforce_rate_limit()
        if limited is not None:
            return limited
        from agent.lesson_director import (
            VALID_STYLES, narrative_plan as _np, _build_scene_safe,
            _accumulate_elements,
        )
        from flask import Response
        import concurrent.futures
        body = request.get_json(silent=True) or {}
        question = (body.get("question") or "").strip()
        if not question:
            return jsonify({"error": "question is required"}), 400
        style = body.get("style")
        if style is not None and style not in VALID_STYLES:
            return jsonify({"error": "invalid style"}), 400
        target_minutes = _parse_target_minutes(body)
        if isinstance(target_minutes, tuple):
            return target_minutes

        def _sse(event: str, data) -> str:
            payload = data if isinstance(data, str) else json.dumps(data)
            return f"event: {event}\ndata: {payload}\n\n"

        def generate():
            try:
                yield _sse("stage", "planning_narrative")
                narrative = _np(question, style=style,
                                 target_minutes=target_minutes)
                yield _sse("narrative", narrative.model_dump())

                yield _sse("stage", "building_scenes")
                contexts = [""] + [sp.objective for sp in narrative.scenes[:-1]]
                carryover = _accumulate_elements(narrative.scenes)
                tool_call_lists = [None] * len(narrative.scenes)

                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    fut_to_idx = {
                        pool.submit(_build_scene_safe, question, sp,
                                    narrative.core_insight, contexts[i], 2,
                                    None, carryover[i]): i
                        for i, sp in enumerate(narrative.scenes)
                    }
                    completed_events = []
                    for fut in concurrent.futures.as_completed(fut_to_idx):
                        i = fut_to_idx[fut]
                        tool_call_lists[i] = fut.result()
                        completed_events.append(_sse("scene_done", {
                            "index": i,
                            "title": narrative.scenes[i].title,
                        }))
                    for ev in completed_events:
                        yield ev

                yield _sse("stage", "queued")

                steps = [
                    StepPlan(
                        tool="dynamic_lesson_step",
                        params={
                            "title": sp.title,
                            "tool_calls": [
                                {"tool": tc.tool, "args": tc.args} for tc in tcs
                            ],
                        },
                        caption=sp.objective,
                    )
                    for sp, tcs in zip(narrative.scenes, tool_call_lists)
                ]
                job_id = submit_lesson(steps)
                yield _sse("job_id", job_id)
                yield _sse("done", {})
            except Exception as exc:
                app.logger.exception("direct-lesson-stream failed")
                yield _sse("error", {"error": str(exc)})

        return Response(generate(), mimetype="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering if reversed
        })

    @app.post("/api/pin")
    def api_pin():
        """Protect a rendered video from LRU cleanup.

        Request:  { "jobId": "uuid" }
        Response: { "url": "/media/lessons/<id>.mp4" }
        """
        body = request.get_json(silent=True) or {}
        job_id = (body.get("jobId") or "").strip()
        if not job_id:
            return jsonify({"error": "jobId required"}), 400
        try:
            url = pin_video(job_id)
        except ValueError as exc:
            msg = str(exc)
            if "unknown" in msg:
                return jsonify({"error": msg}), 404
            return jsonify({"error": msg}), 409
        return jsonify({"url": url}), 200

    @app.delete("/api/pin/<job_id>")
    def api_unpin(job_id: str):
        """Remove pin protection. Idempotent."""
        unpin_video(job_id)
        return jsonify({"ok": True}), 200

    @app.get("/api/trace/<job_id>")
    def api_trace(job_id: str):
        """Return the render trace (LLM calls + stage timings) for a job."""
        from agent.trace import get_trace, load_trace
        active = get_trace(job_id)
        if active is not None:
            return jsonify({
                "job_id": active.job_id,
                "started_at": active.started_at,
                "finished_at": active.finished_at,
                "calls": [
                    {
                        "label": c.label, "model": c.model,
                        "elapsed_ms": c.elapsed_ms,
                        "prompt_chars": c.prompt_chars,
                        "response_chars": c.response_chars,
                        "prompt_tokens": c.prompt_tokens,
                        "completion_tokens": c.completion_tokens,
                        "error": c.error,
                    } for c in active.calls
                ],
                "stages": [
                    {"stage": s.stage, "elapsed_ms": s.elapsed_ms}
                    for s in active.stages
                ],
                "notes": list(active.notes),
                "total_calls": len(active.calls),
                "total_call_ms": active.total_call_ms,
            })
        # Fall back to disk
        on_disk = load_trace(job_id)
        if on_disk is None:
            return jsonify({"error": "trace not found"}), 404
        return jsonify(on_disk)

    return app


if __name__ == "__main__":
    # use_reloader=False: the dev reloader wipes the in-memory _jobs dict
    # mid-render whenever any file is touched, orphaning polling frontends.
    create_app().run(debug=True, use_reloader=False, port=5000)
