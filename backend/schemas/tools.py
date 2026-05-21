"""
Visual tool definitions for the Lesson Director agent.

Each tool maps to one or more Manim primitive operations in tool_executor.py.
The LLM picks and sequences these tools to compose a scene; the executor
handles all Manim details.

Format: OpenAI-style function-calling schema (name, description, parameters).
"""

VISUAL_TOOLS: list[dict] = [

    # ── Element creation ──────────────────────────────────────────────────────

    {
        "name": "show_array",
        "description": (
            "Display a horizontal array of values as labeled cells. "
            "Returns an element_id you use in later tool calls. "
            "Use for arrays, lists, strings, or any indexed sequence."
        ),
        "parameters": {
            "values": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Values to display (max 12). Convert numbers to strings.",
            },
            "label": {
                "type": "string",
                "description": "Variable name shown above the array, e.g. 'nums', 'arr', 's'.",
                "default": "",
            },
            "element_id": {
                "type": "string",
                "description": "Unique ID to reference this element later. Default: 'array_0'.",
                "default": "array_0",
            },
        },
        "required": ["values"],
    },

    {
        "name": "show_hashmap",
        "description": (
            "Display a key:value sidebar panel. "
            "Use for frequency maps, lookup tables, memoization, seen sets."
        ),
        "parameters": {
            "title": {
                "type": "string",
                "description": "Panel header, e.g. 'seen', 'freq', 'memo'.",
                "default": "HashMap",
            },
            "anchor": {
                "type": "string",
                "enum": ["UR", "UL", "DR", "DL"],
                "description": "Screen corner to pin the panel.",
                "default": "UR",
            },
            "element_id": {"type": "string", "default": "map_0"},
        },
        "required": [],
    },

    {
        "name": "show_stack",
        "description": (
            "Display a vertical stack widget. "
            "Use for monotonic stacks, call stacks, DFS, balanced parentheses."
        ),
        "parameters": {
            "title": {
                "type": "string",
                "description": "Stack label shown above, e.g. 'stack', 'mono_stack'.",
                "default": "stack",
            },
            "anchor": {
                "type": "string",
                "enum": ["DR", "DL", "UR", "UL"],
                "default": "DR",
            },
            "element_id": {"type": "string", "default": "stack_0"},
        },
        "required": [],
    },

    {
        "name": "show_grid",
        "description": "Display a 2D matrix of values. Use for DP tables, grid traversal, rotation problems.",
        "parameters": {
            "rows": {"type": "integer", "description": "Number of rows (max 6)."},
            "cols": {"type": "integer", "description": "Number of columns (max 6)."},
            "values": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "string"}},
                "description": "Row-major 2D list of string values.",
            },
            "label": {"type": "string", "default": ""},
            "element_id": {"type": "string", "default": "grid_0"},
        },
        "required": ["rows", "cols", "values"],
    },

    {
        "name": "show_code",
        "description": (
            "Display pseudocode lines as a monospace panel. "
            "Use alongside the main animation so the viewer sees the algorithm. "
            "Keep to 5-8 lines. Anchor to UL to leave room for the main visual."
        ),
        "parameters": {
            "lines": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Pseudocode lines (5-8). Do not include line numbers.",
            },
            "anchor": {
                "type": "string",
                "enum": ["UL", "UR", "DL", "DR"],
                "default": "UL",
            },
            "element_id": {"type": "string", "default": "code_0"},
        },
        "required": ["lines"],
    },

    {
        "name": "show_text",
        "description": (
            "Display a line of explanatory text on screen. "
            "Use for invariants, annotations, or brief labels. "
            "Prefer set_caption() for the ongoing 'why' narration."
        ),
        "parameters": {
            "content": {"type": "string", "description": "Text to display (keep under 60 chars)."},
            "position": {
                "type": "string",
                "enum": ["UP", "DOWN", "LEFT", "RIGHT", "CENTER", "UP_LEFT", "UP_RIGHT"],
                "default": "UP",
            },
            "style": {
                "type": "string",
                "enum": ["normal", "italic", "bold"],
                "default": "normal",
            },
            "element_id": {"type": "string", "default": "text_0"},
        },
        "required": ["content"],
    },

    {
        "name": "show_equation",
        "description": "Render a LaTeX mathematical expression. Use for formulas, recurrences, definitions.",
        "parameters": {
            "latex": {
                "type": "string",
                "description": "LaTeX string, e.g. 'T(n) = 2T(n/2) + O(n)'. Do NOT wrap in $...$.",
            },
            "position": {
                "type": "string",
                "enum": ["CENTER", "UP", "DOWN", "UP_LEFT", "UP_RIGHT"],
                "default": "CENTER",
            },
            "element_id": {"type": "string", "default": "eq_0"},
        },
        "required": ["latex"],
    },

    # ── Pointer tools ─────────────────────────────────────────────────────────

    {
        "name": "add_pointer",
        "description": (
            "Add a named labeled arrow that points up at a cell in an array. "
            "Common names: 'left', 'right', 'i', 'j', 'slow', 'fast', 'mid'. "
            "Colors: GREEN for left/slow, RED for right, YELLOW for mid/i, ORANGE for fast."
        ),
        "parameters": {
            "name": {"type": "string", "description": "Pointer label shown below the arrow."},
            "element_id": {"type": "string", "description": "Array element_id to attach to."},
            "index": {"type": "integer", "description": "Starting index (0-based).", "default": 0},
            "color": {
                "type": "string",
                "enum": ["GREEN", "RED", "YELLOW", "ORANGE", "BLUE", "WHITE"],
                "default": "YELLOW",
            },
        },
        "required": ["name", "element_id"],
    },

    {
        "name": "move_pointer",
        "description": "Animate a pointer sliding to a new index. Call after add_pointer.",
        "parameters": {
            "name": {"type": "string", "description": "Name of the pointer to move."},
            "element_id": {"type": "string", "description": "Array element_id the pointer is on."},
            "to_index": {"type": "integer", "description": "Target index (0-based)."},
        },
        "required": ["name", "element_id", "to_index"],
    },

    # ── Cell / value operations ───────────────────────────────────────────────

    {
        "name": "highlight_cells",
        "description": (
            "Flash one or more cells in an array with an Indicate pulse. "
            "Use YELLOW for 'currently examining', GREEN for 'found/kept', RED for 'rejected'."
        ),
        "parameters": {
            "element_id": {"type": "string"},
            "indices": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of 0-based cell indices to highlight.",
            },
            "color": {
                "type": "string",
                "enum": ["YELLOW", "GREEN", "RED", "ORANGE", "BLUE", "WHITE"],
                "default": "YELLOW",
            },
        },
        "required": ["element_id", "indices"],
    },

    {
        "name": "swap_cells",
        "description": "Animate swapping two cells in an array (arc-path animation).",
        "parameters": {
            "element_id": {"type": "string"},
            "i": {"type": "integer", "description": "First index."},
            "j": {"type": "integer", "description": "Second index."},
        },
        "required": ["element_id", "i", "j"],
    },

    {
        "name": "set_cell_value",
        "description": "Update the displayed value of a specific cell.",
        "parameters": {
            "element_id": {"type": "string"},
            "index": {"type": "integer"},
            "value": {"type": "string", "description": "New value to display."},
        },
        "required": ["element_id", "index", "value"],
    },

    # ── Grid-aware ops (Phase 1: 2D DP tables) ───────────────────────────────

    {
        "name": "set_grid_cell",
        "description": (
            "Update a single (row, col) cell of a 2D grid (created via "
            "show_grid). Optionally tint the cell. Use for 2D DP updates: "
            "dp[i][j] = max(dp[i-1][j], dp[i][j-1])."
        ),
        "parameters": {
            "element_id": {"type": "string"},
            "row": {"type": "integer"},
            "col": {"type": "integer"},
            "value": {"type": "string", "description": "New value to display."},
            "color": {
                "type": "string",
                "description": "Optional fill color name (e.g. GREEN, YELLOW).",
                "default": None,
            },
        },
        "required": ["element_id", "row", "col", "value"],
    },

    {
        "name": "highlight_grid_cells",
        "description": (
            "Tint one or more (row, col) cells of a 2D grid. Use to mark "
            "the cells a current DP cell depends on, BEFORE drawing arrows."
        ),
        "parameters": {
            "element_id": {"type": "string"},
            "cells": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "description": "List of [row, col] pairs.",
            },
            "color": {"type": "string", "default": "YELLOW"},
        },
        "required": ["element_id", "cells"],
    },

    {
        "name": "draw_grid_arrow",
        "description": (
            "Draw a curved dependency arrow between two cells of the same "
            "2D grid. Use to visualize WHICH previous cell dp[i][j] was "
            "computed from. Color it differently per dependency direction "
            "(e.g. TEAL for dp[i-1][j], GREEN for dp[i][j-1])."
        ),
        "parameters": {
            "element_id": {"type": "string"},
            "from_row": {"type": "integer"},
            "from_col": {"type": "integer"},
            "to_row": {"type": "integer"},
            "to_col": {"type": "integer"},
            "color": {"type": "string", "default": "TEAL"},
            "label": {"type": "string", "default": None},
        },
        "required": ["element_id", "from_row", "from_col", "to_row", "to_col"],
    },

    # ── Collection operations ─────────────────────────────────────────────────

    {
        "name": "push_stack",
        "description": "Animate pushing a value onto the stack (slides in from top).",
        "parameters": {
            "element_id": {"type": "string"},
            "value": {"type": "string"},
            "color": {
                "type": "string",
                "enum": ["WHITE", "YELLOW", "GREEN", "RED", "ORANGE", "BLUE"],
                "default": "WHITE",
            },
        },
        "required": ["element_id", "value"],
    },

    {
        "name": "pop_stack",
        "description": "Animate popping the top value from the stack (slides out).",
        "parameters": {
            "element_id": {"type": "string"},
        },
        "required": ["element_id"],
    },

    {
        "name": "set_hashmap_entry",
        "description": "Add or update a key:value entry in a hashmap panel.",
        "parameters": {
            "element_id": {"type": "string"},
            "key": {"type": "string"},
            "value": {"type": "string"},
        },
        "required": ["element_id", "key", "value"],
    },

    {
        "name": "delete_hashmap_entry",
        "description": "Remove a key from a hashmap panel with a fade-out animation.",
        "parameters": {
            "element_id": {"type": "string"},
            "key": {"type": "string"},
        },
        "required": ["element_id", "key"],
    },

    {
        "name": "highlight_code_line",
        "description": "Highlight one line in the code panel yellow; dim the rest.",
        "parameters": {
            "element_id": {"type": "string", "description": "Code panel element_id."},
            "line_index": {"type": "integer", "description": "0-based line number."},
        },
        "required": ["element_id", "line_index"],
    },

    # ── Narrative / pacing ────────────────────────────────────────────────────

    {
        "name": "set_caption",
        "description": (
            "Set the bottom subtitle strip. Explains WHY this step matters. "
            "Call this at the start of each major step. "
            "Keep under 80 characters. Do NOT describe what's visually happening "
            "— the animation shows that. Explain the insight."
        ),
        "parameters": {
            "text": {"type": "string", "description": "Caption text (under 80 chars)."},
        },
        "required": ["text"],
    },

    {
        "name": "add_annotation",
        "description": (
            "Add a small italic label with an arrow pointing at a specific element. "
            "Use to call out an invariant, a key observation, or a named variable."
        ),
        "parameters": {
            "text": {"type": "string", "description": "Short label (under 40 chars)."},
            "element_id": {"type": "string", "description": "Element to point at."},
            "index": {
                "type": "integer",
                "description": "Cell index (for arrays/grids). Use -1 for the whole element.",
                "default": -1,
            },
            "annotation_id": {
                "type": "string",
                "description": "ID so you can fade_out_element this annotation later.",
                "default": "annotation_0",
            },
        },
        "required": ["text", "element_id"],
    },

    {
        "name": "emphasize",
        "description": (
            "Pulse-flash an element to draw the viewer's eye at a key insight moment. "
            "Use this exactly once per scene at the most important beat. "
            "If index is -1, the whole element flashes. "
            "Use pace='slow' for the aha moment (longer flash + built-in beat)."
        ),
        "parameters": {
            "element_id": {"type": "string"},
            "index": {
                "type": "integer",
                "description": "Cell index for arrays (use -1 for whole element).",
                "default": -1,
            },
            "pace": {
                "type": "string",
                "enum": ["slow", "normal", "fast"],
                "description": "Rhythm of the emphasis. 'slow' is the aha moment.",
                "default": "normal",
            },
        },
        "required": ["element_id"],
    },

    {
        "name": "show_result",
        "description": (
            "Display the final answer in a green result box with a pulse animation. "
            "Call this at the END of a scene to reveal the answer or conclusion."
        ),
        "parameters": {
            "value": {"type": "string", "description": "The result value or conclusion."},
            "label": {
                "type": "string",
                "description": "Optional label prefix, e.g. 'answer', 'max_sum', 'found at'.",
                "default": "",
            },
        },
        "required": ["value"],
    },

    {
        "name": "pause",
        "description": (
            "Insert a deliberate pause so the viewer can absorb what just happened. "
            "Use after the key insight moment (after emphasize). "
            "beats=1 is ~0.6s, beats=2 is ~1.2s. Default: 1."
        ),
        "parameters": {
            "beats": {"type": "integer", "minimum": 1, "maximum": 4, "default": 1},
        },
        "required": [],
    },

    {
        "name": "fade_out_element",
        "description": (
            "Fade out and remove an element from the screen. "
            "Use to clear the stage before a new idea, or remove a completed sub-result."
        ),
        "parameters": {
            "element_id": {"type": "string", "description": "Element to remove."},
        },
        "required": ["element_id"],
    },

    # ── Camera tools (Item #7) ────────────────────────────────────────────────
    # Move the viewport without changing scene content. Use sparingly — over-zooming
    # makes lessons feel fidgety. Use pan_to to focus on a single visual when
    # multiple are on screen, zoom_to for the aha moment, zoom_out to re-establish.

    {
        "name": "pan_to",
        "description": (
            "Pan the camera so the named element is centered. "
            "Use to direct attention without changing scene content."
        ),
        "parameters": {
            "element_id": {"type": "string", "description": "Element to center on."},
        },
        "required": ["element_id"],
    },

    {
        "name": "zoom_to",
        "description": (
            "Zoom the camera in on a specific element. "
            "Use ONCE per scene, at the moment a detail matters."
        ),
        "parameters": {
            "element_id": {"type": "string", "description": "Element to zoom toward."},
            "level": {
                "type": "number",
                "description": "Zoom factor >1 zooms in (1.5 = 1.5×). Keep ≤ 2.0.",
                "default": 1.5,
            },
        },
        "required": ["element_id"],
    },

    {
        "name": "zoom_out",
        "description": (
            "Reset zoom + camera position. "
            "Use after a zoom_to to re-establish the wider context."
        ),
        "parameters": {},
        "required": [],
    },

]

