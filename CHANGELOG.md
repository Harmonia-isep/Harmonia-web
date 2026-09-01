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
- Fixed `createPlaylist` interpolating the playlist name into the query string
  unencoded, so a name containing `&`, `?` or `#` was truncated or split into stray
  parameters. Pre-existing since the academic phase.
- Removed `react-router-dom`, unused since the academic phase: nothing has ever imported
  it, and the routing added with the de-auth uses `pushState` directly. Confirmed inert
  by rebuilding, the bundle hashes are identical, so it was installed but never shipped.
  Same class of problem as the five unused crypto pins dropped in Phase 1. This does not
  relax the Node floor: `^20.19.0 || >=22.12.0` is what vite 8 itself requires, so the
  constraint react-router first surfaced now has an independent source. Frontend
  dependency count is 50, down from 94 before the vite upgrade.
- Wired up the upload directory, closing audit finding 14 and Phase 0 step 4. It was two
  hardcoded relative constants (`UPLOAD_DIR = "uploads"` in `api/tracks.py` and
  `ARTWORK_DIR = "uploads/artwork"` in `audio/artwork.py`), so every test that touched the
  upload endpoint wrote real files into the developer's `uploads/` folder. Added
  `backend/storage.py`, which resolves the directory at call time (explicit argument, then
  `HARMONIA_UPLOAD_DIR`, then `uploads`), the same pattern `DATABASE_URL` already uses;
  `create_app(upload_dir=...)` creates it and publishes it on `app.state`, and artwork
  follows it into an `artwork/` subfolder. Documented in `.env.example`. The test suite now
  uploads into a temp directory that is removed at session teardown, verified by counting
  `uploads/` before and after a full run.
- Added the smoke e2e, the release bar from the Phase 7 definition of done: two tracks
  ingested through the real upload UI, analyzed by the real DSP, and one recommending the
  other on screen. It runs in the same CI job as the other e2e tests, because a release
  bar that does not gate is decoration. The recommendation algorithm already had API-level
  coverage with seeded rows, so what this adds is proof that a person can actually get
  there.
- The two tones were chosen by measurement rather than assumption. Analyzing C4 to C5 with
  conftest's `make_tone` recipe showed only 3 of 28 pairs are both inside the +/-5 BPM
  window and Camelot compatible; E4 and A4 were picked because their BPM difference is 0
  and 9A/8A are adjacent on the wheel, so a future librosa tempo shift of up to 5 BPM in
  either direction is absorbed. The full table is in a comment at `SMOKE_TONES`, including
  the warning that the tempo values are arbitrary (pure tones have no percussive content,
  so the beat tracker reads noise) and that this is not an analyzer bug to fix.
- The smoke test builds its own app, database and upload directory instead of sharing the
  session-scoped ones, so ingesting real tracks cannot leak rows into the other e2e
  assertions. Cross-test pollution is solved by isolation, not by test ordering.
- The e2e bundle is now built same-origin (`VITE_API_URL=""`) instead of baking in an
  absolute host and port, so one build serves both e2e servers. This needed `api.js` to
  read the variable with `??` rather than `||`, since an explicitly empty value means
  same-origin and is meaningful, where `||` treated it as missing. An unset variable still
  falls back to the split-origin dev backend.
- Cloud decommission complete. The Render service and the Neon database were deleted on
  2026-08-29 (the Render URL now 404s at the edge), `develop` was fast-forwarded into
  `main` so the default branch a stranger clones is the working code, and the academic
  artifact is frozen three ways: the `v0.1.0-academic` tag, a new `academic` branch, and
  commit `577e5c2`. Two stale academic-phase branches were deleted after confirming both
  were fully contained in `main`. Harmonia now has no external service dependency at all,
  which closes the original Phase 2 goal.
