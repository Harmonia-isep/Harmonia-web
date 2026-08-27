# Harmonia: Open-Source Rebuild Plan

**Handoff document for Claude Code.** Save this at the repo root and reference it at the
start of each session. It is both the brief and the running plan.

---

## 0. Context

Harmonia is a music analysis and DJ-assistance web platform: it computes BPM, key/scale,
energy and danceability from audio files and recommends harmonically compatible tracks
using the Camelot wheel. It was built as a third-year LEI capstone at ISEP
(supervisor: Prof. Carlos Ferreira). The academic phase is finished and defended.

**Repo:** `Harmonia-isep/Harmonia-web`, branch `develop`, HEAD `1c865f3`
**Stack today:** FastAPI + SQLAlchemy + librosa backend, Create React App frontend,
deployed on Render (backend) with Neon (Postgres).
**Runtime:** WSL Ubuntu, Python 3.12.3, packages installed system-wide (no venv).
**Installed DSP:** librosa 0.11.0, numpy 2.4.4, scipy 1.17.1, soundfile 0.13.1.
**Tests:** 53 items / 84% as measured on `1c865f3` (the figure in the project report);
51 passed / 2 failed / 81% on `577e5c2` because commit `812b784` gave `run_analysis` a
2-arg signature but left two test call sites passing 3 args (the merge inherited this red
state rather than causing it); green again from `086a904` onward.

### The goal

Turn Harmonia from a cloud-hosted school prototype into a **production-quality,
open-source, locally deployable tool** that anyone can clone and run. Every free-tier
constraint that shaped the original architecture is being removed:

| Constraint | Consequence in the current code | Now |
|---|---|---|
| Render 512MB RAM | `chroma_stft` instead of `chroma_cqt`, 45s audio cap | Gone |
| Render free tier CPU | No HPSS, no segmentation, single in-process worker | Gone |
| Neon idle connection drops | Retry/polling workarounds | Gone |
| Multi-tenant web deployment | User accounts, ownership filtering | Gone |

The single most important deliverable is **a measured accuracy table in the README**,
benchmarked against public ground truth. That table is the credibility of the project.
Infrastructure choices are secondary to it.

---

## 1. Decisions already made (do not re-litigate)

1. **Database:** SQLite is the default (`sqlite:///./harmonia.db`), Postgres remains
   available via `DATABASE_URL`. The audit confirmed zero Postgres-specific types, so
   this is nearly free. Alembic gets introduced with one baseline migration.

2. **Auth: deleted entirely.** Harmonia is a local-first single-user tool. Auth on
   localhost is security theatre. The `User` model, both `user_id` FKs, and all
   `user_id` request params come out. The server binds `127.0.0.1` by default; LAN
   exposure requires an explicit `--host` flag that logs a warning.

3. **License: MIT for the core.** Key profiles are implemented from published papers
   (Krumhansl-Schmuckler 1990, Temperley 2001, Faraldo et al. 2016), not copied from
   any AGPL source. If Essentia support is ever added it goes in a **separate**
   `harmonia-essentia` repo licensed AGPL-3.0, implementing the same protocols. The
   core repo never imports Essentia.

4. **Storage split:** scalars in the relational DB; dense arrays (beat grids, chroma
   matrices, segment boundaries, tempo curves) in Parquet sidecars keyed by content
   hash. DuckDB optionally reads the Parquet directly for the eval harness. Do not put
   800-float beat grids in JSON columns.

### Hard constraints

- **Do not add madmom.** It is pinned below Python 3.10, breaks on numpy 2.x, and its
  model files are CC BY-NC-SA 4.0 with commercial use requiring author permission.
  We are on Python 3.12 and numpy 2.4.4.
- **Do not add Essentia to the core repo.** AGPL-3.0; models are CC BY-NC-ND 4.0;
  Python bindings are not supported on Windows.
- **Do not bundle FFmpeg** in the Docker image. Require the user to install it.
- **Do not fabricate benchmark numbers.** Every figure in the README must come from a
  reproducible run of the eval harness.

---

## 2. Audit findings that drive the work

