# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build the frontend. Node exists only here, so the final image ships
# the ~350 KB of built assets and no node_modules.
# ---------------------------------------------------------------------------
FROM node:22-slim AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Same-origin: one process serves the API and the UI, so the bundle uses
# relative URLs rather than baking in a host and port.
ENV VITE_API_URL=""
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: the application.
#
# Debian slim rather than Alpine on purpose: numpy, scipy, scikit-learn, numba
# and llvmlite ship manylinux wheels, which are glibc-only. On musl they would
# have to be compiled from source, including LLVM.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS app

# ffmpeg is a declared system dependency, not a redistributed binary. It is
# needed for .m4a and .aac only; libsndfile already handles .mp3, .wav, .flac,
# .ogg and .opus. Installing it makes the image cover the whole scan whitelist.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so a source-only change does not reinstall scipy.
COPY pyproject.toml README.md ./
COPY backend/ ./backend/
RUN pip install --no-cache-dir -e .

COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY --from=frontend /build/build ./frontend/build

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# The database, uploads and extracted artwork all live on one volume, so they
# survive `docker rm`. Both variables are read at call time by create_app and
# backend/storage.py, so no code path is container-specific.
ENV DATABASE_URL=sqlite:////data/harmonia.db \
    HARMONIA_UPLOAD_DIR=/data/uploads \
    PYTHONUNBUFFERED=1

# Non-root. uid 1000 matches the usual first host user, so a read-only bind
# mount of a music folder is readable without extra flags.
RUN useradd --create-home --uid 1000 harmonia \
    && mkdir -p /data /music \
    && chown -R harmonia:harmonia /data /app
USER harmonia

VOLUME ["/data"]
EXPOSE 8000

# No curl in slim, so probe with the interpreter that is already here. Hitting
# a real endpoint proves the app and the database are both up, not just the port.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/tracks/', timeout=4).status == 200 else 1)"

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "--factory", "backend.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
