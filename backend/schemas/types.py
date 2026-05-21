from typing import List, Literal, Optional, Union
from pydantic import BaseModel, field_validator, Field


# ---------------------------------------------------------------------------
# Shared validators
# ---------------------------------------------------------------------------

def _validate_domain(v: List[float]) -> List[float]:
    """Validate that domain has exactly two entries and the upper bound exceeds the lower bound."""
    if len(v) != 2:
        raise ValueError("domain must contain exactly two entries [low, high]")
    if v[1] <= v[0]:
        raise ValueError("domain[1] must be strictly greater than domain[0]")
    return v


# ---------------------------------------------------------------------------
# Visualization schemas (one per scene type)
# ---------------------------------------------------------------------------

class BubbleSortSchema(BaseModel):
    scene: Literal["bubble_sort"] = "bubble_sort"
    array: List[int] = Field(..., max_length=50)
    caption: str = ""


class FunctionPlotSchema(BaseModel):
    scene: Literal["function_plot"] = "function_plot"
    expression: str
    domain: List[float] = [-4.0, 4.0]
    x_point: Optional[float] = None
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class LimitSchema(BaseModel):
    scene: Literal["limit"] = "limit"
    expression: str
    limit_point: float
    domain: List[float] = [-5.0, 5.0]
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class TangentLineSchema(BaseModel):
    scene: Literal["tangent_line"] = "tangent_line"
    expression: str
    x_point: float
    domain: List[float] = [-4.0, 4.0]
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class RiemannSumSchema(BaseModel):
    scene: Literal["riemann_sum"] = "riemann_sum"
    expression: str
    domain: List[float]
    n: int = Field(default=5, ge=1, le=50)
    method: Literal["left", "right", "midpoint"] = "left"
    caption: str = ""

    @field_validator("n")
    @classmethod
    def n_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("n must be at least 1")
        return v

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class CriticalPointsSchema(BaseModel):
    scene: Literal["critical_points"] = "critical_points"
    expression: str
    domain: List[float] = [-4.0, 4.0]
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class LinearFunctionSchema(BaseModel):
    scene: Literal["linear_function"] = "linear_function"
    expression: str
    domain: List[float] = [-5.0, 5.0]
    second_expression: Optional[str] = None
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class QuadraticSchema(BaseModel):
    scene: Literal["quadratic"] = "quadratic"
    expression: str
    domain: List[float] = [-5.0, 5.0]
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class TrigUnitCircleSchema(BaseModel):
    scene: Literal["trig_unit_circle"] = "trig_unit_circle"
    angle: float = 0.785
    animate_rotation: bool = True
    caption: str = ""