# Lookup for validation
VALID_TOOL_NAMES: frozenset[str] = frozenset(t["name"] for t in VISUAL_TOOLS)


_TOOL_GROUPS = {
    "## Element creation (what to put on screen)": [
        "show_array", "show_hashmap", "show_stack", "show_grid",
        "show_code", "show_text", "show_equation",
    ],
    "## Pointer tools": ["add_pointer", "move_pointer"],
    "## Cell / value operations": [
        "highlight_cells", "swap_cells", "set_cell_value",
        "set_grid_cell", "highlight_grid_cells", "draw_grid_arrow",
    ],
    "## Collection operations": [
        "push_stack", "pop_stack",
        "set_hashmap_entry", "delete_hashmap_entry",
        "highlight_code_line",
    ],
    "## Narrative / pacing (use these liberally)": [
        "set_caption", "add_annotation", "emphasize",
        "show_result", "pause", "fade_out_element",
    ],
    "## Camera (use sparingly — at most one zoom per scene)": [
        "pan_to", "zoom_to", "zoom_out",
    ],
}


def tool_catalog_prompt() -> str:
    """Grouped human-readable catalog for LLM system prompts."""
    by_name = {t["name"]: t for t in VISUAL_TOOLS}
    lines: list[str] = []
    for heading, names in _TOOL_GROUPS.items():
        lines.append(heading)
        for name in names:
            t = by_name.get(name)
            if not t:
                continue
            params = t.get("parameters", {})
            required = t.get("required", [])
            sig_parts = []
            for pname, pdef in params.items():
                default = pdef.get("default")
                sig_parts.append(pname if pname in required else f"{pname}={repr(default)}")
            sig = f"  {name}({', '.join(sig_parts)})"
            desc = t["description"].split(".")[0]
            lines.append(sig)
            lines.append(f"    → {desc}.")
        lines.append("")
    return "\n".join(lines)