- Removed two Render-era leftovers. `test_db.py` was a 13-line root script that connected
  to Postgres and printed "Connected to Neon successfully"; it held no credentials but was
  dead, and its name matched pytest's `test_*.py` pattern closely enough to be collected
  by `pytest .`. The root `requirements.txt` was never regenerated after `pyproject.toml`
  landed and had drifted badly: it still carried `pyasn1` and `six` from the crypto pins
  removed in Phase 1, and was missing `alembic` entirely, so installing from it produced
  an environment that could not migrate. `pyproject.toml` plus `requirements.lock` cover
  both roles, and CI already installed from the lock. `eval/requirements.txt` is a
  separate, still-live file and was left alone.
- Fixed the split-origin dev flow, broken since the Vite migration. The backend's
  `DEFAULT_CORS_ORIGINS` allows `localhost:3000`, inherited from Create React App, but
  Vite's dev server defaults to 5173 and `vite.config.js` set no port, so the documented
  two-terminal dev setup was CORS-blocked out of the box. Nothing caught it because the
  e2e suite uses the single-process same-origin path. Pinned the dev server to 3000 with
  `strictPort: true`, so a busy port fails loudly instead of sliding to 3001 and being
  blocked again for a non-obvious reason. Verified both directions: a preflight from
  `localhost:5173` gets no `access-control-allow-origin` header (the browser blocks it)
  while `localhost:3000` does, and a real browser run of the whole flow (Vite dev on 3000,
  API on 8000) uploaded and analyzed a track over four cross-origin calls with no CORS
  errors and no failed requests.
- Rewrote `README.md` (Phase 7 step 3). The previous one described a different project:
  it advertised PostgreSQL as a prerequisite, `chroma_cqt` for key detection (the option
  we measured as worse and reverted), a Create React App dev server with `npm start`, a
  `users.py` and `Auth.js` that no longer exist, and setup commands that could not work
  because a fresh clone landed on the academic branch and had no `pyproject.toml`. It also
  misspelled a collaborator's name in two places.
- The new one is organised around the honesty structure the project has followed
  throughout: accuracy claims are split into three explicitly labelled tiers, benchmarked
  (key, 0.713 weighted / 63.5% exact on GiantSteps+, 567 of 600 scored), heuristic with no
  ground truth (energy, danceability, mix points, with the formulas published), and not
  measured or deferred (tempo, transition detection, beat overlay). The measured negative
  results (HPSS, `chroma_cqt`, tempo octave correction) are stated in the README rather
  than buried, since a harness that reports losses is what makes the wins credible.
- Added a "what this is not" section, because a single-user unauthenticated tool needs to
  say so before someone deploys it, and a runnable `eval/` section with the real costs of
  reproducing the table (817 MB download, about 1.7 GB on disk, roughly 20 minutes for a
  full 567-track run, measured at 1.85 s/track).
- Corrected a citation error, found by review of the README. The plan credited the key
  profiles to "Krumhansl-Schmuckler 1990", which conflates two things: Krumhansl-Schmuckler
  is the name of the key-finding *algorithm*, while the profile vectors are Krumhansl and
  Kessler (1982), tabulated in Krumhansl (1990). The code was already right:
  `key_profiles.py` cites it correctly and its vectors are the canonical KK values, and
  `eval/baseline.md` says "Krumhansl-Kessler" with no year error. Only
  `HARMONIA_REBUILD_PLAN.md` was wrong, in two places, and the README now states the
  distinction explicitly. Worth fixing precisely because that paragraph is the one making
  the clean-room implementation claim that keeps the project MIT licensed.
- Dropped the hardcoded test count from the README's layout block; it went stale every
  phase.