class SurfacePlotSchema(BaseModel):
    scene: Literal["surface_plot"] = "surface_plot"
    expression: str
    x_domain: List[float] = [-3.0, 3.0]
    y_domain: List[float] = [-3.0, 3.0]
    caption: str = ""

    @field_validator("x_domain", "y_domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


# ---------------------------------------------------------------------------
# DSA schemas
# ---------------------------------------------------------------------------

class ArrayPointerSchema(BaseModel):
    scene: Literal["array_pointer"] = "array_pointer"
    array: List[Union[int, str]] = Field(..., max_length=50)
    algorithm: Literal["binary_search", "two_pointers", "palindrome"] = "binary_search"
    target: Optional[int] = None
    caption: str = ""


class SlidingWindowSchema(BaseModel):
    scene: Literal["sliding_window"] = "sliding_window"
    array: List[Union[int, str]] = Field(..., max_length=50)
    algorithm: Literal["max_subarray_fixed", "longest_unique_substring"] = "max_subarray_fixed"
    k: Optional[int] = 3
    caption: str = ""


class LinkedListSchema(BaseModel):
    scene: Literal["linked_list"] = "linked_list"
    values: List[int] = Field(..., max_length=50)
    algorithm: Literal["reverse", "find_middle", "merge_sorted"] = "reverse"
    values2: Optional[List[int]] = Field(default=None, max_length=50)
    caption: str = ""


class TreeTraversalSchema(BaseModel):
    scene: Literal["tree_traversal"] = "tree_traversal"
    values: List[Optional[int]] = Field(..., max_length=50)
    algorithm: Literal["inorder", "preorder", "postorder", "bfs", "dfs", "height"] = "bfs"
    caption: str = ""


class GraphSchema(BaseModel):
    scene: Literal["graph_traversal"] = "graph_traversal"
    num_nodes: int
    edges: List[List[int]]
    start_node: int = 0
    algorithm: Literal["bfs", "dfs", "has_cycle"] = "bfs"
    directed: bool = False
    caption: str = ""


class DPArraySchema(BaseModel):
    scene: Literal["dp_array"] = "dp_array"
    algorithm: Literal["fibonacci", "climbing_stairs", "house_robber", "coin_change"]
    n: Optional[int] = Field(default=8, ge=1, le=20)
    coins: Optional[List[int]] = Field(default=None, max_length=50)
    amount: Optional[int] = None
    caption: str = ""


class StackQueueSchema(BaseModel):
    scene: Literal["stack_queue"] = "stack_queue"
    operations: List[str]
    structure: Literal["stack", "queue"] = "stack"
    caption: str = ""


# ---------------------------------------------------------------------------
# DSA pattern schemas (granular, primitive-based)
# ---------------------------------------------------------------------------

class TwoPointersOppositeSchema(BaseModel):
    scene: Literal["two_pointers_opposite"] = "two_pointers_opposite"
    array: List[Union[int, str]] = Field(..., max_length=50)
    algorithm: Literal["palindrome", "two_sum_sorted", "container_water", "reverse_array"] = "palindrome"
    target: Optional[int] = None
    caption: str = ""


class TwoPointersSameDirSchema(BaseModel):
    scene: Literal["two_pointers_same_dir"] = "two_pointers_same_dir"
    array: List[int] = Field(..., max_length=50)
    algorithm: Literal["remove_duplicates", "move_zeros"] = "remove_duplicates"
    caption: str = ""


class SlidingWindowVariableSchema(BaseModel):
    scene: Literal["sliding_window_variable"] = "sliding_window_variable"
    array: List[Union[int, str]] = Field(..., max_length=50)
    algorithm: Literal["longest_no_repeat", "longest_at_most_k_distinct"] = "longest_no_repeat"
    k: Optional[int] = Field(default=None, ge=1, le=20)
    caption: str = ""


class BinarySearchIndexSchema(BaseModel):
    scene: Literal["binary_search_index"] = "binary_search_index"
    array: List[int] = Field(..., max_length=50)
    algorithm: Literal["find_target", "first_occurrence"] = "find_target"
    target: int = 0
    caption: str = ""


class BinarySearchAnswerSchema(BaseModel):
    scene: Literal["binary_search_answer"] = "binary_search_answer"
    min_value: int = Field(default=1, ge=-1000, le=1000)
    max_value: int = Field(default=16, ge=-1000, le=1000)
    true_at: int = Field(default=7, ge=-1000, le=1000)
    predicate_label: str = "feasible(x)"
    caption: str = ""

    @field_validator("max_value")
    @classmethod
    def _max_above_min(cls, v, info):
        mn = info.data.get("min_value")
        if mn is not None and v <= mn:
            raise ValueError("max_value must be greater than min_value")
        return v


class MonotonicStackSchema(BaseModel):
    scene: Literal["monotonic_stack"] = "monotonic_stack"
    array: List[int] = Field(..., max_length=30)
    algorithm: Literal["next_greater", "daily_temperatures"] = "next_greater"
    monotone: Literal["increasing", "decreasing"] = "decreasing"
    caption: str = ""


class HashMapIterationSchema(BaseModel):
    scene: Literal["hashmap_iteration"] = "hashmap_iteration"
    array: List[Union[int, str]] = Field(..., max_length=50)
    algorithm: Literal["frequency_count", "two_sum_hashmap", "anagram_check"] = "frequency_count"
    target: Optional[int] = None
    caption: str = ""


class PrefixSumSchema(BaseModel):
    scene: Literal["prefix_sum"] = "prefix_sum"
    array: List[int] = Field(..., max_length=30)
    algorithm: Literal["build_prefix", "range_sum_query"] = "build_prefix"
    query_range: Optional[List[int]] = None
    target: Optional[int] = None
    caption: str = ""


# ---------------------------------------------------------------------------
# DSA pattern schemas — extended (LRU, grid, backtracking, intervals,
# Dijkstra, union-find, trie, heap, Kadane's, segment tree, 2D DP)
# ---------------------------------------------------------------------------

class KadanesSchema(BaseModel):
    scene: Literal["kadanes"] = "kadanes"
    array: List[int] = Field(..., max_length=20)
    caption: str = ""


class IntervalMergingSchema(BaseModel):
    scene: Literal["interval_merging"] = "interval_merging"
    intervals: List[List[int]] = Field(..., max_length=12)
    caption: str = ""


class BacktrackingSubsetsSchema(BaseModel):
    scene: Literal["backtracking_subsets"] = "backtracking_subsets"
    array: List[int] = Field(..., max_length=5)
    algorithm: Literal["subsets", "permutations"] = "subsets"
    caption: str = ""


class LRUCacheSchema(BaseModel):
    scene: Literal["lru_cache"] = "lru_cache"
    operations: List[str] = Field(..., max_length=15)
    capacity: int = Field(default=2, ge=1, le=8)
    caption: str = ""


class GridTraversalSchema(BaseModel):
    scene: Literal["grid_traversal"] = "grid_traversal"
    grid: List[List[int]] = Field(..., min_length=1, max_length=8)
    start: List[int]
    target: List[int]
    algorithm: Literal["bfs", "dfs"] = "bfs"
    caption: str = ""

    @field_validator("grid")
    @classmethod
    def _grid_nonempty(cls, v: List[List[int]]) -> List[List[int]]:
        if not v or not v[0]:
            raise ValueError("grid must have at least one row and one column")
        cols = len(v[0])
        if any(len(row) != cols for row in v):
            raise ValueError("grid rows must all have the same length")
        if cols > 8:
            raise ValueError("grid columns must not exceed 8")
        return v


class HeapOpsSchema(BaseModel):
    scene: Literal["heap_ops"] = "heap_ops"
    operations: List[str] = Field(..., max_length=15)
    heap_type: Literal["min", "max"] = "min"
    caption: str = ""


class DP2DSchema(BaseModel):
    scene: Literal["dp_2d"] = "dp_2d"
    algorithm: Literal["lcs", "edit_distance", "unique_paths"] = "lcs"
    input1: str = Field(default="abc", max_length=10)
    input2: str = Field(default="ac", max_length=10)
    caption: str = ""


class TrieOpsSchema(BaseModel):
    scene: Literal["trie_ops"] = "trie_ops"
    words: List[str] = Field(..., max_length=8)
    queries: List[str] = Field(default_factory=list, max_length=6)
    caption: str = ""


class UnionFindSchema(BaseModel):
    scene: Literal["union_find"] = "union_find"
    n: int = Field(default=6, ge=1, le=10)
    operations: List[str] = Field(..., max_length=15)
    caption: str = ""


class DijkstraSchema(BaseModel):
    scene: Literal["dijkstra"] = "dijkstra"
    num_nodes: int = Field(default=5, ge=2, le=10)
    edges: List[List[int]] = Field(..., max_length=20)
    source: int = 0
    caption: str = ""


class SegmentTreeSchema(BaseModel):
    scene: Literal["segment_tree"] = "segment_tree"
    array: List[int] = Field(..., max_length=8)
    queries: List[List[int]] = Field(default_factory=list, max_length=6)
    caption: str = ""


# ---------------------------------------------------------------------------
# Phase 7 — additional pattern scenes
# ---------------------------------------------------------------------------

class FloydCycleSchema(BaseModel):
    scene: Literal["floyd_cycle"] = "floyd_cycle"
    values: List[int] = Field(..., min_length=1, max_length=10)
    cycle_at: Optional[int] = None
    caption: str = ""


class TrappingRainWaterSchema(BaseModel):
    scene: Literal["trapping_rain_water"] = "trapping_rain_water"
    heights: List[int] = Field(..., min_length=2, max_length=12)
    caption: str = ""


class GreedyIntervalSchema(BaseModel):
    scene: Literal["greedy_interval"] = "greedy_interval"
    values: List[int] = Field(..., min_length=1, max_length=10)
    algorithm: Literal["jump_game", "gas_station"] = "jump_game"
    caption: str = ""


class BitManipulationSchema(BaseModel):
    scene: Literal["bit_manipulation"] = "bit_manipulation"
    values: List[int] = Field(..., min_length=1, max_length=8)
    operation: Literal["single_number", "count_bits"] = "single_number"
    caption: str = ""


class TopologicalSortSchema(BaseModel):
    scene: Literal["topological_sort"] = "topological_sort"
    num_nodes: int = Field(default=5, ge=2, le=8)
    edges: List[List[int]] = Field(..., max_length=15)
    caption: str = ""


class MatrixRotationSchema(BaseModel):
    scene: Literal["matrix_rotation"] = "matrix_rotation"
    matrix: List[List[int]] = Field(..., min_length=1, max_length=5)
    operation: Literal["rotate_90", "spiral"] = "rotate_90"
    caption: str = ""

    @field_validator("matrix")
    @classmethod
    def _matrix_shape(cls, v: List[List[int]]) -> List[List[int]]:
        if not v or not v[0]:
            raise ValueError("matrix must have at least one row and one column")
        cols = len(v[0])
        if any(len(row) != cols for row in v):
            raise ValueError("matrix rows must all have the same length")
        if cols > 5:
            raise ValueError("matrix columns must not exceed 5")
        return v


class RecursionTreeDCSchema(BaseModel):
    scene: Literal["recursion_tree_dc"] = "recursion_tree_dc"
    array: List[int] = Field(..., min_length=1, max_length=8)
    algorithm: Literal["merge_sort"] = "merge_sort"
    caption: str = ""


# ---------------------------------------------------------------------------
# 2D DP family (Phase 2 of DP interview-prep batch)
# ---------------------------------------------------------------------------

class KnapsackItem(BaseModel):
    weight: int = Field(..., ge=1, le=20)
    value: int = Field(..., ge=0, le=99)


class Knapsack01Schema(BaseModel):
    scene: Literal["knapsack_01"] = "knapsack_01"
    items: List[KnapsackItem] = Field(..., min_length=1, max_length=5)
    capacity: int = Field(..., ge=1, le=8)
    caption: str = ""


class LCSSchema(BaseModel):
    scene: Literal["lcs"] = "lcs"
    s1: str = Field(..., min_length=1, max_length=8)
    s2: str = Field(..., min_length=1, max_length=8)
    caption: str = ""


class EditDistanceSchema(BaseModel):
    scene: Literal["edit_distance"] = "edit_distance"
    s1: str = Field(..., min_length=1, max_length=6)
    s2: str = Field(..., min_length=1, max_length=6)
    caption: str = ""


class CoinChange2DSchema(BaseModel):
    scene: Literal["coin_change_2d"] = "coin_change_2d"
    coins: List[int] = Field(..., min_length=1, max_length=4)
    amount: int = Field(..., ge=1, le=10)
    caption: str = ""


class LISSchema(BaseModel):
    scene: Literal["lis"] = "lis"
    nums: List[int] = Field(..., min_length=2, max_length=8)
    caption: str = ""


class DPProgressionSchema(BaseModel):
    scene: Literal["dp_progression"] = "dp_progression"
    problem: Literal["fibonacci", "climb_stairs",
                     "coin_change_min", "unique_paths"] = "fibonacci"
    n: int = Field(default=5, ge=2, le=8)
    caption: str = ""


# ---------------------------------------------------------------------------
# Arithmetic schemas
# ---------------------------------------------------------------------------

class NumberLineSchema(BaseModel):
    scene: Literal["number_line"] = "number_line"
    mode: Literal["addition", "subtraction", "inequality", "absolute_value"] = "addition"
    values: List[float] = Field(..., max_length=50)
    domain: List[float] = [-2.0, 12.0]
    inequality_sign: str = ">"
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class FractionSchema(BaseModel):
    scene: Literal["fraction"] = "fraction"
    mode: Literal["represent", "compare", "add", "subtract"] = "represent"
    fractions: List[List[int]] = Field(..., max_length=50)
    caption: str = ""


class AreaModelSchema(BaseModel):
    scene: Literal["area_model"] = "area_model"
    mode: Literal["integer", "algebraic"] = "integer"
    a: str
    b: str
    caption: str = ""


# ---------------------------------------------------------------------------
# Algebra extension schemas
# ---------------------------------------------------------------------------

class InequalitySchema(BaseModel):
    scene: Literal["inequality"] = "inequality"
    expression: str
    domain: List[float] = [-10.0, 10.0]
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class ExponentialSchema(BaseModel):
    scene: Literal["exponential"] = "exponential"
    expression: str
    domain: List[float] = [-3.0, 5.0]
    show_key_points: bool = True
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class TransformationSchema(BaseModel):
    scene: Literal["transformation"] = "transformation"
    base_expression: str
    transformed_expression: str
    domain: List[float] = [-5.0, 5.0]
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


# ---------------------------------------------------------------------------
# Calculus extension schemas
# ---------------------------------------------------------------------------

class VolumeRevolutionSchema(BaseModel):
    scene: Literal["volume_revolution"] = "volume_revolution"
    expression: str
    domain: List[float]
    n_disks: int = Field(default=8, ge=1, le=20)
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class TaylorSeriesSchema(BaseModel):
    scene: Literal["taylor_series"] = "taylor_series"
    expression: str
    center: float = 0.0
    max_terms: int = Field(default=5, ge=1, le=12)
    domain: List[float] = [-5.0, 5.0]
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class FTCSchema(BaseModel):
    scene: Literal["ftc"] = "ftc"
    expression: str
    domain: List[float] = [-1.0, 5.0]
    start: float = 0.0
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class SequenceSchema(BaseModel):
    scene: Literal["sequence"] = "sequence"
    formula: str                        # recursive formula f(x), where aₙ = f(aₙ₋₁)
    a0: float = 0.0
    n_terms: int = Field(default=8, ge=1, le=20)
    caption: str = ""


class CobwebSchema(BaseModel):
    scene: Literal["cobweb"] = "cobweb"
    formula: str
    a0: float = 0.0
    n_steps: int = Field(default=8, ge=1, le=30)
    domain: List[float] = [0.0, 4.0]
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class AreaBetweenCurvesSchema(BaseModel):
    scene: Literal["area_between_curves"] = "area_between_curves"
    f_expression: str
    g_expression: str
    domain: List[float]
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class WasherMethodSchema(BaseModel):
    scene: Literal["washer_method"] = "washer_method"
    f_expression: str
    g_expression: str
    domain: List[float]
    n_washers: int = Field(default=8, ge=1, le=20)
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class ShellMethodSchema(BaseModel):
    scene: Literal["shell_method"] = "shell_method"
    expression: str
    domain: List[float]
    n_shells: int = Field(default=8, ge=1, le=20)
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class ArcLengthSchema(BaseModel):
    scene: Literal["arc_length"] = "arc_length"
    expression: str
    domain: List[float]
    n_segments: int = Field(default=8, ge=1, le=30)
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class AverageValueSchema(BaseModel):
    scene: Literal["average_value"] = "average_value"
    expression: str
    domain: List[float]
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class USubstitutionSchema(BaseModel):
    scene: Literal["u_substitution"] = "u_substitution"
    expression: str
    u_expression: str
    domain: List[float]
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class IntegrationByPartsSchema(BaseModel):
    scene: Literal["integration_by_parts"] = "integration_by_parts"
    u_expression: str
    dv_expression: str
    domain: List[float] = [0.0, 2.0]
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class ImproperIntegralSchema(BaseModel):
    scene: Literal["improper_integral"] = "improper_integral"
    expression: str
    domain: List[float]
    improper_bound: Literal["right", "left", "both"] = "right"
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class CrossSectionSchema(BaseModel):
    scene: Literal["cross_section"] = "cross_section"
    expression: str
    domain: List[float]
    shape: Literal["square", "semicircle", "equilateral_triangle"] = "square"
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


# ---------------------------------------------------------------------------
# Calc 3 extension schemas
# ---------------------------------------------------------------------------

class ContourSchema(BaseModel):
    scene: Literal["contour"] = "contour"
    expression: str
    x_domain: List[float] = [-3.0, 3.0]
    y_domain: List[float] = [-3.0, 3.0]
    num_levels: int = Field(default=8, ge=1, le=15)
    caption: str = ""

    @field_validator("x_domain", "y_domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class VectorFieldSchema(BaseModel):
    scene: Literal["vector_field"] = "vector_field"
    x_expression: str
    y_expression: str
    domain: List[float] = [-3.0, 3.0]
    show_streamlines: bool = False
    caption: str = ""

    @field_validator("domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


class PartialDerivativeSchema(BaseModel):
    scene: Literal["partial_derivative"] = "partial_derivative"
    expression: str
    variable: Literal["x", "y"] = "x"
    fixed_value: float = 0.0
    x_domain: List[float] = [-3.0, 3.0]
    y_domain: List[float] = [-3.0, 3.0]
    caption: str = ""

    @field_validator("x_domain", "y_domain")
    @classmethod
    def _check_domain(cls, v: List[float]) -> List[float]:
        return _validate_domain(v)


VisualizationSchema = (
    BubbleSortSchema
    | FunctionPlotSchema
    | LimitSchema
    | TangentLineSchema
    | RiemannSumSchema
    | CriticalPointsSchema
    | LinearFunctionSchema
    | QuadraticSchema
    | TrigUnitCircleSchema
    | SurfacePlotSchema
    | NumberLineSchema
    | FractionSchema
    | AreaModelSchema
    | InequalitySchema
    | ExponentialSchema
    | TransformationSchema
    | VolumeRevolutionSchema
    | TaylorSeriesSchema
    | FTCSchema
    | SequenceSchema
    | CobwebSchema
    | ContourSchema
    | VectorFieldSchema
    | PartialDerivativeSchema
    | ArrayPointerSchema
    | SlidingWindowSchema
    | LinkedListSchema
    | TreeTraversalSchema
    | GraphSchema
    | DPArraySchema
    | StackQueueSchema
    | AreaBetweenCurvesSchema
    | WasherMethodSchema
    | ShellMethodSchema
    | ArcLengthSchema
    | AverageValueSchema
    | USubstitutionSchema
    | IntegrationByPartsSchema
    | ImproperIntegralSchema
    | CrossSectionSchema
    | TwoPointersOppositeSchema
    | TwoPointersSameDirSchema
    | SlidingWindowVariableSchema
    | BinarySearchIndexSchema
    | BinarySearchAnswerSchema
    | MonotonicStackSchema
    | HashMapIterationSchema
    | PrefixSumSchema
    | KadanesSchema
    | IntervalMergingSchema
    | BacktrackingSubsetsSchema
    | LRUCacheSchema
    | GridTraversalSchema
    | HeapOpsSchema
    | DP2DSchema
    | TrieOpsSchema
    | UnionFindSchema
    | DijkstraSchema
    | SegmentTreeSchema
    | FloydCycleSchema
    | TrappingRainWaterSchema
    | GreedyIntervalSchema
    | BitManipulationSchema
    | TopologicalSortSchema
    | MatrixRotationSchema
    | RecursionTreeDCSchema
)


# ---------------------------------------------------------------------------
# Lesson plan models (planner output)
# ---------------------------------------------------------------------------

class StepPlan(BaseModel):
    tool: str
    params: dict
    caption: str = ""


class LessonPlan(BaseModel):
    concept: str
    level: str
    steps: List[StepPlan]
