# Changelog

Notable changes to Harmonia. The format loosely follows Keep a Changelog. Before the
public release, work is tracked by rebuild phase (see HARMONIA_REBUILD_PLAN.md). The
academic submission is preserved under the `v0.1.0-academic` tag.

## Unreleased

### Phase 2: de-cloud (in progress)
- Chunk 1: added a `create_app()` factory and moved all configuration to call time. There
  is no module-level engine, session factory, or app instance. `DATABASE_URL` now defaults
  to a local SQLite file, so a fresh clone imports and runs with no `.env`. SQLite
  connections turn on foreign-key enforcement via a `PRAGMA foreign_keys=ON` event
  listener (SQLite only); the background analysis task takes an explicit session factory.
  Removed the `CORS_ORIGINS` env-var workaround from the test suite.

### Phase 1: dependency and packaging hygiene
- Removed the unused crypto pins (bcrypt, passlib, python-jose, ecdsa, rsa).
- Added `pyproject.toml` (project metadata, dependencies, `dev` and `e2e` extras) and a
  ruff configuration. DSP dependencies are upper-bounded and `requirements.lock` fixes
  exact versions for reproducibility.
- Restricted CORS to explicit, env-configurable origins and dropped credentials.
- Added GitHub Actions CI (Python 3.11/3.12/3.13; install from the lock; ruff; pytest with
  e2e excluded) plus a non-blocking unpinned drift job.
- Normalized line endings (`.gitattributes`), added a `commit-msg` hook, and tracked
  `CLAUDE.md`.
