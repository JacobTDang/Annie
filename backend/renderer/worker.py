import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from renderer.job_store import JobDictProxy, build_default_store
from renderer.queue import build_default_queue
from renderer.storage import LocalStorageBackend, build_default_storage

# Item #13 — `_jobs` is a dict-shaped façade over a JobStore. Default is
# in-memory (zero behavior change). Set LUMEN_JOBS_DB to opt into SQLite
# persistence so jobs survive a worker restart.
_jobs = JobDictProxy(build_default_store())

# Item #14 — dispatch background work through the pluggable JobQueue.
# Default is InProcessQueue (ThreadPoolExecutor — same shape as the prior
# direct threading.Thread calls). Set REDIS_URL to opt into RQ.
_default_queue = build_default_queue()

# ---------------------------------------------------------------------------
# Quality settings
#
# Set LUMEN_QUALITY=low|medium|high to override (defaults to "low" — 480p15,
# the fastest tier). Each tier is ~3-4x slower than the previous to render.
# 480p is comfortably legible for the educational scenes we ship; bump it up
# only if you're exporting for high-DPI screens or recording a final video.
# ---------------------------------------------------------------------------
_QUALITY_TIERS = {
    "low":    ("-ql", "480p15"),
    "medium": ("-qm", "720p30"),
    "high":   ("-qh", "1080p60"),
}
_QUALITY_2D = _QUALITY_TIERS.get(
    os.environ.get("LUMEN_QUALITY", "medium").lower(),
    _QUALITY_TIERS["medium"],
)
_QUALITY_FLAG_2D, _QUALITY_DIR_2D = _QUALITY_2D
# 3D scenes always render at low — surface plots are an order of magnitude
# slower than 2D scenes and benefit much less from a resolution bump.
_QUALITY_FLAG_3D, _QUALITY_DIR_3D = _QUALITY_TIERS["low"]
_3D_SCENES = {"surface_plot", "partial_derivative"}

