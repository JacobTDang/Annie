# Backend container — Python 3.11 + Manim + ffmpeg.
# Multi-stage isn't worth it here: Manim's runtime deps (cairo, pango, ffmpeg)
# are the same in build and runtime, and we want them in the final image.

FROM python:3.11-slim

# System deps Manim needs at runtime. Keep this list small — every package
# extends the image. texlive is intentionally NOT installed; we don't use the
# LaTeX-based MathTex helpers anywhere that's hot-path.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libffi-dev \
        ffmpeg \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cache layer for pip deps — copy requirements first so a code change doesn't
# bust the dep install layer.
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
WORKDIR /app/backend

# Render output lives here. Mounted as a volume in docker-compose so the
# frontend container (or a CDN sidecar) can serve it.
RUN mkdir -p /app/backend/media
ENV PYTHONPATH=/app/backend

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -fsS http://localhost:5000/health || exit 1

# Production CMD: gunicorn with 2 workers + 3-minute timeout (Manim renders
# can take ~60-180s). The Flask dev server is not safe for production.
# `--access-logfile -` streams Gunicorn access logs to container stdout so
# `fly logs` / `docker logs` show traffic.
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", \
     "--timeout", "180", \
     "--access-logfile", "-", \
     "app:create_app()"]
