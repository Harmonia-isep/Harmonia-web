# Changelog

Notable changes to Harmonia. The format loosely follows Keep a Changelog. Before the
public release, work is tracked by rebuild phase (see HARMONIA_REBUILD_PLAN.md). The
academic submission is preserved under the `v0.1.0-academic` tag.

## Unreleased

### Phase 7: open-source packaging (in progress)
- Migrated the frontend from Create React App to Vite. `react-scripts` 5.0.1 could not
  build against the React 19 already in `package.json`, and it is unmaintained. Build
  output stays in `build/`, so the FastAPI `DEFAULT_FRONTEND_DIR` and the Playwright
  fixture are unchanged; the 11 JSX-bearing sources became `.jsx`, and the client env var
  moved from `REACT_APP_API_URL` to `VITE_API_URL`.
- Node 22. `react-router-dom` had drifted to 7.18.2, which requires Node >=20, while the
  development runtime was 18.19.1 (end of life since April 2025). Rather than pin the
  router back onto an unsupported runtime, declared `"engines": { "node": ">=20" }` in
  `frontend/package.json` and moved development to Node 22 (Active LTS). Pinning down
  would also have dead-ended the vite upgrade, which needs Node 20 as well.
- Added a browser-driven `e2e` CI job (Node pinned to 22, Playwright chromium), separate
  from the default job, which has no browser. It wipes `node_modules` and `build` first,
  so the e2e can never pass against a stale bundle.
- Fixed two bugs in the e2e build fixture. It set the CRA-era `REACT_APP_API_URL`, which
  Vite ignores, so the bundle under test silently fell back to `http://localhost:8000`
  instead of the test server; it now sets `VITE_API_URL`. And it returned early whenever
  `build/` existed, so a source edit could pass e2e without ever being compiled. It now
  rebuilds when any build input is newer than the output, and records the API base it
  built with, since that is a build input an mtime check cannot see.
- Vite 5 to 8, with `@vitejs/plugin-react` 4 to 6. Vite 8 replaces Rollup and esbuild
  with the Rust-based Rolldown and Oxc, and uses Lightning CSS for CSS minification. No
  `vite.config.js` change was needed: the renamed options (`build.rollupOptions` to
  `build.rolldownOptions`, `esbuild` to `oxc`, `optimizeDeps.esbuildOptions` to
  `optimizeDeps.rolldownOptions`) are all ones this project never set, and `build.outDir`
  is unaffected. The production build went from 4.30 s to 854 ms, the bundle shrank
  slightly (JS 285.5 to 280.4 kB, CSS 33.4 to 33.0 kB), and the output layout is
  unchanged. Dependency count fell from 94 to 54, which cleared both advisories: `npm
  audit` now reports 0 vulnerabilities, where before it flagged a dev-server esbuild
  issue and three vite ones.
- Tightened the Node floor from `>=20` to `^20.19.0 || >=22.12.0`, matching what vite 8
  actually requires. The looser range admitted versions (20.0 to 20.18, 21.x, 22.0 to
  22.11) on which vite 8 refuses to run.
- Note for anyone tracking browser support: vite 8 raises the default baseline to Chrome
  111, Firefox 114, and Safari 16.4 (from 107, 104, and 16.0).
- Bumped `actions/checkout` to v5, `actions/setup-python` to v6, and `actions/setup-node`
  to v5, clearing the Node 20 runtime deprecation annotation that every job carried. Input
  names were checked against each action's `action.yml` at the new tag before assuming a
  drop-in: `python-version` and `node-version` are unchanged, and checkout takes no inputs
  here.
- De-authed the frontend, completing Phase 3 on the client side. The login gate is
  replaced by a front door: `/` is a landing page describing the tool and `/library` is
  the app. A local-first single-user tool has nothing to sign up for, but opening
  straight into an empty library with no explanation is a worse first run than a page
  that says what the tool is. Deleted `Auth.jsx` and `Auth.css`. The `user` prop was
  removed outright rather than replaced, because all four components that took it used
  it for exactly one thing, `user.user_id`, which no endpoint accepts any more (seven
  call sites, plus the `useEffect` dependency arrays that listed `user`).
- `api.js`: deleted `createGuestUser`, `registerUser` and `loginUser`; collapsed
  `getUserTracks` and `searchTracks` into one `getTracks(params)`, since both resolved
  to the same `GET /api/tracks/` once the ownership filter went; repointed
  `getUserPlaylists` to `getPlaylists` (`GET /api/playlists/`) and `exportCSV` to
  `GET /api/tracks/export`; dropped the `user_id` argument from `createPlaylist` and the
  `user_id` form field from the upload.