SCENE_REGISTRY = {
    # Core
    "bubble_sort":        ("scenes/array_scene.py",       "BubbleSortScene"),
    "merge_sort":         ("scenes/array_scene.py",       "MergeSortScene"),
    "quick_sort":         ("scenes/array_scene.py",       "QuickSortScene"),
    # Calculus
    "function_plot":      ("scenes/calculus_scene.py",    "FunctionPlotScene"),
    "limit":              ("scenes/calculus_scene.py",    "LimitScene"),
    "tangent_line":       ("scenes/calculus_scene.py",    "TangentLineScene"),
    "secant_line":        ("scenes/calculus_scene.py",    "SecantLineScene"),
    "riemann_sum":        ("scenes/calculus_scene.py",    "RiemannSumScene"),
    "critical_points":    ("scenes/calculus_scene.py",    "CriticalPointsScene"),
    "volume_revolution":  ("scenes/calculus_scene.py",    "VolumeRevolutionScene"),
    "taylor_series":      ("scenes/calculus_scene.py",    "TaylorSeriesScene"),
    "ftc":                ("scenes/calculus_scene.py",    "FTCScene"),
    "sequence":           ("scenes/calculus_scene.py",    "SequenceScene"),
    "cobweb":             ("scenes/calculus_scene.py",    "CobwebScene"),
    "area_between_curves": ("scenes/calculus_scene.py",  "AreaBetweenCurvesScene"),
    "washer_method":       ("scenes/calculus_scene.py",  "WasherMethodScene"),
    "shell_method":        ("scenes/calculus_scene.py",  "ShellMethodScene"),
    "arc_length":          ("scenes/calculus_scene.py",  "ArcLengthScene"),
    "average_value":       ("scenes/calculus_scene.py",  "AverageValueScene"),
    "u_substitution":      ("scenes/calculus_scene.py",  "USubstitutionScene"),
    "integration_by_parts":("scenes/calculus_scene.py",  "IntegrationByPartsScene"),
    "improper_integral":   ("scenes/calculus_scene.py",  "ImproperIntegralScene"),
    "cross_section":       ("scenes/calculus_scene.py",  "CrossSectionScene"),
    # Algebra
    "linear_function":    ("scenes/algebra_scene.py",     "LinearFunctionScene"),
    "quadratic":          ("scenes/algebra_scene.py",     "QuadraticScene"),
    "inequality":         ("scenes/algebra_scene.py",     "InequalityScene"),
    "exponential":        ("scenes/algebra_scene.py",     "ExponentialScene"),
    "transformation":     ("scenes/algebra_scene.py",     "TransformationScene"),
    # DSA — legacy (monolithic, kept for backwards compatibility)
    "array_pointer":   ("scenes/dsa_scene.py", "ArrayPointerScene"),
    "sliding_window":  ("scenes/dsa_scene.py", "SlidingWindowScene"),
    "linked_list":     ("scenes/dsa_scene.py", "LinkedListScene"),
    "tree_traversal":  ("scenes/dsa_scene.py", "TreeTraversalScene"),
    "graph_traversal": ("scenes/dsa_scene.py", "GraphScene"),
    "dp_array":        ("scenes/dsa_scene.py", "DPArrayScene"),
    "stack_queue":     ("scenes/dsa_scene.py", "StackQueueScene"),
    # DSA — pattern-specific (primitive-based)
    "two_pointers_opposite":   ("scenes/dsa_pattern_scene.py", "TwoPointersOppositeScene"),
    "two_pointers_same_dir":   ("scenes/dsa_pattern_scene.py", "TwoPointersSameDirScene"),
    "sliding_window_variable": ("scenes/dsa_pattern_scene.py", "SlidingWindowVariableScene"),
    "binary_search_index":     ("scenes/dsa_pattern_scene.py", "BinarySearchIndexScene"),
    "binary_search_answer":    ("scenes/dsa_pattern_scene.py", "BinarySearchAnswerScene"),
    "monotonic_stack":         ("scenes/dsa_pattern_scene.py", "MonotonicStackScene"),
    "hashmap_iteration":       ("scenes/dsa_pattern_scene.py", "HashMapIterationScene"),
    "prefix_sum":              ("scenes/dsa_pattern_scene.py", "PrefixSumScene"),
    # DSA — extended pattern scenes (advanced LeetCode coverage)
    "kadanes":                 ("scenes/dsa_pattern_scene.py", "KadanesScene"),
    "interval_merging":        ("scenes/dsa_pattern_scene.py", "IntervalMergingScene"),
    "backtracking_subsets":    ("scenes/dsa_pattern_scene.py", "BacktrackingSubsetsScene"),
    "lru_cache":               ("scenes/dsa_pattern_scene.py", "LRUCacheScene"),
    "grid_traversal":          ("scenes/dsa_pattern_scene.py", "GridTraversalScene"),
    "heap_ops":                ("scenes/dsa_pattern_scene.py", "HeapOpsScene"),
    "dp_2d":                   ("scenes/dsa_pattern_scene.py", "DP2DScene"),
    "trie_ops":                ("scenes/dsa_pattern_scene.py", "TrieOpsScene"),
    "union_find":              ("scenes/dsa_pattern_scene.py", "UnionFindScene"),
    "dijkstra":                ("scenes/dsa_pattern_scene.py", "DijkstraScene"),
    "segment_tree":            ("scenes/dsa_pattern_scene.py", "SegmentTreeScene"),
    # DSA — Phase 7 (visual depth + 7 missing patterns)
    "floyd_cycle":             ("scenes/dsa_pattern_scene.py", "FloydCycleScene"),
    "trapping_rain_water":     ("scenes/dsa_pattern_scene.py", "TrappingRainWaterScene"),
    "greedy_interval":         ("scenes/dsa_pattern_scene.py", "GreedyIntervalScene"),
    "bit_manipulation":        ("scenes/dsa_pattern_scene.py", "BitManipulationScene"),
    "topological_sort":        ("scenes/dsa_pattern_scene.py", "TopologicalSortScene"),
    "matrix_rotation":         ("scenes/dsa_pattern_scene.py", "MatrixRotationScene"),
    "recursion_tree_dc":       ("scenes/dsa_pattern_scene.py", "RecursionTreeDCScene"),
    # Arithmetic
    "number_line":        ("scenes/arithmetic_scene.py",  "NumberLineScene"),
    "fraction":           ("scenes/arithmetic_scene.py",  "FractionScene"),
    "area_model":         ("scenes/arithmetic_scene.py",  "AreaModelScene"),
    # Trig
    "trig_unit_circle":   ("scenes/trig_scene.py",        "TrigUnitCircleScene"),
    # 3D / Calc 3
    "surface_plot":       ("scenes/threed_scene.py",      "SurfacePlotScene"),
    "contour":            ("scenes/threed_scene.py",      "ContourScene"),
    "vector_field":       ("scenes/threed_scene.py",      "VectorFieldScene"),
    "partial_derivative": ("scenes/threed_scene.py",      "PartialDerivativeScene"),
    # Dynamic tool-composed scenes (Lesson Director agent)
    "dynamic_lesson_step": ("scenes/tool_executor.py",    "DynamicScene"),
}

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MEDIA_DIR   = os.path.join(_BACKEND_DIR, "media")
_TEMP_DIR    = os.path.join(_MEDIA_DIR,   "temp")
_LESSONS_DIR = os.path.join(_MEDIA_DIR,   "lessons")
_CACHE_INDEX = os.path.join(_LESSONS_DIR, "cache_index.json")
_PINNED_INDEX = os.path.join(_LESSONS_DIR, "pinned_index.json")
_CACHE_LOCK  = threading.Lock()
_PIN_LOCK    = threading.Lock()

# Item #15 — final lesson MP4s upload through the pluggable storage backend.
# Default is LocalStorageBackend(_LESSONS_DIR) which mirrors the historical
# behavior. Set LUMEN_STORAGE_BACKEND=s3 + the LUMEN_S3_* env vars to push to
# S3/R2 instead. Index files (cache_index.json, pinned_index.json) stay
# local — they're operational metadata, not user content.
_storage = build_default_storage(local_base_dir=_LESSONS_DIR)


def _lesson_key(lesson_id: str) -> str:
    """Storage key for a lesson's final MP4 (backend-agnostic)."""
    return f"{lesson_id}.mp4"


def _lesson_url(lesson_id: str) -> str:
    """URL the frontend can play. Relative for Local, absolute for S3."""
    return _storage.url_for(_lesson_key(lesson_id))


def _lesson_exists(lesson_id: str) -> bool:
    """True if the storage backend already has this lesson."""
    return _storage.exists(_lesson_key(lesson_id))