> **Provenance note.** This audit was run on the pre-fast-forward `develop` (`1c865f3`).
> `develop` has since been fast-forwarded to the tagged academic artifact `main`
> (`577e5c2`, tag `v0.1.0-academic`). Only `backend/api/analysis.py` and
> `backend/models/database.py` differed between the two commits; every other audited
> file is byte-identical. Line numbers below are updated where they shifted.

These came from a read-only audit of the live repo. Treat them as verified.

### Blockers and bugs

| # | Finding | Location |
|---|---|---|
| 1 | Key detection picks the tonic as `argmax` of mean chroma, then only decides major vs minor. Not a 24-rotation correlation. | `backend/audio/analyzer.py` |
| 2 | `librosa.load(..., sr=22050, duration=45)` with no offset analyzes the **first 45 seconds**, i.e. the intro. | `analyzer.py:12` |
| 3 | `loudness = min(1.0, rms_mean / 0.3)` likely saturates at 1.0 for most modern masters. | `analyzer.py:37` |
| 4 | `punch = (punch - 3.0) / 6.0` likely clamps to 0.0 for most tracks, collapsing danceability to `0.2 * steadiness`. | `analyzer.py:54` |
| 5 | Beat array is computed then discarded. Only scalar BPM is persisted. Blocks US04 beat overlay. | `analyzer.py` |
| 6 | **RESOLVED post-tag.** `run_analysis` no longer takes a `db` argument; it opens its own `SessionLocal()` by design. The audited signature `run_analysis(track_id, file_path, db)` (which shadowed and discarded the arg) no longer exists. | `analysis.py:20` |
| 7 | N+1: `get_recommendations` loads all `Analysis` rows across all users, then queries `Track` once per candidate. | `analysis.py:211, 215` |
| 8 | `allow_origins=["*"]` with `allow_credentials=True`. Self-contradictory; browsers reject it for credentialed requests. | `backend/main.py:14-20` |
| 9 | No Alembic. Schema created by `Base.metadata.create_all(bind=engine)` at import. | `main.py:8` |
| 10 | No `ondelete` on any FK. Cascade is hand-rolled in `delete_track` / `delete_playlist`. SQLite does not enforce FKs by default, so missed cleanup passes tests but orphans rows on Postgres. | `models/models.py` |
| 11 | `requirements.txt` pins `bcrypt`, `passlib`, `python-jose`, `ecdsa`, `rsa`. **None are imported.** Real hashing is unsalted `hashlib.sha256`. | `requirements.txt`, `api/users.py:19-20` |
| 12 | `docker-compose.yml` is tracked and **0 bytes**. | repo root |
| 13 | `frontend/.env` is tracked (holds the `onrender.com` URL) despite `.gitignore` listing `.env`. | `frontend/.env` |
| 14 | No `.env.example` anywhere. `SECRET_KEY` and `UPLOAD_FOLDER` in `.env` are dead (never read; `UPLOAD_DIR` is hardcoded to `"uploads"`). | |
| 15 | No `.github/workflows`. No CI. | |
| 16 | No git tags. Working tree dirty: `frontend/.env`, `frontend/package-lock.json` modified; `coverage.json`, `docs/`, `frontend/.env.render` untracked. | |
| 17 | No job/status table. "Async" is FastAPI `BackgroundTasks` in-process; the client polls `GET /api/analysis/{track_id}` until 404 flips to 200. | `analysis.py:10-37` |
| 18 | No content hash on `Track`. No dedup, no cache invalidation key. | `models/models.py` |

### Things that are already fine

- Zero `sqlalchemy.dialects.postgresql` imports. All generic column types.
- Zero raw SQL. Everything through the ORM.
- Camelot adjacency is already runtime Python dicts (`CAMELOT_MINOR`, `CAMELOT_MAJOR`
  at `analysis.py:121-150`; `camelot_compatible` at `analysis.py:163-192`). Nothing to
  migrate out of the DB.
- No production secrets in git history. Only a **localhost** Postgres dev password in
  `README.md` (commit `702d8bb`) and the `onrender.com` URL in `frontend/.env`.
- Auth has no middleware, no `get_current_user`, no tokens. Removing it is mechanical.
- Test suite genuinely runs the DSP on synthesized audio. Nothing is mocked.

---

## 3. Working agreement

