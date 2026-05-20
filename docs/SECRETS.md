# Secrets & environment variables

This document is the canonical reference for every secret Lumen reads.
All entries live in **two places**:

1. `backend/.env` — local-only, gitignored. Copied from `backend/.env.example`.
2. **GitHub Actions Secrets** — referenced from the CI workflows.

If a secret is in the table below but missing from either place, treat that
as a bug. CI should fail fast when a required secret is unset.

---

## Quick start

```bash
cp backend/.env.example backend/.env
# fill in at least OPENROUTER_API_KEY (free at openrouter.ai)
.\venv\Scripts\Activate.ps1
python backend/app.py
```

You can render lessons with just **one** LLM key set — the agent falls
through the provider list and uses whichever responds first.

---

## Variable reference

| Variable | Required | Where used | Default | Notes |
|---|---|---|---|---|
| `OPENROUTER_API_KEY` | Yes (or Groq) | `agent/llm_client.py` | — | Free tier at openrouter.ai |
| `OPENROUTER_BASE_URL` | No | `agent/llm_client.py` | `https://openrouter.ai/api/v1` | |
| `OPENROUTER_MODEL` | No | `agent/llm_client.py` | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | |
| `GROQ_API_KEY` | Yes (or OpenRouter) | `agent/llm_client.py` | — | Free tier at console.groq.com |
| `GROQ_PLANNER_MODEL` | No | `agent/llm_client.py` | `llama-3.3-70b-versatile` | |
| `GROQ_CLASSIFIER_MODEL` | No | `agent/classifier.py` | `llama-3.1-8b-instant` | |
| `GEMINI_API_KEY` | No | `agent/llm_client.py` | — | Fallback only |
| `SENTRY_DSN` | No | `app.py::_init_sentry` | — | When unset, Sentry is disabled entirely. |
| `SENTRY_TRACES_RATE` | No | `app.py::_init_sentry` | `0.1` | Float 0.0-1.0 |
| `LUMEN_ENV` | No | `app.py::_init_sentry` | `dev` | Tag used by Sentry events |
| `LUMEN_RATE_LIMIT` | No | `app.py` (Item #18) | `10` | Requests/IP/window. `0` disables. |
| `LUMEN_RATE_LIMIT_WINDOW_SECONDS` | No | `app.py` (Item #18) | `86400` | Default 24h window |
| `LUMEN_TTS_ENABLED` | No | `agent/tts.py` (Item #8) | `0` | Set `1` to enable narration mux |
| `LUMEN_TTS_VOICE` | No | `agent/tts.py` | `en-US-AriaNeural` | edge-tts voice name |
| `LUMEN_MAX_TOOL_CALLS` | No | `scenes/tool_executor.py` | `20` | Hard cap per scene |

---

## GitHub Actions secrets

The CI workflows in `.github/workflows/` reference the same names. Add each
secret at **Settings → Secrets and variables → Actions → New repository secret**.

Required for the integration job:

- `OPENROUTER_API_KEY`
- `GROQ_API_KEY`

Optional (the corresponding feature is silently disabled if unset):

- `SENTRY_DSN`
- `GEMINI_API_KEY`

After adding secrets, the workflow exposes them as env vars via the standard
pattern:

```yaml
- name: Run integration tests
  env:
    OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
    GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
  run: pytest backend/tests/ -v -m integration
```

---

## Rotation & hygiene

- **Never** commit a real key, even in a comment or a `.example` file. The
  `.env.example` ships placeholder values like `your_openrouter_key_here`.
- If a key leaks (pushed to git, posted in a chat), rotate it at the
  provider and add a new GitHub Actions secret value the same day.
- `git secret` / `pre-commit` hooks scanning for `*_API_KEY=sk-` patterns
  are a good belt-and-suspenders defense — recommended but not enforced
  in this repo.
