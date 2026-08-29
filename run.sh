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
  ok "created"
fi

PY="$VENV/bin/python"

# ---------------------------------------------------------------------------
# Dependencies. Reinstalled only when pyproject.toml actually changes, so a
# second run does not sit through pip resolving scipy again.
# ---------------------------------------------------------------------------
PYPROJECT_SUM="$("$PY" - <<'PY'
import hashlib, pathlib
print(hashlib.sha256(pathlib.Path("pyproject.toml").read_bytes()).hexdigest())
PY
)"

if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$PYPROJECT_SUM" ]; then
  ok "dependencies already installed"
else
  info "Installing Python dependencies (this takes a few minutes the first time)"
  "$PY" -m pip install --upgrade pip >/dev/null
  if ! "$PY" -m pip install -e .; then
    die "Installing the Python dependencies failed. The output above says why."
  fi
  printf '%s' "$PYPROJECT_SUM" > "$STAMP"
  ok "installed"
fi

# ---------------------------------------------------------------------------
# Database. `upgrade head` is idempotent and quick, so it always runs: that is
# what keeps an existing install working after a version bump.
# ---------------------------------------------------------------------------
info "Applying database migrations"
if ! "$PY" -m alembic upgrade head; then
  die "Database migrations failed. The output above says why."
fi
ok "database ready"

# ---------------------------------------------------------------------------
# Frontend. Built once. Delete frontend/build to force a rebuild.
# ---------------------------------------------------------------------------
if [ -f "frontend/build/index.html" ]; then
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

  NODE_OK="$(node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.stdout.write((a>22||(a===22&&b>=12)||(a===20&&b>=19)||(a===21))?"yes":"no")')"
  if [ "$NODE_OK" != "yes" ]; then
    die "Node.js $(node -v) is too old to build the interface.

Harmonia needs Node.js 20.19+ or 22.12+.
  https://nodejs.org/"
  fi

  info "Building the web interface (first run only)"
  ( cd frontend && npm install && npm run build ) \
    || die "Building the web interface failed. The output above says why."
  [ -f "frontend/build/index.html" ] \
    || die "The build reported success but produced no frontend/build/index.html."
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

printf '\n'
info "Starting Harmonia on http://127.0.0.1:$PORT"
printf '    Press Ctrl+C to stop.\n\n'

open_when_ready &

# exec so Ctrl+C reaches uvicorn directly rather than this script.
exec "$PY" -m uvicorn --factory backend.main:create_app \
  --host 127.0.0.1 --port "$PORT"