- **Confirm the approach before implementing.** Propose the change, wait for agreement,
  then write code. Do not batch multiple phases into one commit.
- **One phase per session** unless told otherwise.
- **Tests must pass before a phase is considered done.** Report the pytest summary line.
- **Prefer paste-ready terminal commands** over describing manual file edits.
- **Honesty over polish.** Known limitations get documented in the README, not hidden.
  This rule held through the whole academic phase and continues here.
- **Do not overstate certainty.** If a claim needs verification, say so and verify it.
- **No em dashes in prose** written into the repo (README, docs, comments).
- Every phase ends with a short note in `CHANGELOG.md`.

---

## 4. Phases

### Phase 0: freeze the academic artifact

**Goal:** make the submitted work permanently verifiable before anything changes.

1. Run `git log main..develop --oneline` and report the output. **Do not tag until the
   result is reviewed**, because it is not yet settled whether the artifact to preserve
   is `main` (what Render deployed and examiners tested) or `develop` (which includes
   the cascade-delete fix made during report finalization).
2. Resolve the dirty working tree: commit or discard `frontend/package-lock.json`;
   decide on `docs/` and `frontend/.env.render`; delete `coverage.json` and gitignore it.
3. `git rm --cached frontend/.env` and add `frontend/.env.example`.
4. Add a root `.env.example` documenting every variable actually read. Remove the dead
   `SECRET_KEY` and `UPLOAD_FOLDER` entries or wire `UPLOAD_FOLDER` up properly.
5. Tag the agreed commit as `v0.1.0-academic` and cut a GitHub Release describing it as
   the state of the code at defence.