- Added the community files (Phase 7 step 4 and 5): `CONTRIBUTING.md`,
  `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), `SECURITY.md`, `CITATION.cff`, GitHub
  issue forms and a pull request template. `SECURITY.md` states plainly that missing
  authentication is documented design rather than a vulnerability, and scopes what is and
  is not a real report. `CONTRIBUTING.md` leads with the rule that carries this project:
  do not claim what you have not measured, run `eval/` for DSP changes, and expect
  negative results to be kept rather than discarded. `CITATION.cff` credits the ISEP
  origin and Prof. Ferreira's supervision, and cites the three key-profile papers.
- Added `run.sh` and `run.bat`, launchers for people who do not want a terminal session.
  Each creates the virtual environment, installs the dependencies, applies migrations,
  builds the interface if it is missing, starts the server and opens a browser. They are
  idempotent by design: the dependency install is keyed on a hash of `pyproject.toml`, the
  frontend build is skipped when `frontend/build/index.html` exists, and only the (fast,
  idempotent) migration step always runs. (This entry originally reported **96 s cold, 3 s
  warm**, measured on a fresh clone. Those figures are withdrawn: see the correction in the
  `run.bat` rewrite below.) Missing or too-old Python and Node produce a message naming what
  to install rather than a stack trace; both paths were exercised. `.gitattributes` now
  forces CRLF
  on `*.bat`, since the repo default of `eol=lf` would have broken batch parsing on the
  one platform that file exists for.
- Restructured the README's entry points into three doors, easiest first: the launcher
  script, Docker, then from source for development. The Docker example is pinned to a
  real published tag, because `:latest` does not exist until the first release is tagged.
- Corrected the ffmpeg scoping in the README: `.opus` does NOT need it. libsndfile 1.2.2
  supports Ogg Opus natively; the error came from reading `available_formats()`, which
  lists OGG but not OPUS because Opus is a subtype there rather than a format. Rechecked
  by generating a real file in each whitelisted format and decoding it: ffmpeg is needed
  for `.m4a` and `.aac` only, two of the seven formats, not three.
- Added a Dockerfile and a GHCR publish workflow (Phase 7 step 6). Multi-stage, so the
  final image carries the built frontend but no Node; Debian slim rather than Alpine
  because the numpy/scipy/numba stack ships glibc-only manylinux wheels and musl would
  mean compiling LLVM. ffmpeg is installed, so the image handles every format the
  scanner accepts. The database, uploads and artwork share one `/data` volume and
  survive `docker rm`; migrations run at container start from an entrypoint that then
  `exec`s uvicorn so signals reach it. Runs as a non-root uid 1000. The README documents
  `-p 127.0.0.1:8000:8000` as the form to copy, not as an alternative, because the plain
  `-p 8000:8000` would put an unauthenticated app on every interface. Published on
  version tags plus `sha-<short>` only, with no moving `main` tag; pull requests build
  and smoke-test without publishing. amd64 only; arm64 is a post-release item.
- Fixed a race in the smoke e2e, caught when it failed once in a full-suite run and
  then passed three times in isolation. It was a defect in the test, not a flake to be
  waited out and not the Phase 5 polling problem: the recommendations panel is gated on
  `analysis &&`, and `selectTrack` sets the analysis BEFORE awaiting
  `getRecommendations`, so `.recs-empty` is on screen transiently while that request is
  in flight. The test read that transient state as the answer. It now waits for a real
  `.rec-item` row and only interprets the empty state after that wait expires, which
  also preserves the diagnostic message for a genuinely empty result. Five consecutive
  full-suite runs pass.
- Rewrote `run.bat` after its first real Windows run, which failed. It was shipped
  unexecuted and had three faults, and they turned out to be one cascade rather than
  three independent bugs. A `for /f` whose command begins with a quote is mis-parsed by
  cmd, so the `pyproject.toml` hash step died with `'.venv\Scripts\python.exe" -c
  "import' is not recognized`. Nothing checked it, and the failure then disguised itself
  as success: the hash variable was left empty, the stored hash was also empty, and
  `if "%SUM%"=="%OLDSUM%"` compared `""` with `""` and printed `ok dependencies already
  installed`. So no dependencies were installed, and the migration step then reported
  `'alembic' is a package and cannot be directly executed`, which is what `python -m
  alembic` says when alembic is absent and only this repository's own `alembic\`
  directory is left to match. A check that fails and reports success is worse than one
  that crashes, so the script was rewritten rather than patched: no `for /f` anywhere,
  output captured through a file, version gates read from exit codes rather than
  captured text, a linear `goto` flow so plain `%ERRORLEVEL%` is always the code of the
  command just run, and an errorlevel check after every external command. Every failure
  path now ends in `pause`, since the documented way to start Harmonia is to
  double-click the file and a window that closes on its own tells you nothing.
