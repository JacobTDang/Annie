# Lumen

AI-powered math + DSA visualization tool. Paste a problem, get an animated walkthrough.

Highlight any concept in your notes → click **Analyze** → the agent picks a visualization, plans a multi-scene lesson, and renders it as a Manim animation. Run the algorithm yourself in a browser-side Python editor. Save lessons to your library for offline replay.

## Quick start

Windows: double-click `start.bat` (launches backend + frontend in separate windows, press any key to stop both).

Manual:
```bash
# Backend (Python 3.11)
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cd backend && python app.py            # serves on :5000

# Frontend (Node 18+)
cd frontend && npm install && npm run dev   # serves on :5173
```

Open http://localhost:5173.

## Stack

**Backend:** Python 3.11, Flask, Manim (Community 0.20), LangChain + OpenRouter, Google Gemini (vision/OCR), ffmpeg (scene stitching)

**Frontend:** React 18, TypeScript, Vite, Tailwind, framer-motion, Monaco editor, Pyodide (browser Python), KaTeX, IndexedDB

**LLM stack:** `openai/gpt-oss-120b` (OpenRouter, reasoning) → `llama-3.3-70b` (Groq) → free fallback

## Features

| Feature | What it does |
|---|---|
| **Highlight-to-analyze** | Select any text in a note → "Analyze" → full visualization in a side panel |
| **Lesson Director agent** | Two-phase agent: plans narrative arc → composes scenes from 24 visual tools |
| **Stage timeline** | Live progress (`planning_narrative → building_scenes → rendering_X_of_N → stitching → done`) |
| **Multi-scene lessons** | Parallel render of 2–4 scenes, stitched with ffmpeg, content-addressable cache |
| **In-browser Python editor** | Monaco + Pyodide — run your own solution against the same inputs the agent used |
| **Library** | Save renders to IndexedDB + pin on backend; survives both cleanup and offline use |
| **Quiz mode** | Gemini-generated comprehension questions after each render |
| **Voice narration** | Offline browser SpeechSynthesis reads the explanation aloud |
| **Side-by-side comparison** | Render the primary + alternative approach concurrently with synced playback |
| **Shareable links** | Save a render under a short code; `/r/<code>` deep-links into the analysis panel |

## API surface

Frontend polls `/status/<job_id>` and reads `{status, url, error, progress, stage}` on every tick.

```
POST /ask                      → classify + plan + render (hardcoded scene path)
POST /api/direct-lesson        → Lesson Director agent (tool-composed scenes)
POST /api/render-lesson        → render N pre-built steps in parallel
POST /render                   → render a single scene
GET  /status/<job_id>          → poll job state (progress + stage)

POST /api/parse-problem-v2     → universal math/DSA parser
POST /api/parse-followup       → conversational refinement
POST /api/fetch-leetcode       → fetch a problem by leetcode.com URL

POST /api/ocr                  → image/PDF → text (Gemini vision)
POST /api/breakdown            → 3-section problem explanation
POST /api/quiz                 → comprehension MCQs from a render
POST /api/share                → save a parsed problem under a short code
GET  /api/share/<code>         → retrieve a shared problem
POST /api/pin / DELETE /api/pin/<id> → protect a render from cleanup
```

## Project structure