def _url_to_lesson_id(url: str) -> str | None:
    """Extract the lesson_id from a lesson URL (any backend).

    Used to migrate legacy cache_index entries that stored full URLs into
    the new key-based shape. Returns None when the URL doesn't look like
    a lesson MP4.
    """
    base = os.path.basename(url.split("?", 1)[0])
    if base.endswith(".mp4"):
        return base[:-4]
    return None


# ---------------------------------------------------------------------------
# Lesson render cache
# ---------------------------------------------------------------------------

def _lesson_cache_key(steps: list) -> str:
    """Build a deterministic md5 hash from each step's tool + params.

    Captions are excluded — they only affect the on-screen text, not the
    rendered video bytes that we'd be reusing.
    """
    payload = [{"tool": s.tool, "params": s.params} for s in steps]
    serialized = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.md5(serialized.encode("utf-8")).hexdigest()


def _load_cache_index() -> dict:
    if not os.path.exists(_CACHE_INDEX):
        return {}
    try:
        with open(_CACHE_INDEX) as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache_index(index: dict) -> None:
    os.makedirs(_LESSONS_DIR, exist_ok=True)
    with open(_CACHE_INDEX, "w") as fh:
        json.dump(index, fh, indent=2, sort_keys=True)


def _cache_lookup(cache_key: str) -> str | None:
    """Return cached URL if present AND the lesson is still in storage.

    The index stores either a lesson_id (new shape, Item #15) or a full URL
    (legacy). Legacy entries are migrated on read.
    """
    with _CACHE_LOCK:
        index = _load_cache_index()
        entry = index.get(cache_key)
        if entry is None:
            return None
        lesson_id = entry if not (entry.startswith("/") or entry.startswith("http")) \
                          else _url_to_lesson_id(entry)
        if not lesson_id or not _lesson_exists(lesson_id):
            # Stale entry — drop it so future runs re-render
            index.pop(cache_key, None)
            _save_cache_index(index)
            return None
        # Always return a freshly-computed URL — accounts for backend swap
        return _lesson_url(lesson_id)


def _cache_store(cache_key: str, lesson_id: str) -> None:
    """Store a cache entry. Takes a lesson_id (not a URL) so the entry is
    portable across storage backends."""
    with _CACHE_LOCK:
        index = _load_cache_index()
        index[cache_key] = lesson_id
        _save_cache_index(index)


# ---------------------------------------------------------------------------
# Video pinning — user-saved videos protected from LRU eviction
# ---------------------------------------------------------------------------

def _pinned_bucket(user_id: str | None) -> str:
    """Auth-gating namespace key for the pinned-index. Anonymous → ``__anon``."""
    return f"user:{user_id}" if user_id else "__anon"


def _migrate_flat_pin_index(raw: dict) -> dict:
    """Auth-gating compat: legacy pinned_index.json was {job_id → lesson_id}.

    Detect that shape (top-level values are strings) and wrap into
    ``{"__anon": {job_id → lesson_id}}`` so older deployments don't lose
    their pinned set on upgrade.
    """
    if not raw:
        return {}
    # Already nested if every top-level value is a dict
    if all(isinstance(v, dict) for v in raw.values()):
        return raw
    # Legacy flat → nest under __anon
    return {"__anon": dict(raw)}


def _load_pinned_index() -> dict:
    if not os.path.exists(_PINNED_INDEX):
        return {}
    try:
        with open(_PINNED_INDEX) as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    migrated = _migrate_flat_pin_index(data)
    if migrated is not data and migrated != data:
        # Best-effort migration write — failing here is non-fatal; we still
        # return the migrated shape so reads work right away.
        try:
            _save_pinned_index(migrated)
        except OSError:
            pass
    return migrated


def _save_pinned_index(index: dict) -> None:
    os.makedirs(_LESSONS_DIR, exist_ok=True)
    tmp = _PINNED_INDEX + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(index, fh, indent=2, sort_keys=True)
    os.replace(tmp, _PINNED_INDEX)


def pin_video(job_id: str, user_id: str | None = None) -> str:
    """Mark a completed job's video as protected from cleanup.

    Returns the video URL. Raises ValueError if the job is unknown or not
    yet done. The pin index stores a lesson_id (backend-agnostic) so the
    entry survives a Local→S3 backend swap. ``user_id`` (when set) namespaces
    the pin so signed-in users don't share a flat pool with anonymous traffic.
    """
    job = _jobs.get(job_id)
    if job is None:
        raise ValueError(f"unknown job_id: {job_id}")
    if job.get("status") != "done":
        raise ValueError(f"cannot pin job in status={job.get('status')!r}")
    url = job.get("url")
    if not url:
        raise ValueError("job has no url")
    lesson_id = _url_to_lesson_id(url) or job_id
    bucket = _pinned_bucket(user_id)
    with _PIN_LOCK:
        index = _load_pinned_index()
        index.setdefault(bucket, {})[job_id] = lesson_id
        _save_pinned_index(index)
    return url


def unpin_video(job_id: str, user_id: str | None = None) -> bool:
    """Remove protection. Idempotent — returns True if it was pinned, False otherwise."""
    bucket = _pinned_bucket(user_id)
    with _PIN_LOCK:
        index = _load_pinned_index()
        sub = index.get(bucket, {})
        existed = job_id in sub
        if existed:
            sub.pop(job_id, None)
            if not sub:
                index.pop(bucket, None)
            _save_pinned_index(index)
    return existed


