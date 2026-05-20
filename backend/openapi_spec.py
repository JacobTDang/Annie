"""
OpenAPI 3.1 schema for the Lumen backend (Item #21).

Hand-written rather than scraped from decorators so the public contract stays
explicit. To regenerate a typed frontend client, run:

    npx openapi-typescript http://localhost:5000/openapi.json \\
        -o frontend/src/lib/apiSchema.ts

Only the endpoints the frontend actually depends on are described here — admin
+ debug routes are intentionally omitted to keep the surface small.
"""
from __future__ import annotations


def build_openapi_spec() -> dict:
    """Return the full OpenAPI 3.1 document as a JSON-serializable dict."""
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Lumen API",
            "version": "1.0.0",
            "description": (
                "Backend API for Lumen — AI math + DSA visualization tool. "
                "Renders Manim animations from natural-language questions."
            ),
        },
        "servers": [
            {"url": "http://localhost:5000", "description": "Local dev"},
        ],
        "paths": {
            "/health": {
                "get": {
                    "summary": "Liveness probe",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"},
                            }},
                        },
                    },
                },
            },
            "/topics": {
                "get": {
                    "summary": "List supported topics",
                    "responses": {
                        "200": {
                            "description": "topics list",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/TopicsResponse"},
                            }},
                        },
                    },
                },
            },
            "/ask": {
                "post": {
                    "summary": "Classify a natural-language question and render",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/AskRequest"},
                        }},
                    },
                    "responses": {
                        "202": {
                            "description": "queued",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/JobAccepted"},
                            }},
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "422": {"$ref": "#/components/responses/Unprocessable"},
                    },
                },
            },
            "/render": {
                "post": {
                    "summary": "Render a specific scene by name",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/RenderRequest"},
                        }},
                    },
                    "responses": {
                        "202": {
                            "description": "queued",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/JobAccepted"},
                            }},
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                    },
                },
            },
            "/status/{job_id}": {
                "get": {
                    "summary": "Poll a job's status",
                    "parameters": [
                        {"name": "job_id", "in": "path", "required": True,
                         "schema": {"type": "string"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "status snapshot",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/JobStatus"},
                            }},
                        },
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                },
            },
            "/api/direct-lesson": {
                "post": {
                    "summary": "Submit a lesson via the Lesson Director agent",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/DirectLessonRequest"},
                        }},
                    },
                    "responses": {
                        "202": {
                            "description": "queued",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/JobAccepted"},
                            }},
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                    },
                },
            },
            "/api/direct-lesson-stream": {
                "post": {
                    "summary": "SSE variant of /api/direct-lesson — streams stage transitions",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/DirectLessonRequest"},
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "event stream",
                            "content": {"text/event-stream": {
                                "schema": {"type": "string"},
                            }},
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                    },
                },
            },
            "/api/share": {
                "post": {
                    "summary": "Create a shareable short code for a finished job",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/ShareRequest"},
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "share record",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/ShareRecord"},
                            }},
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                    },
                },
            },
            "/api/share/{code}": {
                "get": {
                    "summary": "Resolve a share code into its lesson metadata",
                    "parameters": [
                        {"name": "code", "in": "path", "required": True,
                         "schema": {"type": "string", "pattern": "^[A-Za-z0-9]+$"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "share record",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/ShareRecord"},
                            }},
                        },
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                },
            },
            "/api/pin": {
                "post": {
                    "summary": "Pin a rendered video so cleanup keeps it on disk",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/PinRequest"},
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "pinned",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/PinResponse"},
                            }},
                        },
                    },
                },
            },
            "/api/pin/{job_id}": {
                "delete": {
                    "summary": "Unpin a rendered video (idempotent)",
                    "parameters": [
                        {"name": "job_id", "in": "path", "required": True,
                         "schema": {"type": "string"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "unpinned (or no-op)",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/OkResponse"},
                            }},
                        },
                    },
                },
            },
            "/api/share/mine": {
                "get": {
                    "summary": "List shares owned by the authenticated caller",
                    "responses": {
                        "200": {
                            "description": "owned shares",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/MySharesResponse"},
                            }},
                        },
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                    },
                },
            },
            "/api/quiz-attempt": {
                "post": {
                    "summary": "Record a quiz attempt (authenticated users only — 204 for anonymous)",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/QuizAttemptRequest"},
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "stored",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/QuizAttemptResponse"},
                            }},
                        },
                        "204": {"description": "anonymous; skipped silently"},
                        "400": {"$ref": "#/components/responses/BadRequest"},
                    },
                },
            },
            "/api/render-lesson": {
                "post": {
                    "summary": "Submit a multi-scene lesson for parallel render + stitch",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/RenderLessonRequest"},
                        }},
                    },
                    "responses": {
                        "202": {
                            "description": "queued",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/JobAccepted"},
                            }},
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                    },
                },
            },
            "/api/parse-problem-v2": {
                "post": {
                    "summary": "Classify and parse a problem (math or DSA) — primary parser",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/ParseProblemRequest"},
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "parsed problem",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/ParsedProblem"},
                            }},
                        },
                        "422": {"$ref": "#/components/responses/Unprocessable"},
                    },
                },
            },
            "/api/parse-problem": {
                "post": {
                    "summary": "Legacy parser endpoint — prefer /api/parse-problem-v2",
                    "deprecated": True,
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/ParseProblemRequest"},
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "parsed problem",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/ParsedProblem"},
                            }},
                        },
                    },
                },
            },
            "/api/parse-followup": {
                "post": {
                    "summary": "Parse a conversational follow-up against a prior parse",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/ParseFollowupRequest"},
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "updated parsed problem",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/ParsedProblem"},
                            }},
                        },
                    },
                },
            },
            "/api/parse-leetcode": {
                "post": {
                    "summary": "Parse a raw LeetCode problem text into a renderable scene",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/ParseProblemRequest"},
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "parsed problem",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/ParsedProblem"},
                            }},
                        },
                    },
                },
            },
            "/api/fetch-leetcode": {
                "post": {
                    "summary": "Fetch + parse a LeetCode problem by URL",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/FetchLeetcodeRequest"},
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "parsed problem",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/ParsedProblem"},
                            }},
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                    },
                },
            },
            "/api/ocr": {
                "post": {
                    "summary": "Run OCR over an uploaded image, returning extracted text",
                    "requestBody": {
                        "required": True,
                        "content": {"multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["image"],
                                "properties": {
                                    "image": {"type": "string", "format": "binary"},
                                },
                            },
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "extracted text",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/OcrResponse"},
                            }},
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                    },
                },
            },
            "/api/format-note": {
                "post": {
                    "summary": "Clean / format a raw OCR / pasted note for display",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/FormatNoteRequest"},
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "formatted note",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/FormatNoteResponse"},
                            }},
                        },
                    },
                },
            },
            "/api/breakdown": {
                "post": {
                    "summary": "Generate a step-by-step breakdown for a parsed problem",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/BreakdownRequest"},
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "breakdown sections",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/BreakdownResponse"},
                            }},
                        },
                    },
                },
            },
            "/api/quiz": {
                "post": {
                    "summary": "Generate a small quiz from a parsed problem",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/QuizRequest"},
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "quiz questions",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/QuizResponse"},
                            }},
                        },
                    },
                },
            },
            "/api/topics": {
                "get": {
                    "summary": "List supported topics (alias for /topics)",
                    "responses": {
                        "200": {
                            "description": "topics list",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/TopicsResponse"},
                            }},
                        },
                    },
                },
            },
            "/api/trace/{job_id}": {
                "get": {
                    "summary": "Return per-job LLM + render trace for the debug panel",
                    "parameters": [
                        {"name": "job_id", "in": "path", "required": True,
                         "schema": {"type": "string"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "trace snapshot",
                            "content": {"application/json": {
                                "schema": {"type": "object", "additionalProperties": True},
                            }},
                        },
                        "404": {"$ref": "#/components/responses/NotFound"},
                    },
                },
            },
            "/api/prereqs": {
                "get": {
                    "summary": "Topic prerequisite graph by domain (Item #35)",
                    "responses": {
                        "200": {
                            "description": "prereq graph",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/PrereqsResponse"},
                            }},
                        },
                        "500": {"$ref": "#/components/responses/BadRequest"},
                    },
                },
            },
            "/api/public/recent": {
                "get": {
                    "summary": "List the N most-recent public shares for discovery",
                    "parameters": [
                        {"name": "limit", "in": "query", "required": False,
                         "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 30}},
                    ],
                    "responses": {
                        "200": {
                            "description": "public shares",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/PublicSharesResponse"},
                            }},
                        },
                    },
                },
            },
            "/breakdown": {
                "post": {
                    "summary": "Legacy alias for /api/breakdown",
                    "deprecated": True,
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {
                            "schema": {"$ref": "#/components/schemas/BreakdownRequest"},
                        }},
                    },
                    "responses": {
                        "200": {
                            "description": "breakdown sections",
                            "content": {"application/json": {
                                "schema": {"$ref": "#/components/schemas/BreakdownResponse"},
                            }},
                        },
                    },
                },
            },
        },
        "components": {
            "responses": {
                "BadRequest": {
                    "description": "validation error",
                    "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    }},
                },
                "NotFound": {
                    "description": "not found",
                    "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    }},
                },
                "Unprocessable": {
                    "description": "agent or classifier failure",
                    "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    }},
                },
                "Unauthorized": {
                    "description": "auth required or token rejected",
                    "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                    }},
                },
            },
            "schemas": {
                "HealthResponse": {
                    "type": "object",
                    "required": ["status"],
                    "properties": {
                        "status": {"type": "string", "enum": ["ok"]},
                    },
                },
                "TopicsResponse": {
                    "type": "object",
                    "required": ["topics"],
                    "properties": {
                        "topics": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
                "ErrorResponse": {
                    "type": "object",
                    "required": ["error"],
                    "properties": {
                        "error": {"type": "string"},
                    },
                },
                "AskRequest": {
                    "type": "object",
                    "required": ["question"],
                    "properties": {
                        "question": {"type": "string", "minLength": 1},
                    },
                },
                "RenderRequest": {
                    "type": "object",
                    "required": ["scene", "params"],
                    "properties": {
                        "scene": {"type": "string"},
                        "params": {"type": "object", "additionalProperties": True},
                    },
                },
                "DirectLessonRequest": {
                    "type": "object",
                    "required": ["question"],
                    "properties": {
                        "question": {"type": "string", "minLength": 1},
                        "style": {
                            "type": "string",
                            "enum": ["intuition_first", "rigor_first",
                                     "socratic", "speedrun"],
                        },
                        "target_minutes": {
                            "type": "number",
                            "minimum": 0.5,
                            "maximum": 10.0,
                            "default": 1.5,
                        },
                    },
                },
                "JobAccepted": {
                    "type": "object",
                    "required": ["job_id"],
                    "properties": {
                        "job_id": {"type": "string", "format": "uuid"},
                        "scene": {"type": "string"},
                    },
                },
                "JobStatus": {
                    "type": "object",
                    "required": ["status"],
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["pending", "done", "error"],
                        },
                        "url": {"type": ["string", "null"]},
                        "error": {"type": ["string", "null"]},
                        "stage": {"type": "string"},
                        "progress": {"type": "number"},
                    },
                },
                "ShareRequest": {
                    "type": "object",
                    "required": ["job_id"],
                    "properties": {
                        "job_id": {"type": "string"},
                        "title": {"type": "string"},
                    },
                },
                "ShareRecord": {
                    "type": "object",
                    "required": ["code", "url"],
                    "properties": {
                        "code": {"type": "string"},
                        "url": {"type": "string"},
                        "title": {"type": "string"},
                        "created_at": {"type": "string", "format": "date-time"},
                    },
                },
                "PinRequest": {
                    "type": "object",
                    "required": ["job_id"],
                    "properties": {
                        "job_id": {"type": "string"},
                    },
                },
                "PinResponse": {
                    "type": "object",
                    "required": ["pinned"],
                    "properties": {
                        "pinned": {"type": "boolean"},
                    },
                },
                "OkResponse": {
                    "type": "object",
                    "required": ["ok"],
                    "properties": {"ok": {"type": "boolean"}},
                },
                "MyShareSummary": {
                    "type": "object",
                    "required": ["code", "title"],
                    "properties": {
                        "code": {"type": "string"},
                        "title": {"type": "string"},
                        "scene": {"type": ["string", "null"]},
                        "domain": {"type": ["string", "null"]},
                        "is_public": {"type": "boolean"},
                        "created_at": {"type": ["integer", "null"]},
                    },
                },
                "MySharesResponse": {
                    "type": "object",
                    "required": ["shares"],
                    "properties": {
                        "shares": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/MyShareSummary"},
                        },
                    },
                },
                "PublicSharesResponse": {
                    "type": "object",
                    "required": ["shares"],
                    "properties": {
                        "shares": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/MyShareSummary"},
                        },
                    },
                },
                "QuizAttemptRequest": {
                    "type": "object",
                    "required": ["scene", "correct"],
                    "properties": {
                        "scene": {"type": "string"},
                        "correct": {"type": "boolean"},
                        "question_index": {"type": ["integer", "null"]},
                    },
                },
                "QuizAttemptResponse": {
                    "type": "object",
                    "required": ["stored"],
                    "properties": {"stored": {"type": "boolean"}},
                },
                "RenderLessonStep": {
                    "type": "object",
                    "required": ["scene"],
                    "properties": {
                        "scene": {"type": "string"},
                        "params": {"type": "object", "additionalProperties": True},
                        "caption": {"type": "string"},
                    },
                },
                "RenderLessonRequest": {
                    "type": "object",
                    "required": ["steps"],
                    "properties": {
                        "steps": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 6,
                            "items": {"$ref": "#/components/schemas/RenderLessonStep"},
                        },
                    },
                },
                "ParseProblemRequest": {
                    "type": "object",
                    "required": ["text"],
                    "properties": {
                        "text": {"type": "string", "minLength": 1, "maxLength": 4000},
                    },
                },
                "ParseFollowupRequest": {
                    "type": "object",
                    "required": ["text", "prior"],
                    "properties": {
                        "text": {"type": "string"},
                        "prior": {"$ref": "#/components/schemas/ParsedProblem"},
                    },
                },
                "FetchLeetcodeRequest": {
                    "type": "object",
                    "required": ["url"],
                    "properties": {
                        "url": {"type": "string", "format": "uri"},
                    },
                },
                "OcrResponse": {
                    "type": "object",
                    "required": ["text"],
                    "properties": {
                        "text": {"type": "string"},
                    },
                },
                "FormatNoteRequest": {
                    "type": "object",
                    "required": ["text"],
                    "properties": {"text": {"type": "string"}},
                },
                "FormatNoteResponse": {
                    "type": "object",
                    "required": ["text"],
                    "properties": {"text": {"type": "string"}},
                },
                "BreakdownRequest": {
                    "type": "object",
                    "required": ["topicName"],
                    "properties": {
                        "topicName": {"type": "string"},
                        "topicDescription": {"type": "string"},
                        "problem": {"type": "string"},
                    },
                },
                "BreakdownResponse": {
                    "type": "object",
                    "required": ["sections"],
                    "properties": {
                        "sections": {
                            "type": "array",
                            "items": {"type": "object", "additionalProperties": True},
                        },
                    },
                },
                "QuizRequest": {
                    "type": "object",
                    "required": ["prior"],
                    "properties": {
                        "prior": {"$ref": "#/components/schemas/ParsedProblem"},
                    },
                },
                "QuizQuestion": {
                    "type": "object",
                    "required": ["q", "options", "correct"],
                    "properties": {
                        "q": {"type": "string"},
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                        },
                        "correct": {"type": "integer", "minimum": 0},
                        "why": {"type": "string"},
                    },
                },
                "QuizResponse": {
                    "type": "object",
                    "required": ["questions"],
                    "properties": {
                        "questions": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/QuizQuestion"},
                        },
                    },
                },
                "ParsedProblem": {
                    "type": "object",
                    "description": (
                        "Output shape of /api/parse-problem-v2 and friends. "
                        "Loose schema — fields vary by domain (math vs DSA)."
                    ),
                    "required": ["scene"],
                    "properties": {
                        "scene": {"type": "string"},
                        "title": {"type": "string"},
                        "domain": {"type": "string"},
                        "params": {"type": "object", "additionalProperties": True},
                        "pseudocode": {"type": "string"},
                        "step_lines": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "steps": {
                            "type": "array",
                            "items": {"type": "object", "additionalProperties": True},
                        },
                        "alternatives": {
                            "type": "array",
                            "items": {"type": "object", "additionalProperties": True},
                        },
                    },
                    "additionalProperties": True,
                },
                "PrereqsResponse": {
                    "type": "object",
                    "required": ["domains"],
                    "properties": {
                        "domains": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "object",
                                "additionalProperties": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        },
    }
