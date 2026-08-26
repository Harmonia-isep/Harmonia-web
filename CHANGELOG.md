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
- Chunk 2: introduced Alembic with a single baseline migration and a constraint naming
  convention. Removed `Base.metadata.create_all` from startup, so the schema is now owned
  by migrations; `env.py` resolves `DATABASE_URL` through the same path as `create_app`.
  Tests run the migration chain instead of `create_all`, and CI asserts the chain is
  complete (`alembic upgrade head` then `alembic check`).
- Chunk 3: added real `ON DELETE CASCADE` to every foreign key with `passive_deletes` on
  the parent relationships, so the database performs cascades; removed the hand-rolled
  child-deletion loops from `delete_track` and `delete_playlist`. Dropped the redundant
  `index=True` from the primary-key `id` columns (it duplicated the implicit PK index).
  Added a test proving the cascade fires at the database level.
- Chunk 4: the app serves the built frontend when present. `create_app` conditionally
  mounts StaticFiles and registers a scoped SPA catch-all (registered last, and it refuses
  `api/`, `docs`, `openapi.json`, `redoc`), so client-side routes resolve on refresh
  without shadowing the API or docs; a missing build logs a warning and serves the API
  only. The e2e suite now runs a single same-origin server, retiring the split-origin CORS
  workaround. CORS middleware stays for the split-origin dev flow (CRA on :3000).

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