def _all_pinned_lesson_ids() -> set:
    """Flatten every bucket's lesson_id values — used by cleanup_old_lessons."""
    out: set = set()
    index = _load_pinned_index()
    for bucket in index.values():
        if isinstance(bucket, dict):
            for v in bucket.values():
                if isinstance(v, str):
                    out.add(v)
    return out


# ---------------------------------------------------------------------------
# Media cleanup
# ---------------------------------------------------------------------------

def cleanup_old_jobs(max_age_seconds: int = 3600) -> int:
    """Delete media/jobs/<dir>/ older than max_age_seconds (by mtime).

    media/lessons/ is handled separately by cleanup_old_lessons since those
    files are referenced from the cache index and may still be served.
    Returns the number of directories removed.
    """
    jobs_dir = os.path.join(_MEDIA_DIR, "jobs")
    if not os.path.isdir(jobs_dir):
        return 0

    now     = time.time()
    cutoff  = now - max_age_seconds
    removed = 0
    for entry in os.listdir(jobs_dir):
        path = os.path.join(jobs_dir, entry)
        if not os.path.isdir(path):
            continue
        try:
            if os.path.getmtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed


def cleanup_old_lessons(max_count: int = 200, min_age_seconds: int = 120) -> int:
    """LRU eviction over media/lessons/*.mp4: keep at most max_count files.

    Two protections:
    1. Files referenced in the cache index are NEVER deleted.
    2. Files newer than min_age_seconds are also protected to avoid racing
       in-flight renders.

    Item #15: when LUMEN_STORAGE_BACKEND=s3 (or any non-Local backend),
    this is a no-op. S3 buckets should use lifecycle policies for eviction;
    we don't enumerate remote objects from inside the request path. Returns
    the count removed (0 when storage is remote).
    """
    if not isinstance(_storage, LocalStorageBackend):
        return 0
    if not os.path.isdir(_LESSONS_DIR):
        return 0

    # Collect cache-referenced AND user-pinned lesson IDs (sacred).
    with _CACHE_LOCK:
        cache_index = _load_cache_index()

    def _resolve_lesson_id(entry: str) -> str | None:
        if entry.startswith("/") or entry.startswith("http"):
            return _url_to_lesson_id(entry)
        return entry

    protected_ids: set = set()
    for entry in cache_index.values():
        lid = _resolve_lesson_id(entry)
        if lid:
            protected_ids.add(lid)
    # Pins live in a nested per-user index now (auth-gating).
    with _PIN_LOCK:
        protected_ids.update(_all_pinned_lesson_ids())
    protected_paths = {
        os.path.realpath(os.path.join(_LESSONS_DIR, f"{lid}.mp4"))
        for lid in protected_ids
    }

    files = []
    for entry in os.listdir(_LESSONS_DIR):
        if not entry.endswith(".mp4"):
            continue
        path = os.path.join(_LESSONS_DIR, entry)
        if os.path.realpath(path) in protected_paths:
            continue
        try:
            files.append((os.path.getmtime(path), path))
        except OSError:
            continue

    if len(files) <= max_count:
        return 0

    files.sort()   # oldest first
    cutoff = time.time() - min_age_seconds
    excess = len(files) - max_count
    removed = 0
    for mtime, path in files:
        if removed >= excess:
            break
        if mtime > cutoff:
            continue   # too fresh — protect
        try:
            os.remove(path)
            removed += 1
        except OSError:
            continue
    return removed


# ---------------------------------------------------------------------------
# Single-scene API
# ---------------------------------------------------------------------------

def submit_render(scene_type: str, params: dict) -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending", "url": None, "error": None,
                     "progress": 0.0, "stage": "queued"}
    # Dispatch via the JobQueue. InProcess backend submits to a thread pool
    # (replaces the prior daemon Thread). RQ backend pushes to Redis where an
    # external `rq worker` picks it up.
    _default_queue.enqueue(_run_render, job_id, scene_type, params)
    return job_id


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)


def shutdown(wait: bool = True, timeout: float = 5.0) -> None:
    """Drain the in-flight job queue cooperatively.

    Used by:
      - pytest session teardown (conftest.py) so tests that submit lessons
        but don't poll completion don't trigger
        ``RuntimeError: cannot schedule new futures after interpreter shutdown``.
      - Production graceful-shutdown hooks (e.g. signal handlers).

    Safe to call multiple times. The InProcessQueue backend's ThreadPoolExecutor
    accepts wait + (in modern Python) a timeout; if the underlying pool doesn't
    expose timeout, we fall back to a plain shutdown(wait=wait).
    """
    q = globals().get("_default_queue")
    if q is None:
        return
    try:
        # InProcessQueue exposes .shutdown(wait); RedisQueue doesn't need one
        # (Redis owns the job lifecycle).
        if hasattr(q, "shutdown"):
            try:
                q.shutdown(wait=wait)
            except TypeError:
                # Older signature without kwargs
                q.shutdown()
    except Exception:
        # Best-effort drain — never raise from a teardown helper
        pass


# Manim's tqdm progress bar emits lines like:
#   "Animation 0:  42%|████▏      | 10/24 [00:00<00:01, ...]"
# We track the most recent (animation_idx, frac_in_anim) and combine with the
# total animations seen so far to estimate overall job progress.
_TQDM_RE = re.compile(r"Animation\s+(\d+):\s*(\d+)%\|")


