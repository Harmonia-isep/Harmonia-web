#!/bin/sh
# Bring the schema up to date, then hand off. Migrations run at startup rather
# than as a documented manual step: this is a single-user local app, and the
# alternative is a class of "no such table" bug reports. `alembic upgrade head`
# is idempotent, so a restart against a current database is a no-op.
set -e

echo "harmonia: running migrations against ${DATABASE_URL}"
alembic upgrade head

# exec so uvicorn becomes PID 1 and receives SIGTERM directly, which lets
# `docker stop` shut down cleanly instead of waiting out the timeout.
exec "$@"
