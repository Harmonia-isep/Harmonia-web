#!/usr/bin/env bash
#
# Harmonia launcher. Sets everything up the first time, then just starts the
# server on every run after that. Safe to run repeatedly.
#
#   ./run.sh
#
set -euo pipefail

cd "$(dirname "$0")"

PORT="${HARMONIA_PORT:-8000}"
VENV=".venv"
STAMP="$VENV/.harmonia-deps"

# The frontend bundle is built with VITE_API_URL unset, so it calls the API on
# whatever origin the page was served from. This stamp records that, so a bundle
# left behind by an older launcher (which baked in http://localhost:8000 and was
# therefore unusable at the 127.0.0.1 address this script prints) gets rebuilt
# instead of skipped.
FRONTEND_BUILD="frontend/build"
FRONTEND_STAMP="$FRONTEND_BUILD/.harmonia-frontend"
# No angle brackets or quotes in this value: run.bat writes the same stamp with
# `echo`, where they would be redirection operators.
FRONTEND_STAMP_WANT="VITE_API_URL-unset-same-origin"

info()  { printf '\033[1;36m==>\033[0m %s\n' "$1"; }
ok()    { printf '\033[1;32m  ok\033[0m %s\n' "$1"; }
die()   { printf '\033[1;31m\nError: %s\033[0m\n\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Prerequisites. Fail with something actionable, not a stack trace.
# ---------------------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
  die "Python 3 is not installed, or is not on your PATH.

Harmonia needs Python 3.11 or newer.
  Debian/Ubuntu:  sudo apt install python3 python3-venv
  Fedora:         sudo dnf install python3
  macOS:          brew install python@3.12
  Or download it: https://www.python.org/downloads/"
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  die "Python $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])') is too old.

Harmonia needs Python 3.11 or newer. Install a newer one and try again:
  https://www.python.org/downloads/"
fi

if ! python3 -c 'import venv' >/dev/null 2>&1; then
  die "Python is installed but the 'venv' module is missing.

On Debian and Ubuntu this ships separately:
  sudo apt install python3-venv"
fi

# ---------------------------------------------------------------------------
# Virtual environment. Created once.
# ---------------------------------------------------------------------------
if [ -x "$VENV/bin/python" ]; then
  ok "virtual environment already exists"
else
  info "Creating a virtual environment in $VENV"
  python3 -m venv "$VENV" || die "Could not create the virtual environment in $VENV."
  # venv can exit 0 and still leave no interpreter behind, so check for one.
  [ -x "$VENV/bin/python" ] \
    || die "Creating the virtual environment reported success but produced no
$VENV/bin/python."
  ok "created"
fi

PY="$VENV/bin/python"

# Console scripts, not `python -m`. Both work when the package is installed, but
# `-m alembic` reports a missing alembic as "'alembic' is a package and cannot be
# directly executed", because this repository has its own alembic/ migrations
# directory, which is the only candidate left when the real package is absent.
# That message sends you looking at the wrong thing.
ALEMBIC="$VENV/bin/alembic"
UVICORN="$VENV/bin/uvicorn"

# ---------------------------------------------------------------------------
# Dependencies. Reinstalled only when pyproject.toml actually changes, so a
# second run does not sit through pip resolving scipy again.
# ---------------------------------------------------------------------------
PYPROJECT_SUM="$("$PY" - <<'PY'
import hashlib, pathlib
print(hashlib.sha256(pathlib.Path("pyproject.toml").read_bytes()).hexdigest())
PY
)" || die "Could not read pyproject.toml to decide whether the dependencies need
installing. Check that you are running this script from inside the Harmonia
folder and that pyproject.toml is next to it."

# An empty hash would compare equal to an empty stamp and silently claim the
# dependencies were already installed.
[ -n "$PYPROJECT_SUM" ] \
  || die "Hashing pyproject.toml produced nothing. Refusing to guess whether the
dependencies are installed."

if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$PYPROJECT_SUM" ]; then
  ok "dependencies already installed"
else
  info "Installing Python dependencies (this takes a few minutes the first time)"
  "$PY" -m pip install --upgrade pip >/dev/null \
    || die "Upgrading pip failed. The output above says why."
  if ! "$PY" -m pip install -e .; then
    die "Installing the Python dependencies failed. The output above says why."
  fi
  # The stamp is written only after pip actually succeeded, so an install that
  # was interrupted is retried next run rather than skipped.
  printf '%s' "$PYPROJECT_SUM" > "$STAMP"
  ok "installed"