def _stream_progress(stderr, job_id: str, on_done: list):
    """Read stderr line-by-line; whenever a tqdm progress line shows up,
    update the job's `progress` field. Best-effort — manim's output format
    can change between versions, in which case progress just stays at 0."""
    last_anim   = -1
    max_anim    = 0
    err_buf: list[str] = []
    try:
        for raw in iter(stderr.readline, ""):
            line = raw.rstrip("\n")
            if not line:
                continue
            err_buf.append(line)
            if len(err_buf) > 200:
                err_buf = err_buf[-200:]   # cap memory
            m = _TQDM_RE.search(line)
            if m:
                anim_idx = int(m.group(1))
                pct      = int(m.group(2)) / 100.0
                if anim_idx > max_anim:
                    max_anim = anim_idx
                last_anim = anim_idx
                # Estimate overall progress: completed anims + current anim's
                # fraction, divided by max_anim+1 (the highest seen). Asymptotic
                # because we don't know total animations until the end.
                total = max(max_anim + 1, last_anim + 1)
                overall = (last_anim + pct) / total
                # Cap at 95% — leave the last 5% for the file-write phase
                _jobs[job_id]["progress"] = min(0.95, overall)
    except Exception:
        pass
    finally:
        on_done.append("\n".join(err_buf[-50:]))


def _run_render(job_id: str, scene_type: str, params: dict):
    if scene_type not in SCENE_REGISTRY:
        _jobs[job_id] = {"status": "error", "url": None,
                         "error": f"unknown scene type: {scene_type}",
                         "progress": 0.0, "stage": "error"}
        return

    # Mark this single-scene job as actively rendering.
    if job_id in _jobs:
        _jobs[job_id]["stage"] = "rendering"

    os.makedirs(_TEMP_DIR, exist_ok=True)
    params_path = os.path.join(_TEMP_DIR, f"{job_id}.json")

    is_3d         = scene_type in _3D_SCENES
    quality_flag  = _QUALITY_FLAG_3D if is_3d else _QUALITY_FLAG_2D
    quality_dir   = _QUALITY_DIR_3D  if is_3d else _QUALITY_DIR_2D
    job_media_dir = os.path.join(_MEDIA_DIR, "jobs", job_id)
    os.makedirs(job_media_dir, exist_ok=True)

    proc = None
    try:
        with open(params_path, "w") as f:
            json.dump(params, f)

        scene_file, scene_class = SCENE_REGISTRY[scene_type]

        # IMPORTANT: stdout MUST be DEVNULL (or actively read in a thread).
        # Manim writes occasional info to stdout; if we capture it via PIPE
        # but never drain it, the OS pipe buffer fills (~64KB) and manim
        # blocks on its next print, deadlocking the entire render.
        proc = subprocess.Popen(
            [sys.executable, "-u", "-m", "manim", quality_flag,
             "--media_dir", job_media_dir,
             "--disable_caching", scene_file, scene_class],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True, bufsize=1, cwd=_BACKEND_DIR,
            env={**os.environ, "MANIM_JOB_ID": job_id, "MANIM_TEMP_DIR": _TEMP_DIR},
        )

        err_capture: list = []
        stderr_thread = threading.Thread(
            target=_stream_progress, args=(proc.stderr, job_id, err_capture), daemon=True,
        )
        stderr_thread.start()

        try:
            proc.wait(timeout=180)
        except subprocess.TimeoutExpired:
            proc.kill()
            _jobs[job_id] = {"status": "error", "url": None,
                             "error": "render timed out after 180s",
                             "progress": _jobs[job_id].get("progress", 0.0),
                             "stage": "error"}
            return

        # Drain remaining stderr
        stderr_thread.join(timeout=2.0)
        err_tail = err_capture[0] if err_capture else ""

        if proc.returncode != 0:
            _jobs[job_id] = {"status": "error", "url": None,
                             "error": err_tail[-500:] or f"exit {proc.returncode}",
                             "progress": _jobs[job_id].get("progress", 0.0),
                             "stage": "error"}
            return

        scene_stem = os.path.splitext(os.path.basename(scene_file))[0]
        video_rel  = f"jobs/{job_id}/videos/{scene_stem}/{quality_dir}/{scene_class}.mp4"
        full_path  = os.path.join(_MEDIA_DIR, video_rel)

        if not os.path.exists(full_path):
            _jobs[job_id] = {"status": "error", "url": None,
                             "error": "output file not found after render",
                             "progress": _jobs[job_id].get("progress", 0.0),
                             "stage": "error"}
            return

        _jobs[job_id] = {"status": "done", "url": f"/media/{video_rel}",
                         "error": None, "progress": 1.0, "stage": "done"}

    except Exception as e:
        if proc is not None:
            try: proc.kill()
            except Exception: pass
        _jobs[job_id] = {"status": "error", "url": None, "error": str(e),
                         "progress": _jobs[job_id].get("progress", 0.0),
                         "stage": "error"}
    finally:
        if os.path.exists(params_path):
            os.remove(params_path)


# ---------------------------------------------------------------------------
# Multi-scene lesson API  (parallel rendering)
# ---------------------------------------------------------------------------