**On the README localhost password (finding 11 in the audit's own numbering):** it is a
`postgresql://user:pass@localhost/harmonia_db` dev credential, functionally worthless.
Recommendation is to fix the current README and leave history alone, since rewriting
history would invalidate the tag's relationship to the report and break Inas's clone.
Note it in `SECURITY.md` instead. Flag if you disagree.

**Done when:** a tag exists, the tree is clean, no `.env` is tracked.

---

### Phase 1: dependency and packaging hygiene

**Goal:** stop the repo from looking unserious the moment it goes public.

1. Remove `bcrypt`, `passlib`, `python-jose`, `ecdsa`, `rsa` from `requirements.txt`.
   Confirm with grep that nothing imports them first.
2. Create `pyproject.toml` with a proper `[project]` block, entry point
   (`harmonia = "harmonia.cli:main"`), and optional extras. Keep `requirements.txt`
   generated from it or drop it.
3. Delete the 0-byte `docker-compose.yml`. It gets rewritten in Phase 2 or not at all.
4. Fix CORS in `backend/main.py`: explicit origins list defaulting to
   `["http://localhost:3000", "http://127.0.0.1:3000"]`, and drop
   `allow_credentials=True` since there are no credentials once auth is gone.
5. Add `.github/workflows/ci.yml`: matrix over Python 3.11/3.12/3.13, install, run
   `pytest --cov=backend`, run `ruff check`. Note: the `e2e` optional-dependency
   extra (playwright + httpx) and its browser-driven tests stay OUT of the default
   CI job for now, because running them needs a `playwright install chromium`
   browser step. Add a separate opt-in e2e job later.
6. Add `ruff` config to `pyproject.toml`. Fix what it flags, including the unused `Text`
   import at `models/models.py:1`.

**Done when:** CI is green on `develop`, `pip install -e .` works from a clean checkout.

---

### Phase 2: de-cloud

**Goal:** `git clone && pip install -e . && harmonia serve` with no external services.

**First, introduce a `create_app()` factory** so configuration is read at call time, not
import time. Today `backend/main.py` builds the app, reads CORS origins, and runs
`Base.metadata.create_all` at import, and `backend/models/database.py` builds the engine at
import from `DATABASE_URL`. That import-time coupling is why tests must set env vars before
importing `backend.main` (the CORS/conftest `CORS_ORIGINS` workaround is the symptom) and
why a fresh clone with no `.env` cannot `import backend.main` at all. Move app construction,
engine creation, and table setup into functions invoked at startup; the steps below assume
this factory.

1. `backend/models/database.py`: default `DATABASE_URL` to `sqlite:///./harmonia.db`.
   Add `connect_args={"check_same_thread": False}` for SQLite only.
2. **Add a `PRAGMA foreign_keys=ON` event listener** on connect. Without it SQLite
   silently skips FK enforcement, which is exactly why the hand-rolled cascade deletes
   have been passing tests (audit finding 10).
3. Introduce Alembic. `alembic init`, configure it to read `DATABASE_URL`, generate one
   baseline migration matching the current schema, and remove `Base.metadata.create_all`
   from app startup. Note: the migration chain built across Phases 2 and 3 gets squashed
   into a single initial migration before the public release, so the published history
   starts from one clean baseline.
4. Add real `ondelete="CASCADE"` to every FK in a follow-up migration, then delete the
   manual child-deletion loops in `delete_track` and `delete_playlist`.
5. Serve the frontend: build React, mount the output with `StaticFiles` in `main.py`
   with an SPA catch-all so client-side routes resolve. One process, one port.
6. Rewrite `docker-compose.yml` properly, or ship a Dockerfile only. Do not bundle FFmpeg.

Local folder scanning and the `content_hash` column (formerly steps 7 and 8) have moved
to run **after Phase 3** (see "Phase 3.5: local ingestion" below), so ingestion is built
against the already auth-free models instead of being reworked twice.

**Done when:** the app runs offline on a fresh machine with no `DATABASE_URL` set.

---

### Phase 3: delete auth

**Goal:** remove the `User` model and everything that touches it.

1. Drop `User` from `models/models.py`. Drop `Track.user_id` and `Playlist.user_id`.
   Generate the Alembic migration.
2. Delete `backend/api/users.py` and unregister its router.
3. Remove the `user_id` `Form`/path params from `tracks.py:13`, `tracks.py:60`,
   `tracks.py:120`, `playlists.py:11`, `playlists.py:23`.
4. Simplify `get_recommendations` (`analysis.py:196-239`): the ownership filter
   disappears, which lets the whole thing become a single query joining `Analysis` to
   `Track` with the BPM window applied in SQL. **This kills the N+1 as a side effect.**
   Keep `camelot_compatible` filtering in Python; the wheel is a fixed 24-node graph and
   is not worth pushing into SQL.
5. Fix the tests. The blast radius looks large but is concentrated:
   - `test_unit.py`: one module-level `from backend.api.users import hash_password`
     breaks all 18. Remove the import, delete the 3 `TestPasswordHashing` tests, and the
     other 15 Camelot/DSP tests should pass untouched.
   - `test_analysis_paths.py`: rewrite `_make_user_and_track` as `_make_track`. 7 tests.
   - `test_integration.py`: 6 tests seed via `/register`. Reseed directly.
   - `test_acceptance.py`: 17 of 19 parametrized stories reference a user. US01/US02
     (register/login) get deleted outright; the rest get the user step removed.
   - `test_e2e.py`: both tests drive the guest UI. Rewrite for the no-auth entry path.
6. **Recompute coverage.** Do not reuse the 84% figure from the report; the denominator
   changed. Report the new number honestly.
7. Bind to `127.0.0.1` by default. Add `--host` to the CLI with a warning log line when
   it is not loopback.
8. Document the decision in the README as a deliberate local-first design choice, not an
   omission.

**Done when:** no reference to `User` remains, the suite passes, coverage is re-measured.

---

### Phase 3.5: local ingestion (moved out of Phase 2)

**Goal:** ingest music from a local folder, keyed by content hash. Runs after auth is gone
so it targets the final, user-free models rather than being reworked twice.

1. Replace upload-only ingestion with **local folder scanning**: a configurable music
   directory, scanned in place with `mutagen` for tags, no file copying. Keep the upload
   endpoint if it is cheap to keep, but scanning becomes the primary path.
2. Add a `content_hash` column to `Track` (blake2b over file size plus first and last
   1MB is enough and is fast). This becomes the cache and Parquet key.

**Done when:** pointing the app at a folder populates the library with hashed tracks.

---

### Phase 4: evaluation harness and baseline

**Goal:** measure the current algorithm before changing it, so the improvement claim is
falsifiable.

1. Create `eval/` with a runner that takes a dataset directory plus an annotation file
   and emits a scored report.
2. **Datasets:** GiantSteps Key (604 EDM tracks) and GiantSteps Tempo. Ship the eval
   script and the annotation files only. Users bring their own audio. Do not commit audio.
3. **Key scoring: MIREX weighting.** Correct 1.0, perfect fifth 0.5, relative major/minor
   0.3, parallel major/minor 0.2, else 0.0. Report both the weighted score and the
   raw exact-match rate.
4. **Tempo scoring:** Accuracy1 (within 4%) and Accuracy2 (within 4% allowing
   octave errors: 1/3, 1/2, 2, 3).
5. **Run it against `analyze_audio` exactly as it is today. Write the numbers down.**
   This is the baseline every later claim is measured against.
6. **Also histogram energy and danceability across the dataset.** Audit findings 3 and 4
   predict these saturate. Confirm or refute with real data and report the distributions.
   If they are near-constant, say so plainly; that is a finding, not a failure.
7. Add `eval/README.md` explaining how to reproduce, including dataset acquisition.

**Done when:** `python -m eval.run --dataset giantsteps-key` prints a scored table, and
the baseline numbers are committed to `eval/baseline.md`.

**Update (as built):** shipped as a standalone `eval/` that vendors nothing and downloads
data on demand (see `eval/README.md`). Key uses GiantSteps+ EDM Key (600), not the
original 604, so scores are not comparable to 604-based papers. Tempo could not use
GiantSteps Tempo (dead Beatport audio; only a 43-track overlap with the key audio); GTZAN
is wired in as a development regression check only, not an accuracy claim, and no GTZAN
tempo number goes in the project README. See open question 4. Multi-label key references
are scored best-of (the estimate is credited with its highest-weight acceptable match).

---

### Phase 5: job processing and feature store

**Goal:** make room for analysis that takes 10 to 25 seconds per track. This must land
**before** the DSP work or the UX gets worse, not better.

1. Add a `jobs` table: id, track_id, status (`queued`/`running`/`done`/`failed`),
   progress, error, created_at, finished_at.
2. Replace `BackgroundTasks` with a `multiprocessing` pool sized `cpu_count() - 1`.
   Not Celery, not Redis. This is a local app.
3. `run_analysis` already takes no session on this branch (audit finding 6 resolved
   post-tag). Optionally switch to an explicit session factory.
4. Add `analyzer_version` to `Analysis`. Cache key becomes
   `(track_id, content_hash, analyzer_version)`. Bumping the version invalidates and
   forces recompute, which you will need on every DSP iteration in Phase 6.
5. Parquet feature store: `features/{content_hash}.parquet` holding beat grid, chroma
   matrix, tempo curve, segment boundaries. `pyarrow` dependency.
6. Progress endpoint: SSE or polling against the `jobs` table. Replace the current
   404-until-200 polling hack.
7. Batch library scan: enqueue every unanalyzed track in the music folder.

**Done when:** a 100-track folder analyzes end to end with visible progress and survives
a server restart mid-run.

---

### Phase 6: DSP

**Goal:** the accuracy table. Change one thing at a time and re-run the harness after
each so every improvement has an attributable delta.

Refactor first: define protocols in `backend/audio/protocols.py`:

```python
class KeyDetector(Protocol):
    def detect(self, y: np.ndarray, sr: int) -> KeyResult: ...

class TempoDetector(Protocol):
    def detect(self, y: np.ndarray, sr: int) -> TempoResult: ...

class DescriptorEstimator(Protocol):
    def estimate(self, y: np.ndarray, sr: int) -> Descriptors: ...
```

**Reordered after the Phase 4 baseline.** The confusion breakdown contradicts the
original assumption that full-track audio would be the largest key-accuracy jump. Exact
key is right only 34.7% of the time; the errors split into unrelated keys ("other",
28.9%), fifths (17.5%), parallel / wrong-mode (12.9%), and relatives (6.0%). Two things
stand out. Parallel mode confusion is a large bucket, and the binary diatonic templates
for major and minor differ in one pitch class, so the mode discriminator is close to a
coin flip. And the pervasive "other" errors say tonic selection is frequently wrong too.
Audio-side improvements (full track, HPSS, CQT) will not fix either, so the key-profile
and correlation work moves first. See `eval/baseline.md`.

Then, in this order, re-running `eval/run` after each step:

1. **Weighted key profiles + 24-rotation correlation.** Replace both the `argmax` tonic
   selection and the one-pitch-class binary major/minor templates with correlation of the
   mean chroma against all 24 rotations (12 tonics x major and minor) of weighted
   profiles. Return the best match plus a confidence score plus the runner-up. Start with
   Krumhansl-Schmuckler (1990), then add Temperley (2001) and Faraldo et al. (2016) EDMA
   profiles; benchmark all three against each other and pick the winner as default,
   keeping the others selectable. These are 12-element vectors from published papers;
   implement them, cite them, stay MIT. This is aimed straight at the parallel-mode
   confusion the baseline exposed.
2. **Full track instead of 45s.** Drop `duration=45`. Analyze the whole file in
   overlapping windows and aggregate. The current code analyzes only the intro.
   Tuning correction was originally listed here as a step. It was found **already
   present**: librosa's `chroma_stft` auto-estimates and applies tuning by default
   (`tuning=None`), so it was never absent and was not an addition by us. It was
   quantified by ablation instead - disabling it (`tuning=0.0`) costs 0.007 weighted
   and 7 exact matches on GiantSteps+ (about 24% of the corpus sits >10 cents off
   A440). Removed as a step. See `eval/baseline.md`.

3. **HPSS.** Separate the harmonic component before chroma so percussion stops polluting
   pitch classes. **Tried and reverted:** like-for-like on 150 GiantSteps+ tracks it
   gained +0.0007 weighted (within noise) at 6.2x the per-track cost (8.34 s vs 1.34 s).
   A measured negative on this EDM corpus - see `eval/baseline.md`. Revisit only if a
   later change (e.g. `chroma_cqt`) changes the picture.
4. **`chroma_cqt`.** Log-spaced semitone-aligned bins. **Tried and reverted:** like-for-
   like on 150 GiantSteps+ tracks it lost 0.094 weighted (11 exact matches) at 1.3x cost,
   mostly to `other` errors. A measured negative on this EDM corpus with the EDMA profile
   (see `eval/baseline.md`). STFT was not just the RAM-cheap choice - it is more accurate
   here. Revisit only if the key profile is re-derived against CQT-style chroma.
5. **Tempo octave correction.** DJ-range prior plus onset-autocorrelation disambiguation
   for the half/double-time ambiguity. **Not pursued (unmeasurable):** the only EDM tempo
   reference we could build (GiantSteps+ Beatport metadata) failed validation - it carries
   the same half-time bias as the error under test (agrees with gold on 2/24 within 4%; 10
   of 22 disagreements are octave relations). On the 43 gold tracks the analyzer scores
   Acc1 0.419 with only 4 octave errors - too small a population, and no larger
   genre-correct reference exists. See `eval/baseline.md` and open question 6.
6. **Persist the beat grid.** **Done:** `analyze_audio` now returns the beat times
   (previously computed for danceability, then discarded) and `run_analysis` stores them in
   a generic SQLAlchemy JSON column on `analyses` (`beat_grid`, portable SQLite/Postgres),
   served via `GET /api/analysis/{id}/beats` for the US04 overlay. Stored as JSON, not
   Parquet: a beat grid is one short 1-D array per track, where Parquet buys nothing. The
   `Analysis(**result)` spread was replaced with explicit field mapping so the analyzer
   output and the schema change independently. The **Parquet feature store** from the
   original design is deferred, and would apply to chroma matrices and segment data if those
   ever land - not to the beat grid.
7. **Recalibrate energy and danceability against the measured ranges in
   `eval/baseline.md`.** **Done in part (constants recalibrated):** the existing formula's
   per-component constants were replaced with robust corpus p2/p98 min-max maps, so both
   descriptors now spread across [0, 1] (spreads roughly doubled; see `eval/baseline.md`).
   Stated in code and record as heuristics with no ground truth - success is spread, not
   accuracy. Still open: the larger composite rebuild (EBU R128 integrated loudness via
   `pyloudnorm`, spectral flux, onset rate, pulse clarity, low-band energy ratio) and
   publishing the formula in the README.
8. **Structural segmentation (mix points).** **Partly done:** intro end and outro
   start ship as `analyses.intro_end` / `outro_start` (beat-synchronous energy
   envelope; heuristics with sanity checks only, no ground truth - see
   `eval/baseline.md`). **Major-transition detection is deferred:** it cannot be
   validated on this EDM corpus without a per-track downbeat, and low-band energy
   gives no downbeat phase on four-on-the-floor material (kick on every beat), so
   the phase estimate was a coin flip. Future work is contingent on a trained
   downbeat model; madmom is ruled out on licence and Python-version grounds (see
   the section 1 constraints). Laplacian segmentation was rejected as
   section-labelling, out of scope for mix points.

**Done when:** `eval/results.md` has a per-step accuracy table from baseline to final.

---

### Phase 7: open-source packaging

1. Migrate the frontend from Create React App (`react-scripts` 5.0.1, deprecated) to
   Vite. React 19.2 and react-router-dom 7 carry over.
2. `LICENSE` (MIT).
3. `README.md`: 60-second quickstart, demo GIF, **the accuracy table**, architecture
   diagram, honest limitations section, documented descriptor formulas.
4. `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, issue and PR templates.
5. `CITATION.cff` crediting the ISEP origin and Prof. Ferreira's supervision.
6. GHCR image published from CI.
7. Dependency lockfile (`uv.lock` or `requirements.lock`).

---

## 5. Open questions

1. **Which commit is the academic artifact?** `main`, `develop` at `1c865f3`, or
   `develop` merged into `main` first. Blocks Phase 0. Needs `git log main..develop`.
2. **API compatibility with Inas Mezouri's `Harmonia-mobile`.** Every phase from 3
   onward breaks the contract her Expo client consumes. Options: freeze `/api/v1` and
   build `/api/v2`, co-evolve both repos, or accept the break. Needs a conversation with
   her, ideally before Phase 3.
3. **Keep the upload endpoint alongside folder scanning, or replace it?** Affects how
   much of `tracks.py` survives Phase 2. **Resolved (Phase 3.5): keep both.** Upload
   serves the web UI (copies into `uploads/`); the scan CLI (`backend/scan.py`) ingests a
   local library in place, deduped by content hash. They coexist.
4. **Tempo benchmark gap (OPEN).** There is no accuracy benchmark for tempo. GiantSteps
   Tempo annotations exist, but their Beatport audio is dead, and the obtainable
   GiantSteps+ key audio overlaps the tempo set by only 43 tracks (of 664) - too few to
   benchmark. GTZAN is wired into `eval/` as a development regression check only, NOT an
   accuracy claim: no GTZAN tempo number goes in the project README. Revisit if a usable
   EDM tempo set with obtainable audio turns up, or if we hand-annotate one. Flagged
   open, not closed.
5. **Steadiness is near-constant on EDM (OPEN).** The danceability beat-steadiness term
   (`1 - CV` of beat intervals) spans only 0.929-0.984 (p2..p98) across GiantSteps+ - it
   barely varies, because EDM grids are uniformly steady. Its 20% weight is therefore
   close to a constant offset on this corpus. Left unchanged in the recalibration
   (reweighting is a separate experiment). Open: drop or reweight steadiness, or swap in a
   rhythm feature that actually varies, decided on a corpus where it does. See
   `eval/baseline.md`.
6. **Tempo detection is worse than expected, and unmeasurable (OPEN).** On the 43 gold
   GiantSteps Tempo tracks (the only genre-correct EDM tempo ground truth with obtainable
   audio) the analyzer scores Accuracy1 0.419 - low for the Ellis (2007) beat tracker on
   strongly-metered dance music - and only 4 of the 25 misses are octave errors; the rest
   are outright-wrong tempos. So the tempo problem is not the half/double ambiguity the plan
   assumed. It cannot be quantified because no large genre-correct tempo reference exists:
   the GiantSteps Tempo audio is unobtainable, the GiantSteps+ Beatport metadata is
   octave-biased (fails validation - agrees with gold on only 2/24 within 4%, see
   `eval/baseline.md`), and GTZAN is genre-mismatched. This blocks any measured tempo
   improvement. Related to open question 4.