- Routing is three routes matched on `window.location.pathname` with `pushState` and a
  `popstate` listener, not react-router, which has been a dependency since the academic
  phase but has never been imported. Adopting it is a separate change if the route count
  ever justifies it.
- Verified the SPA catch-all now that a real client route exercises it, which none did
  when it landed in Phase 2 chunk 4: `/`, `/library`, `/library/` and `/shared/<token>`
  each return 200 with `index.html` byte for byte, `/favicon.ico` still serves the real
  file, and `/api/...`, `/docs` and `/openapi.json` are not shadowed.
- e2e rewritten for the no-auth entry path: one test that the landing page renders and
  its Open Library action routes to `/library`, with the library nav replacing the hero,
  and one that a direct `/library` load is served by the catch-all rather than 404ing.
  Deliberately not extended to ingest, analyze and recommend; that smoke test is its own
  piece of work.
- One unconditional `localStorage.removeItem('harmonia_user')` on mount clears the
  account object left behind by pre-1.0 builds. Nothing reads it any more, so this is
  hygiene rather than a fix, and it can be dropped after the first public release.

### Phase 3.5: folder scanning (local ingestion) — done after Phase 6
- Added `backend/scan.py`, a CLI (`python -m backend.scan PATH`) that registers local
  audio files into the library **in place** (no copy), unlike the web upload. Dedup and
  relink are by **content hash** (blake2b over file size + first/last 1 MB, not a full
  read) with `file_path` as a secondary key, so a moved file relinks instead of
  duplicating and the library survives reorganisation; the hash is also the cache key any
  future re-analysis will use. Added `Track.content_hash` (indexed, nullable; migration
  `42cd00ca544f`).
- Registration is the default; `--analyze` opts into the CPU-bound DSP pass (printing a
  track count and rough time estimate first), `--reanalyze` forces it on already-analyzed
  tracks. Per-file error tolerance (one bad file never aborts the scan), an extension
  whitelist, filename fallback for a missing title, and per-track commit (interruptible,
  idempotent on re-scan). The upload endpoint is kept alongside scanning (resolves the
  plan's open question 3).

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
- Tempo octave correction: investigated and NOT pursued (unmeasurable). An EDM tempo
  reference built from the GiantSteps+ Beatport metadata failed validation against the
  gold GiantSteps Tempo - it agrees on only 2/24 within 4%, and 10 of 22 disagreements
  are octave relations (Beatport lists high-BPM genres at half tempo, the same bias as
  the error under test), so it cannot adjudicate an octave correction. On the 43 gold
  tracks the analyzer scores Acc1 0.419 with only 4 octave errors, so the addressable
  gain is ~+0.09 on 43 tracks, indistinguishable from noise, and no larger genre-correct
  reference exists. Recorded with the tempo baseline and a new open question: tempo
  detection is worse than expected and its errors are mostly non-octave. No analyzer
  change. See eval/baseline.md.
- Persist beat grid: `analyze_audio` now returns the beat times (previously computed for
  danceability and discarded) and `run_analysis` stores them in a generic JSON column
  (`analyses.beat_grid`, portable across SQLite and Postgres), served via
  `GET /api/analysis/{id}/beats` for the beat overlay (US04). Migration 5afbc2f7ed44 adds
  the nullable column. Replaced the `Analysis(**result)` spread with explicit field mapping
  so the analyzer output and the schema change independently and a new analyzer key can no
  longer crash the write with an opaque error. The Parquet feature store is deferred (for
  chroma / segment data, not the beat grid).
- Structural segmentation (mix points): ship `intro_end` and `outro_start` float columns on
  `analyses`, detected from a beat-synchronous energy envelope. Heuristics with sanity
  checks only, no ground truth (same class as energy/danceability, not the benchmarked
  key): on 30 tracks intro_end was plausible on 27/30, outro_start on 29/30. Migration
  0cb1637e4e45 adds the columns. Major-transition detection was investigated (Foote novelty
  over beat-sync MFCC; 0.27s, +20% cost; stable) but DEFERRED: it cannot be validated
  without a downbeat phase anchor, and low-band energy carries no downbeat phase on
  four-on-the-floor EDM (kick every beat), so the phase estimate was a coin flip (no track
  above 0.10 margin). A trained downbeat model would be required; madmom is ruled out. Full
  investigation in eval/baseline.md.

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