def submit_lesson(steps: list) -> str:
    lesson_id = str(uuid.uuid4())
    _jobs[lesson_id] = {"status": "pending", "url": None, "error": None,
                        "progress": 0.0, "stage": "queued"}
    _default_queue.enqueue(_run_lesson, lesson_id, steps)
    return lesson_id


def _aggregate_progress(lesson_id: str, step_job_ids: list, stop_event: threading.Event):
    """Background ticker that averages step progress into the lesson job's
    progress field while the lesson is still rendering.

    Also updates the lesson's stage to ``rendering_X_of_N`` based on how many
    step jobs have completed so the frontend can show meaningful progress.
    """
    n = len(step_job_ids)
    while not stop_event.is_set():
        try:
            progresses = [
                _jobs.get(sid, {}).get("progress", 0.0) for sid in step_job_ids
            ]
            done_count = sum(
                1 for sid in step_job_ids
                if _jobs.get(sid, {}).get("status") == "done"
            )
            # "Currently rendering" is the (done_count+1)th, clamped to N.
            current_idx = min(done_count + 1, n)
            if progresses:
                avg = sum(progresses) / len(progresses)
                cur = _jobs.get(lesson_id, {})
                if cur.get("status") == "pending":
                    cur["progress"] = min(0.95, avg)
                    cur["stage"] = f"rendering_{current_idx}_of_{n}"
        except Exception:
            pass
        stop_event.wait(0.25)


def stitch_videos(paths: list[str], out: str):
    filelist_path = out + ".txt"
    with open(filelist_path, "w") as fh:
        fh.write("\n".join(f"file '{p}'" for p in paths))
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", filelist_path, "-c", "copy", out],
        check=True, capture_output=True, text=True, timeout=60,
    )
    os.remove(filelist_path)


def _run_lesson(lesson_id: str, steps: list):
    # Lazy housekeeping — drop old per-job render dirs and cap lessons/ size
    # so media/ doesn't grow unboundedly during normal usage. Failures here
    # must not block a render.
    try:
        cleanup_old_jobs()
        cleanup_old_lessons()
    except Exception:
        pass

    # Cache check — identical (tool, params) sequence → reuse stitched video
    cache_key   = _lesson_cache_key(steps)
    cached_url  = _cache_lookup(cache_key)
    if cached_url is not None:
        _jobs[lesson_id] = {"status": "done", "url": cached_url, "error": None,
                            "progress": 1.0, "stage": "done"}
        return

    # Pre-allocate step job IDs so the progress aggregator can track them
    # before each step actually starts running.
    step_job_ids = [str(uuid.uuid4()) for _ in steps]
    for sid in step_job_ids:
        _jobs[sid] = {"status": "pending", "url": None, "error": None,
                      "progress": 0.0, "stage": "queued"}

    progress_stop = threading.Event()
    progress_thread = threading.Thread(
        target=_aggregate_progress,
        args=(lesson_id, step_job_ids, progress_stop),
        daemon=True,
    )
    progress_thread.start()

    def _render_step(idx: int, step):
        _run_render(step_job_ids[idx], step.tool, {**step.params, "caption": step.caption})

    # Render all steps in parallel — isolated media dirs prevent collisions
    max_workers = min(len(steps), 4)
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_render_step, i, step) for i, step in enumerate(steps)]
            for f in futures:
                f.result()
    finally:
        progress_stop.set()
        # Join the aggregator so it doesn't outlive the lesson and try to
        # write to _jobs after interpreter shutdown. The thread polls
        # `stop_event.wait(0.25)` so 2s is generous.
        progress_thread.join(timeout=2.0)

    # Check for any render errors
    for jid in step_job_ids:
        if _jobs[jid]["status"] == "error":
            _jobs[lesson_id] = {
                "status": "error", "url": None,
                "error": f"Step failed: {_jobs[jid]['error']}",
                "progress": _jobs[lesson_id].get("progress", 0.0),
                "stage": "error",
            }
            return

    # Single step — copy into storage so the cache has a stable URL that
    # survives cleanup_old_jobs() removing the original per-job dir.
    if len(step_job_ids) == 1:
        src_url  = _jobs[step_job_ids[0]]["url"]
        src_path = os.path.join(_MEDIA_DIR, src_url.removeprefix("/media/"))
        try:
            final_url = _storage.put(src_path, _lesson_key(lesson_id))
            cached = True
        except Exception as exc:
            # Fall back to the original URL if upload fails — caching skipped.
            print(f"[worker] storage.put failed (single-step): {exc}")
            final_url = src_url
            cached = False
        _jobs[lesson_id] = {"status": "done", "url": final_url, "error": None,
                            "progress": 1.0, "stage": "done"}
        if cached:
            _cache_store(cache_key, lesson_id)
        return

    # Multi-step: announce stitching stage before invoking ffmpeg
    _jobs[lesson_id]["stage"] = "stitching"

    # Collect video paths in submission order then stitch into a local tmp
    # file before uploading via storage.put(). We can't stitch directly into
    # S3 — ffmpeg needs a local target.
    video_paths = [
        os.path.join(_MEDIA_DIR, _jobs[jid]["url"].removeprefix("/media/"))
        for jid in step_job_ids
    ]
    os.makedirs(_TEMP_DIR, exist_ok=True)
    output_path = os.path.join(_TEMP_DIR, f"{lesson_id}.mp4")

    try:
        stitch_videos(video_paths, output_path)
    except Exception as e:
        _jobs[lesson_id] = {"status": "error", "url": None,
                            "error": f"stitch failed: {e}",
                            "progress": _jobs[lesson_id].get("progress", 0.95),
                            "stage": "error"}
        return

    # Item #8 — optional TTS narration. Gated by LUMEN_TTS_ENABLED so default
    # behavior is unchanged. Any failure (no provider, ffmpeg error, etc.) falls
    # back to the silent stitched video — never blocks the response.
    try:
        _maybe_apply_tts(lesson_id, steps, output_path)
    except Exception as exc:
        print(f"[worker] TTS pipeline raised (continuing without audio): {exc}")

    # Upload the (possibly muxed) stitched file via the storage backend.
    try:
        final_url = _storage.put(output_path, _lesson_key(lesson_id))
    except Exception as exc:
        _jobs[lesson_id] = {"status": "error", "url": None,
                            "error": f"storage upload failed: {exc}",
                            "progress": _jobs[lesson_id].get("progress", 0.95),
                            "stage": "error"}
        return
    finally:
        # Don't leak temp stitch files even if upload failed
        try:
            if os.path.exists(output_path) and isinstance(_storage, LocalStorageBackend):
                # LocalStorageBackend.put() copied into _LESSONS_DIR; the
                # temp copy is redundant.
                os.remove(output_path)
            elif os.path.exists(output_path):
                os.remove(output_path)
        except OSError:
            pass

    _jobs[lesson_id] = {"status": "done", "url": final_url, "error": None,
                        "progress": 1.0, "stage": "done"}
    _cache_store(cache_key, lesson_id)