- Fixed three further faults in `run.bat` found while auditing for that pattern. The
  browser opened immediately instead of when the server was ready: `timeout /t 4` cannot
  work under `start /b`, which gives it no console to read from, and on any machine with
  Git for Windows on PATH the name resolves to GNU `timeout` instead. It now polls the
  port and opens the browser when something answers, matching `run.sh`. The final
  `uvicorn` line had no errorlevel check and no `pause`, so a busy port closed the window
  with nothing readable; it now names the port and how to change it. And interpreter
  discovery trusted `where py`, which succeeds against the Microsoft Store stub that is
  not Python, so every candidate now has to run before it is accepted.
- Switched both launchers from `python -m alembic` to the venv's `alembic` console
  script, and `python -m uvicorn` to `uvicorn`. To be accurate about why: `-m` was not
  broken. An installed regular package wins over a same-named directory in the working
  directory, because a directory without `__init__.py` is only a namespace portion and
  the path scan continues past it, so `python -m alembic` resolves correctly from the
  repository root whenever alembic is actually installed. The console script is used
  because `-m` reports a *missing* alembic as a message about this repository's
  `alembic/` directory, which sends you looking at the wrong thing. It is a legibility
  fix, not a correctness fix.
- Applied the same audit to `run.sh`, which was already sound under `set -e` but failed
  bare in places. Explicit messages now cover the pip upgrade, the `pyproject.toml` hash
  and an empty hash result; the venv is checked for an interpreter rather than trusted to
  have made one; `npm` is checked separately from `node`, and the Node version gate reads
  an exit code instead of comparing captured text, so a crashed node can no longer be
  reported as an old node.
- Fixed `run.sh` being committed without its executable bit, which made the documented
  first command fail on every fresh clone with `bash: ./run.sh: Permission denied`. It
  had been mode `100644` since the launchers landed. The working copy here sits on a
  filesystem where `core.filemode` is `false`, so a local `chmod +x` never reached the
  index and the wrong mode was invisible from inside the working tree; `git update-index
  --chmod=+x` sets it. Only cloning into a new directory and running `./run.sh` the way
  the README says surfaces this, which is how it was found. `docker-entrypoint.sh` is
  also `100644` but is unaffected, because the Dockerfile chmods it at build time.
- Withdrew the "96 s cold, 3 s warm" figures from the launcher entry above. They cannot be
  relied on: on a genuine fresh clone `./run.sh` could not have run at all, because of the
  mode bit fixed in the entry above, so whatever produced those numbers was not the
  documented invocation on a clean clone. A cold and a warm run were re-done from a fresh
  clone after the fix and both work, but the timings were not measured cleanly and no
  replacement figures are given here rather than invent them. If a number is wanted, it
  needs a deliberate measurement on a stated machine.
- README: gave the Windows launcher in both shell forms. PowerShell is the default
  terminal on current Windows and will not run a program from the current directory, so
  the documented `run.bat` fails there with "not recognized" and needs `.\run.bat`. Both
  are now shown, labelled by shell, with double-clicking still noted.
- CLAUDE.md: added a rule to merge fixes forward to `main` in the same session. `main` is
  the default branch and the one the README tells people to clone, so a fix that stops at
  `develop` is not shipped. The rule exists because the `run.bat` rewrite sat on `develop`
  while `main` kept serving the broken launcher to anyone cloning.
- README: noted that OneDrive, Dropbox and similar syncing folders cause file-locking
  failures partway through the first run, because a virtual environment is thousands of
  small files being written while the sync client tries to upload them. Added the related
  Windows path-length trap in the same place, after hitting it for real: with long paths
  disabled, which is the default, a 260 character cap applies, and installing into a
  folder already deep in a long path fails partway with `Could not install packages due
  to an OSError` naming a deeply nested file under `.venv\Lib\site-packages`. The
  rewritten `run.bat` handled that correctly, stopping at the pip step with its message
  rather than continuing.

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