```
backend/
├── app.py                          Flask entry + all routes
├── agent/
│   ├── llm_client.py               Shared LLM stack (gpt-oss-120b → Groq → free)
│   ├── classifier.py               math vs DSA routing
│   ├── planner.py, dsa_planner.py  Hardcoded-scene planners (legacy /ask path)
│   ├── math_parser.py              Pasted math → scene + steps + alternatives
│   ├── leetcode_parser.py          Pasted LeetCode → scene + pseudocode
│   ├── lesson_director.py          Tool-based agent (narrative_plan + build_scene)
│   └── explainer.py, gemini_client.py
├── scenes/
│   ├── dsa_primitives.py           ArrayStrip, Pointer, HashMapPanel, … (visual tools)
│   ├── tool_executor.py            DynamicScene + ToolExecutor for agent renders
│   ├── calculus_scene.py           21 calculus scenes
│   ├── dsa_pattern_scene.py        19 DSA pattern scenes (kadanes, dijkstra, …)
│   ├── dsa_scene.py                7 legacy DSA scenes (array_pointer, sliding_window, …)
│   ├── algebra_scene.py, arithmetic_scene.py, threed_scene.py, trig_scene.py
│   └── array_scene.py              Sort scenes
├── schemas/
│   ├── types.py                    Pydantic schemas for every scene + LessonPlan
│   └── tools.py                    24 visual tools for the Lesson Director
├── renderer/worker.py              Job state, parallel render, ffmpeg stitch, cache, pin
├── tests/                          286 unit tests (`pytest -m "not integration"`)
└── media/                          Rendered videos (gitignored)

frontend/
├── src/
│   ├── App.tsx                     Router, sidebar, HomePage, NotesPage, NoteEditor, …
│   ├── pages/
│   │   ├── PasteProblemPage.tsx    Analysis panel (embedded in notes via highlight)
│   │   └── LibraryPage.tsx         Saved videos grid + inline player
│   ├── components/
│   │   ├── StageTimeline.tsx       Live stage UI for renders
│   │   └── ErrorBoundary.tsx
│   ├── lib/
│   │   ├── api.ts                  All backend HTTP + live progress/stage hooks
│   │   ├── videoStore.ts           IndexedDB wrapper
│   │   ├── savedVideos.ts          Library metadata + thumbnail generator
│   │   └── runPython.ts            Pyodide execution wrapper
│   ├── usePyodide.ts               Lazy CDN load of Python-in-browser
│   ├── CodeEditorPanel.tsx         Monaco editor + run/output panel
│   ├── MathContent.tsx             KaTeX with fallback
│   ├── theme.ts, types.ts          Shared design tokens + interfaces
│   └── react-katex.d.ts            Type shim
└── vite.config.ts                  manualChunks for monaco + katex

start.bat / start.ps1               Launch both servers, press any key to stop
```

## Environment

`backend/.env`:
```
OPENROUTER_API_KEY=             # required — primary LLM
OPENROUTER_GPT_OSS_120_KEY=     # optional — uses gpt-oss-120b with reasoning
GROQ_API_KEY=                   # optional — fast fallback
GEMINI_API_KEY=                 # optional — OCR + quiz generation
```

`frontend/.env` (copy from `.env.example`):
```
VITE_FLASK_URL=http://localhost:5000
```

## Testing

```bash
# Backend unit suite (~10s, no Manim or LLM calls)
venv/Scripts/python.exe -m pytest backend/tests/ -m "not integration"

# Integration: real Manim renders + real LLM calls (slow)
venv/Scripts/python.exe -m pytest backend/tests/ -m integration

# Frontend type check + production build
cd frontend && npx tsc --noEmit && npm run build
```

Current status: **286 unit tests passing**, frontend builds clean at ~345 kB initial JS (monaco + katex code-split into lazy chunks).

## Adding a new scene type

1. Implement the scene class in `backend/scenes/<file>.py`
2. Register in `backend/renderer/worker.py::SCENE_REGISTRY`
3. Add a Pydantic schema to `backend/schemas/types.py`
4. (For LeetCode parser routing) add to `agent/leetcode_parser.py::_SCENE_SCHEMAS`

For tool-composed scenes via the Lesson Director, you usually don't need a new scene class — extend `backend/schemas/tools.py` and `backend/scenes/tool_executor.py` instead.

## Deploying to Fly.io

Two apps, one repo. Both Dockerfiles already exist (Item #16). The Fly configs
are at `fly.toml` (backend) and `frontend/fly.toml`. The setup is one-time per
app; deploys after that are `fly deploy` (or use the manual GitHub Actions
workflow at `.github/workflows/deploy.yml`).

```bash
# Backend (one time)
fly launch --name lumen-api --no-deploy
fly secrets set OPENROUTER_API_KEY=… GROQ_API_KEY=…
fly volumes create lumen_media --size 1   # persists /app/backend/media
fly deploy

# Frontend (one time, from repo root)
fly launch --config frontend/fly.toml --name lumen-web --no-deploy
fly deploy --config frontend/fly.toml
```

The frontend's nginx config templates `${BACKEND_HOST}` at boot, so it talks
to `lumen-api.internal` on Fly and to the docker-compose `backend` service
locally — same image, no rebuild.

If you renamed the backend app (e.g. `fly launch --name lumen-prod`),
override the host on the frontend so the proxy points at the right place:

```bash
fly secrets set BACKEND_HOST=lumen-prod.internal \
  --config frontend/fly.toml --app lumen-web
```

Manual redeploys from GitHub: Actions → "deploy" workflow → Run workflow
(needs `FLY_API_TOKEN` as a repository secret).