def _maybe_apply_tts(lesson_id: str, steps: list, stitched_path: str) -> None:
    """Generate TTS per step caption, concat, then mux into ``stitched_path``.

    Replaces the stitched video in place on success. No-op when
    LUMEN_TTS_ENABLED is unset. Never raises.
    """
    from agent import tts
    if not tts.is_enabled():
        return

    captions = [getattr(s, "caption", "") or "" for s in steps]
    if not any(captions):
        return

    work_dir = os.path.join(_MEDIA_DIR, "tts", lesson_id)
    os.makedirs(work_dir, exist_ok=True)

    audio_paths: list[str] = []
    for i, caption in enumerate(captions):
        path = os.path.join(work_dir, f"scene_{i}.wav")
        tts.synthesize(caption, path)
        if os.path.exists(path):
            audio_paths.append(path)

    if not audio_paths:
        return

    concat_path = os.path.join(work_dir, "narration.wav")
    if not tts.concat_audio_tracks(audio_paths, concat_path):
        return

    muxed_path = stitched_path + ".muxed.mp4"
    if not tts.mux_audio_into_video(stitched_path, concat_path, muxed_path):
        return

    try:
        os.replace(muxed_path, stitched_path)
    except OSError as exc:
        print(f"[tts] replace failed: {exc}")


# ---------------------------------------------------------------------------
# Direct-lesson API — async LLM agent wrapper around submit_lesson
# ---------------------------------------------------------------------------
#
# The Lesson Director makes 3-5 LLM calls before rendering can start. Doing
# this synchronously inside the request thread blocks for ~10s with no UI
# feedback. Instead we create the job up front, return its id immediately,
# and run the agent + lesson submission on a daemon thread that mirrors the
# inner lesson's state into the outer job for unified status polling.

