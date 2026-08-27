# Changelog

Notable changes to Harmonia. The format loosely follows Keep a Changelog. Before the
public release, work is tracked by rebuild phase (see HARMONIA_REBUILD_PLAN.md). The
academic submission is preserved under the `v0.1.0-academic` tag.

## Unreleased

### Phase 6: DSP (in progress)
- Step 1: replaced the analyzer's argmax-tonic plus one-pitch-class binary
  major/minor key templates with Pearson correlation of the mean chroma against
  all 24 rotations (12 tonics times major/minor) of a selectable published key
  profile. Added `backend/audio/key_profiles.py` with the Krumhansl-Kessler,
  Temperley, and Faraldo EDMA profiles, each cited to its source; `estimate_key`
  returns the winner, a confidence, and the runner-up. On GiantSteps+ (567
  scored) the weighted MIREX score rose from 0.478 to 0.687 and exact-match from
  34.7% to 60.5% with EDMA, now the default; KS and Temperley stay selectable
  via `--key-profile` / `HARMONIA_KEY_PROFILE`. EDMA is corpus-matched (EDM
  profile on an EDM corpus); see eval/baseline.md. Nothing else in the analyzer
  changed.
- Step 2: dropped the analyzer's 45-second load cap (`duration=45`), so the full
  track is analyzed instead of only the intro. On GiantSteps+ (567 scored, EDMA
  profile) weighted rose 0.687 to 0.713 and exact-match 60.5% to 63.5%, mostly
  from better tonic selection (`other` errors 102 to 89), at about 2.5x the
  per-track cost. Nothing else in the analyzer changed.
- Tuning correction (ablation, not a feature): the planned tuning-correction step
  was found already present - librosa's `chroma_stft` auto-estimates and applies
  tuning by default (`tuning=None`), so it was never our addition. An ablation with
  tuning disabled (`tuning=0.0`) cost 0.007 weighted and 7 exact matches on
  GiantSteps+ (about 24% of the corpus sits >10 cents off A440); reverted (we do
  not ship tuning disabled) and left a comment at the call site. Removed from the
  Phase 6 step list. See eval/baseline.md.
- HPSS (measured negative result, reverted): tried computing chroma on the
  harmonic component (`librosa.effects.hpss`). Compared like-for-like on the same
  150 tracks it gained +0.0007 weighted / -1 exact match (within noise) at 6.2x
  the per-track cost (8.34 s vs 1.34 s), so it was reverted per the decision rule
  fixed before the run. A useful negative: 6.2x cost, no gain on this EDM corpus.
  See eval/baseline.md.
- chroma_cqt (measured negative result, reverted): tried swapping `chroma_stft`
  for `chroma_cqt` (log-spaced, semitone-aligned bins). Diffed the defaults first
  (both auto-tune when `tuning=None`; `norm`/`hop_length`/`n_chroma` identical -
  a fair comparison). Like-for-like on the same 150 tracks it lost 0.094 weighted
  / 11 exact matches, mostly to `other` errors, at 1.3x cost, so it was reverted
  per the pre-set rule. STFT is more accurate here, not merely cheaper (correcting
  the old code comment). See eval/baseline.md.
- Energy and danceability recalibration: replaced the ad-hoc scaling constants
  (loudness `rms/0.3`, brightness `centroid/4000`, punch `(ratio-3)/6`) with robust
  min-max maps from each intermediate's 2nd..98th percentile measured over
  GiantSteps+, so both descriptors spread across their full [0, 1] range instead of
  bunching (energy std 0.123 -> 0.183, danceability 0.115 -> 0.207; both means moved
  to ~0.48). These are heuristics with NO ground truth (unlike key), so success is
  distributional spread, not accuracy, and the constants are EDM-derived and may not
  transfer. Beat steadiness barely varies on EDM (0.929-0.984), making its
  danceability weight near a constant offset here (left unchanged; flagged as an open
  question). See eval/baseline.md.

### Phase 4: evaluation harness and baseline
- Added `eval/`, a standalone harness that measures `backend/audio/analyzer.py`
  as-is (imports and calls `analyze_audio`; the analyzer is not modified). Scores
  key with the MIREX weighting (correct 1.0, fifth 0.5, relative 0.3, parallel
  0.2, else 0.0), reporting the weighted score, the raw exact-match rate, and a
  fifth/relative/parallel/other confusion breakdown. The directional fifth (+7
  only) matches `mir_eval.key.weighted_score`, cross-checked over all 576 key
  pairs in the test suite.
- Scores tempo with Accuracy1 (within 4%) and Accuracy2 (plus 1/3, 1/2, 2, 3
  metrical factors), reporting how many Accuracy2 hits were octave errors.
- Histograms energy and danceability, and audits two suspected analyzer
  pathologies by recomputing its internal `loudness` and `punch` terms from the
  same audio: how often `min(1.0, rms/0.3)` saturates at 1.0 and
  `clamp((ratio-3)/6)` clamps to 0.0.
- Datasets: GiantSteps+ EDM Key (600 tracks, Zenodo 1095691) for key; GTZAN
  (Hugging Face mirror + TempoBeatDownbeat tempo annotations) for tempo. The key
  set is the re-annotated 600, not the original 604, so numbers are not directly
  comparable to papers on the 604. GTZAN replaces GiantSteps Tempo because the
  GiantSteps key and tempo sets overlap by only 43 Beatport IDs (of 664),
  too few to reuse the key audio for a tempo baseline.
- Vendors nothing: `fetch_datasets.py` downloads everything at runtime into
  `eval/datasets/` (gitignored); no audio or annotation is committed. `eval/NOTICE`
  credits both datasets with licenses (GiantSteps+ is CC BY-SA 4.0; the GTZAN
  audio and tempo annotations have no stated license and are fetched, not
  redistributed). `eval/README.md` documents acquisition, scoring, and the
  dataset-swap caveats.

### Phase 3: delete auth
- Removed authentication entirely (local-first, single-user). Dropped the `User` model and
  the `user_id` foreign keys from `Track` and `Playlist` (one migration), deleted
  `backend/api/users.py` and its router, and removed the `user_id` form/path params from
  the tracks and playlists endpoints.
- Rewrote `get_recommendations` as a single `Analysis`-to-`Track` join with the BPM window
  applied in SQL (Camelot compatibility stays in Python), killing the N+1: the endpoint's
  query count dropped from O(N) to 2 regardless of library size.
- The server binds `127.0.0.1` by default; the README documents the no-auth decision.

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