fi

# ---------------------------------------------------------------------------
# Database. `upgrade head` is idempotent and quick, so it always runs: that is
# what keeps an existing install working after a version bump.
# ---------------------------------------------------------------------------
info "Applying database migrations"
[ -x "$ALEMBIC" ] \
  || die "alembic is not installed in $VENV. The dependency install did not
complete. Remove the $VENV directory and run this script again."
if ! "$ALEMBIC" upgrade head; then
  die "Database migrations failed. The output above says why."
fi
ok "database ready"

# ---------------------------------------------------------------------------
# Frontend. Built once, and rebuilt if the bundle on disk was not built the way
# this script builds it. Delete frontend/build to force a rebuild.
# ---------------------------------------------------------------------------
if [ -f "$FRONTEND_BUILD/index.html" ] \
   && [ -f "$FRONTEND_STAMP" ] \
   && [ "$(cat "$FRONTEND_STAMP")" = "$FRONTEND_STAMP_WANT" ]; then
  ok "frontend already built"
else
  if ! command -v node >/dev/null 2>&1; then
    die "The web interface has not been built yet, and Node.js is not installed.

Harmonia needs Node.js 20.19+ or 22.12+ to build the interface, once.
  Download:       https://nodejs.org/
  Debian/Ubuntu:  https://github.com/nodesource/distributions
  macOS:          brew install node

You only need Node for this build step. It is not needed to run Harmonia
afterwards."
  fi
  if ! command -v npm >/dev/null 2>&1; then
    die "Node.js is installed but npm is not on your PATH.

npm ships with Node.js, so this usually means a partial install:
  https://nodejs.org/"
  fi

  # Version gate by exit code. Capturing "yes" or "no" would make a node that
  # crashed indistinguishable from a node that is too old.
  if ! node -e 'const v=process.versions.node.split(".").map(Number); process.exit((v[0]>22||(v[0]===22&&v[1]>=12)||v[0]===21||(v[0]===20&&v[1]>=19))?0:1)'; then
    die "Node.js $(node -v) is too old to build the interface.

Harmonia needs Node.js 20.19+ or 22.12+.
  https://nodejs.org/"
  fi

  info "Building the web interface (first run only)"
  # VITE_API_URL is explicitly unset rather than set to an empty string, so the
  # bundle that ships is the one produced by api.js's own default. That keeps
  # the default on a tested path: the e2e builds exactly this way, so a
  # regression back to an absolute API origin fails the suite instead of only
  # breaking users.
  ( cd frontend && npm install && env -u VITE_API_URL npm run build ) \
    || die "Building the web interface failed. The output above says why."
  [ -f "$FRONTEND_BUILD/index.html" ] \
    || die "The build reported success but produced no $FRONTEND_BUILD/index.html."
  # Written after the build: vite empties outDir, which would remove it.
  printf '%s' "$FRONTEND_STAMP_WANT" > "$FRONTEND_STAMP"
  ok "built"
fi

# ---------------------------------------------------------------------------
# Open a browser once the server answers, then hand the terminal to uvicorn.
# ---------------------------------------------------------------------------
open_when_ready() {
  local url="http://127.0.0.1:$PORT"
  for _ in $(seq 1 60); do
    if "$PY" - "$PORT" <<'PY' >/dev/null 2>&1
import socket, sys
s = socket.socket(); s.settimeout(1)
sys.exit(s.connect_ex(("127.0.0.1", int(sys.argv[1]))))
PY
    then
      if command -v xdg-open >/dev/null 2>&1; then xdg-open "$url" >/dev/null 2>&1 || true
      elif command -v open    >/dev/null 2>&1; then open "$url"     >/dev/null 2>&1 || true
      fi
      return
    fi
    sleep 1
  done
}

[ -x "$UVICORN" ] \
  || die "uvicorn is not installed in $VENV. The dependency install did not
complete. Remove the $VENV directory and run this script again."

printf '\n'
info "Starting Harmonia on http://127.0.0.1:$PORT"
printf '    Press Ctrl+C to stop.\n\n'

open_when_ready &

# exec so Ctrl+C reaches uvicorn directly rather than this script.
exec "$UVICORN" --factory backend.main:create_app \
  --host 127.0.0.1 --port "$PORT"