def submit_direct_lesson(question: str, style: str | None = None,
                          target_minutes: float = 1.5,
                          difficulty_hint: str | None = None) -> str:
    """Submit a Lesson Director lesson and return a job_id immediately.

    ``style`` (optional): one of intuition_first | rigor_first | socratic | speedrun.
    ``target_minutes`` (default 1.5): desired lesson length — the agent scales
    scene count and per-scene tool density to match.

    Stage progression:
        planning_narrative  → Phase 1 LLM call
        building_scenes     → Phase 2 parallel LLM calls
        queued              → handoff to submit_lesson
        rendering_X_of_N    → per-scene renders
        stitching           → ffmpeg concat
        done                → final stitched MP4 URL
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending", "url": None, "error": None,
                     "progress": 0.0, "stage": "planning_narrative"}
    _default_queue.enqueue(_run_direct_lesson, job_id, question, style,
                            target_minutes, difficulty_hint)
    return job_id


def _run_direct_lesson(job_id: str, question: str, style: str | None = None,
                        target_minutes: float = 1.5,
                        difficulty_hint: str | None = None):
    """Background worker: agent planning + submit_lesson + state mirror.

    Imports the agent lazily to avoid a circular import (lesson_director
    imports from schemas which is fine, but keeping it lazy is defensive).
    """
    try:
        # Phase 1: narrative plan
        from agent.lesson_director import (
            narrative_plan,
            build_scene,
            ToolCall,
        )
        from agent import trace as _trace_mod
        from schemas.types import StepPlan
        import concurrent.futures
        import time as _t

        # Start a render trace so LLM calls + stage timings are recorded.
        render_trace = _trace_mod.new_trace(job_id)
        _trace_mod.set_current(render_trace)

        stage_start = _t.perf_counter()
        narrative = narrative_plan(question, style=style,
                                    target_minutes=target_minutes,
                                    difficulty_hint=difficulty_hint)
        render_trace.add_stage(
            "planning_narrative",
            int((_t.perf_counter() - stage_start) * 1000),
        )
        if _jobs[job_id]["status"] != "pending":
            return  # cancelled externally — abort

        _jobs[job_id]["stage"] = "building_scenes"

        # Phase 2: build scenes in parallel (matches lesson_director.direct_lesson).
        # Each worker thread carries the same trace so its call_model invocations
        # are recorded. The same _worker is reused by the retry path below so
        # the retry also gets parallelism (Bug 3 fix).
        stage_start = _t.perf_counter()
        contexts = [""] + [sp.objective for sp in narrative.scenes[:-1]]

        # Item #2 — element_id carryover per scene from the narrative plan.
        from agent.lesson_director import _accumulate_elements
        carryover = _accumulate_elements(narrative.scenes)

        def _worker(i, sp, prev_err: str | None = None):
            _trace_mod.set_current(render_trace)
            try:
                return _safe_build_scene(
                    question, sp, narrative.core_insight, contexts[i],
                    previous_error=prev_err,
                    previous_scene_elements=carryover[i],
                )
            finally:
                _trace_mod.set_current(None)

        def _build_all(prev_err: str | None = None):
            """Parallel build for all scenes. Used both initially and on retry."""
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                futures = [
                    pool.submit(_worker, i, sp, prev_err)
                    for i, sp in enumerate(narrative.scenes)
                ]
                return [f.result() for f in futures]

        tool_call_lists = _build_all()
        render_trace.add_stage(
            "building_scenes",
            int((_t.perf_counter() - stage_start) * 1000),
        )

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

        # Phase 3: hand off to submit_lesson and mirror its state to ours
        _jobs[job_id]["stage"] = "queued"
        _jobs[job_id]["concept"] = narrative.lesson_title
        _jobs[job_id]["scene_count"] = len(steps)

        inner_id = submit_lesson(steps)
        _jobs[job_id]["inner_job_id"] = inner_id

        # Mirror loop — copy status/url/error/progress/stage from inner to outer.
        # On error, retry once: rebuild scenes with the stderr fed back so the
        # agent has a chance to avoid whatever broke the first render.
        render_start = _t.perf_counter()
        retry_used = False
        while True:
            inner = _jobs.get(inner_id)
            if inner is None:
                time.sleep(0.2)
                continue
            outer = _jobs[job_id]
            outer["progress"] = inner.get("progress", outer.get("progress", 0.0))
            outer["stage"]    = inner.get("stage",    outer.get("stage", "queued"))
            if inner["status"] == "done":
                outer["status"] = "done"
                outer["url"]    = inner["url"]
                outer["stage"]  = "done"
                outer["progress"] = 1.0
                render_trace.add_stage(
                    "render_and_stitch",
                    int((_t.perf_counter() - render_start) * 1000),
                )
                render_trace.finalize()
                return
            if inner["status"] == "error":
                err_text = inner.get("error", "render failed")
                # One retry: rebuild scenes with the error fed back, resubmit.
                # Reuses _build_all() for parallelism (Bug 3 fix) and records a
                # "building_scenes_retry" stage so the trace shows the cost
                # (Bug 4 fix). _build_all() routes through _safe_build_scene
                # which re-runs critique + lint, so the retry gets the full
                # quality pass too (Bug 5 confirmed not an issue).
                if not retry_used:
                    retry_used = True
                    render_trace.note(f"first render failed: {err_text}; retrying with error feedback")
                    outer["stage"] = "building_scenes"
                    retry_start = _t.perf_counter()
                    new_tool_call_lists = _build_all(prev_err=err_text)
                    render_trace.add_stage(
                        "building_scenes_retry",
                        int((_t.perf_counter() - retry_start) * 1000),
                    )
                    new_steps = [
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
                        for sp, tcs in zip(narrative.scenes, new_tool_call_lists)
                    ]
                    outer["stage"] = "queued"
                    inner_id = submit_lesson(new_steps)
                    outer["inner_job_id"] = inner_id
                    render_start = _t.perf_counter()
                    continue
                # Retry already used → propagate the failure to the outer job
                outer["status"] = "error"
                outer["error"]  = err_text
                outer["stage"]  = "error"
                render_trace.note(f"retry also failed: {err_text}")
                render_trace.finalize()
                return
            time.sleep(0.25)

    except Exception as e:
        _jobs[job_id] = {"status": "error", "url": None,
                         "error": f"lesson planning failed: {e}",
                         "progress": _jobs[job_id].get("progress", 0.0),
                         "stage": "error"}
        try:
            render_trace.note(f"agent exception: {e}")
            render_trace.finalize()
        except Exception:
            pass


def _safe_build_scene(question, scene_plan, core_insight, prev_context,
                       previous_error: str | None = None,
                       previous_scene_elements: list[str] | None = None):
    """build_scene + critique + lint wrapper that returns a minimal fallback on failure.

    Delegates to lesson_director._build_scene_safe so the async path has the
    same resilience + quality + static-validation as the synchronous one.
    """
    from agent.lesson_director import _build_scene_safe as _delegate
    return _delegate(
        question=question,
        scene_plan=scene_plan,
        core_insight=core_insight,
        prev_context=prev_context,
        max_retries=2,
        previous_error=previous_error,
        previous_scene_elements=previous_scene_elements,
    )
