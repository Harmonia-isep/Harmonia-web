# Harmonia

Local-first music analysis and DJ assistance. Point it at your library and it
computes BPM, musical key, energy and danceability for every track, then
suggests harmonically compatible tracks to mix using the Camelot wheel.

Everything runs on your machine. No account, no cloud service, no upload to
anyone else.

[![CI](https://github.com/Harmonia-isep/Harmonia-web/actions/workflows/ci.yml/badge.svg)](https://github.com/Harmonia-isep/Harmonia-web/actions/workflows/ci.yml)

## What this is not

Harmonia is single-user, local, and **deliberately unauthenticated**. There is no
login, no user accounts, and no per-user data separation, because on `127.0.0.1`
an auth layer would be security theatre. The server binds loopback by default.

That makes it the wrong shape for a hosted service. **Do not expose it to a
network or the internet as-is**: anyone who can reach the port has full control
of the library, including deleting tracks. If you want it reachable from another
device, put it behind a reverse proxy that provides authentication, and treat
that proxy as the security boundary.

It is also not a real-time tool. Analysis is a batch job of roughly two seconds
per track, not something that runs live in a DJ set.

## Getting started

Three ways in, easiest first. All of them end at <http://127.0.0.1:8000>.

`ffmpeg` is optional in every case: it is needed only for `.m4a` and `.aac`,
because libsndfile handles `.mp3`, `.wav`, `.flac`, `.ogg` and `.opus` natively.

### 1. Just want to use it

Download the repository ([zip](https://github.com/Harmonia-isep/Harmonia-web/archive/refs/heads/main.zip)
or `git clone`), then run the launcher for your system:

```bash
./run.sh          # macOS, Linux
```

```bat
run.bat           :: Windows, Command Prompt
```

```powershell
.\run.bat         # Windows, PowerShell
```

On Windows you can also just double-click `run.bat` in Explorer. If you are
typing it, note that PowerShell is the default terminal on current Windows and
it will not run a program from the current directory without the leading `.\`,
so plain `run.bat` there fails with "not recognized".

It creates a virtual environment, installs the dependencies, sets up the
database, builds the interface, starts the server and opens your browser. The
first run takes a few minutes, mostly installing scientific Python packages.
**Every run after that starts in a couple of seconds**, because it skips
whatever is already done.

You need **Python 3.11+** installed. Node.js 20.19+ or 22.12+ is needed only for
the one-time interface build; the script tells you if either is missing, and
what to install.

> **Do not put the project in a syncing folder** (OneDrive, Dropbox, Google
> Drive, iCloud). A virtual environment is thousands of small files, and the
> sync client will hold one open at the wrong moment, failing the first run
> partway through with a permission error. Anywhere local is fine. On Windows
> see [Windows notes](#windows-notes) for this and three other papercuts.

### 2. Have Docker

```bash
docker run -d --name harmonia \
  -p 127.0.0.1:8000:8000 \
  -v "$HOME/Music:/music:ro" \
  -v harmonia-data:/data \
  ghcr.io/harmonia-isep/harmonia-web:latest
```

`:latest` tracks the newest release. Pin it if you would rather not move:
`:1.0.0` is exactly this release, and `:1.0` follows patch releases only. Every
commit on `main` is also published as `sha-<short>`, which is what to quote in a
bug report.

Then scan the library you mounted:

```bash
docker exec harmonia python -m backend.scan /music --analyze
```

Three things about that command are deliberate:

- **`-p 127.0.0.1:8000:8000`, not `-p 8000:8000`.** The plain form publishes on
  every interface, which would put an unauthenticated app on your whole network.
  Harmonia has no login by design (see [What this is not](#what-this-is-not)), so
  the binding is the only thing keeping it local. Change this only if you have
  read [`SECURITY.md`](SECURITY.md) and put a proxy in front.
- **Your music mounts read-only** (`:ro`). Scanning registers files in place and
  never writes to them, so the container has no reason to hold write access to
  your library.
- **`/data` is a named volume.** The SQLite database, uploads and extracted
  artwork all live there, so they survive `docker rm` and upgrades. Migrations
  run automatically at container start.

The image includes ffmpeg, so it handles every format the scanner accepts. It is
built for `linux/amd64`; arm64 is not published yet.

### 3. Working on it

```bash
git clone https://github.com/Harmonia-isep/Harmonia-web.git
cd Harmonia-web

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e .
alembic upgrade head

(cd frontend && npm install && npm run build)

python -m uvicorn --factory backend.main:create_app --host 127.0.0.1 --port 8000
```

One process serves both the interface and the API. The database is a local
SQLite file (`harmonia.db`) created by the migration step. Nothing else is
required: no `.env`, no Postgres, no external service. Set `DATABASE_URL` if you
would rather use Postgres.

See [Development](#development) for the test suite and the two-terminal setup
with hot reload.

### Windows notes

None of these are Harmonia bugs. All of them have cost someone real time.

- **PowerShell needs `.\run.bat`, not `run.bat`.** PowerShell does not run a
  program from the current directory, so the bare name fails with "not
  recognized". Command Prompt accepts `run.bat`, and double-clicking the file in
  Explorer works either way.
- **Python 3.10 is too old.** Harmonia needs 3.11 or newer. The launcher checks
  the version and stops with a message saying so, rather than failing later in a
  confusing way. If you see it, install a newer Python from
  [python.org](https://www.python.org/downloads/) and tick "Add python.exe to
  PATH" during setup.
- **Clone somewhere short, such as `C:\dev\Harmonia-web`.** Unless long paths are
  enabled, Windows caps a full path at 260 characters, and some of the files
  installed into `.venv` are deeply nested. Starting from an already deep folder
  makes the install fail partway with `Could not install packages due to an
  OSError` naming a file under `.venv\Lib\site-packages`.
- **Not inside OneDrive.** Syncing a virtual environment causes file-locking
  failures partway through the first run, and OneDrive paths are usually long
  enough to hit the previous point as well. If you have already hit either, move
  the folder, delete `.venv`, and run the launcher again.

## Accuracy: what is measured, and what is not

Harmonia reports several numbers per track. They are **not equally trustworthy**,
so they are separated here by how well they are actually evidenced. Read the tier
before you trust the number.

### Tier 1: benchmarked against public ground truth

**Key detection only.** Measured against GiantSteps+ EDM Key using the MIREX
weighting (exact 1.0, perfect fifth 0.5, relative 0.3, parallel 0.2, else 0.0).

| | Before | Shipped |
| --- | --- | --- |
| MIREX weighted score | 0.478 | **0.713** |
| Exact match | 34.7% (197/567) | **63.5%** (360/567) |

The dataset is 600 tracks; **567 are scored**. The other 33 are excluded because
their reference mode is `<tonic> other`, which the MIREX weighting cannot score.
90 references carry more than one acceptable key and are scored best-of.

Two caveats that matter as much as the number:

- **It is EDM-specific.** The winning key profile is Faraldo EDMA, derived from
  electronic dance music, and the benchmark is electronic dance music. The
  profile ranking, and possibly the whole result, **may not transfer to other
  genres**. Krumhansl-Kessler and Temperley remain selectable via
  `--key-profile` or `HARMONIA_KEY_PROFILE`, so this is testable rather than
  assumed. Do not quote 0.713 as a genre-independent figure.
- **It is not comparable to papers quoting the original 604-track GiantSteps.**
  GiantSteps+ is a corrected re-annotation of 600 tracks, a different set.

Full method, per-profile comparison and confusion breakdown: [`eval/baseline.md`](eval/baseline.md).
You can reproduce all of it yourself; see [Reproducing the numbers](#reproducing-the-numbers).

### Tier 2: heuristics with no ground truth

**Energy, danceability, and intro/outro mix points.** These are **not measured
against anything**, because no ground truth dataset exists for them. They are
defensible formulas, not validated predictions, and you should treat them as
relative sorting keys rather than absolute truths.

The formulas are published rather than hidden:

```
energy       = 0.6 * loudness   + 0.4 * brightness
danceability = 0.8 * punch      + 0.2 * steadiness
```

where each input is min-max mapped from its 2nd to 98th percentile as measured
across GiantSteps+. `loudness` is mean RMS, `brightness` is mean spectral
centroid, `punch` is onset strength at beats over the overall mean, and
`steadiness` is `1 - CV` of the beat intervals.

Because there is no ground truth, the recalibration was judged on **distribution
spread, not accuracy**: energy standard deviation moved 0.123 to 0.183 and
danceability 0.115 to 0.207, so the values now use their full range instead of
bunching. Two honest limitations: those percentile constants are EDM-derived and
may not suit other libraries, and beat steadiness barely varies on EDM (0.929 to
0.984), which makes its 0.2 weight close to a constant offset on this material.

Intro and outro mix points come from a beat-synchronous energy envelope with
sanity checks only. On a 30-track spot check the intro point looked plausible on
27 and the outro point on 29. That is a spot check, not a benchmark.

### Tier 3: not measured, or deferred

- **Tempo accuracy. There is no benchmark, and this is the least trustworthy
  number Harmonia prints.** No usable reference exists: the GiantSteps Tempo
  audio is unobtainable, the obtainable GiantSteps+ key audio overlaps that
  tempo set by only 43 of 664 tracks, and GTZAN is genre-mismatched. On those 43
  gold tracks the analyzer scores Accuracy1 0.419, and only 4 of the 25 misses
  are octave errors, so the problem is not the half/double-time ambiguity that
  was assumed. GTZAN is wired into the harness purely as a regression check
  across analyzer edits, and **no GTZAN tempo number is claimed as accuracy.**
- **Transition detection: deferred.** It cannot be validated without a per-track
  downbeat, and low-band energy gives no downbeat phase on four-on-the-floor
  material where the kick lands on every beat. It needs a trained downbeat model;
  madmom is ruled out on licence and Python version grounds.
- **Beat overlay: partially done.** The beat grid is computed, persisted and
  served at `GET /api/analysis/{id}/beats`. The interface does not draw it yet.

## Measured negative results

These were tried, measured, and reverted. They are listed because the discipline
of keeping them is what makes the tier 1 number above believable: the harness
reports losses as readily as wins.

| Change | Measured effect | Outcome |
| --- | --- | --- |
| HPSS (chroma on the harmonic component) | +0.0007 weighted, -1 exact, at **6.2x** the per-track cost (8.34 s vs 1.34 s) | reverted, within noise and expensive |
| `chroma_cqt` instead of `chroma_stft` | **-0.094 weighted**, -11 exact, at 1.3x cost | reverted, STFT is more accurate here, not merely cheaper |
| Tempo octave correction | abandoned: the only EDM tempo reference available agreed with gold on 2 of 24 tracks and carries the same half-time bias as the error under test | not pursued, unmeasurable |
| Tuning correction | already active (librosa's `chroma_stft` auto-estimates tuning); ablation showed disabling it costs 0.007 weighted | kept the default, it was never our addition |

The `chroma_cqt` result is worth stating plainly because it contradicts the
usual advice: on this corpus, with this profile, the cheaper front end is also
the more accurate one. A hypothesis is that the EDMA profile was derived against
STFT-style chroma and fits its shape better, but that is **unverified**; nobody
re-derived a profile against CQT chroma to test it.

## How analysis actually works

Per track, in order:

1. **Load.** The whole file, mono, resampled to 22050 Hz. Full track, not an
   excerpt: an earlier 45-second cap analyzed only the intro and cost 0.026
   weighted on the key benchmark.
2. **Onset envelope**, computed once and reused by both tempo and danceability.
3. **Tempo and beat grid.** `librosa.beat.beat_track` over that envelope. Beat
   times are persisted, not discarded.
4. **Chroma.** `librosa.feature.chroma_stft`, with librosa's default automatic
   tuning estimation left on. **Not** `chroma_cqt`; see the negative results above.
5. **Key.** The mean chroma is Pearson-correlated against all 24 rotations
   (12 tonics times major and minor) of a published key profile, default Faraldo
   EDMA, and the best match wins. Returns the key, a confidence, and the
   runner-up. This replaced an `argmax` tonic pick plus binary major/minor
   templates whose mode discrimination was close to a coin flip.
6. **Energy and danceability**, per the formulas above.
7. **Mix points.** Intro end and outro start from a beat-synchronous energy
   envelope.

Key profiles are implemented from the published papers: Krumhansl and Kessler
(1982), as tabulated in Krumhansl (1990); Temperley (1999), also in Temperley
(2001); and Faraldo et al. (2016) for EDMA. The numbers are the published
values; the correlation is implemented here independently, with no
third-party key-detection code copied, which is what keeps this MIT licensed.
Note that Krumhansl-Schmuckler names the classic key-finding *algorithm* that
uses the Krumhansl-Kessler profiles, not the profiles themselves.

## Getting music in

**Scan a folder (recommended).** Registers files in place, without copying:

```bash
python -m backend.scan ~/Music                # register
python -m backend.scan ~/Music --analyze      # register and analyze
```

Tracks are deduplicated by content hash (blake2b over the file size plus the
first and last 1 MB), so moving a file relinks it instead of creating a
duplicate, and rescanning is idempotent. One unreadable file never aborts a scan.

**Or upload through the interface**, which copies into the upload directory. Set
`HARMONIA_UPLOAD_DIR` to move that elsewhere.

## Architecture

One FastAPI process serves the API and the built React interface on a single
origin. SQLAlchemy over SQLite by default, Postgres if you set `DATABASE_URL`.
Schema is owned by Alembic migrations. librosa does the DSP. Analysis runs as a
background task and the interface polls for the result.

```
frontend/  React 19 + Vite, built to frontend/build/ and served by the backend
backend/
  api/         tracks, analysis, playlists endpoints
  audio/       analyzer.py (DSP), key_profiles.py, artwork.py
  models/      SQLAlchemy models and engine/session setup
  main.py      create_app() factory: all config read at call time
  scan.py      folder-scanning CLI
  storage.py   upload/artwork directory resolution
  tests/       unit, integration, acceptance, browser-driven end-to-end
alembic/     migrations
eval/        the accuracy harness (see below)
```

## Development

```bash
pip install -e ".[dev]"
pytest -m "not e2e"          # fast suite
pytest                       # everything, needs: pip install playwright && playwright install chromium
ruff check .
```

Two-terminal development, with hot reload:

```bash
python -m uvicorn --factory backend.main:create_app --reload --host 127.0.0.1 --port 8000
cd frontend && npm run dev   # binds port 3000 and proxies /api to the backend
```

The dev server proxies `/api` to port 8000 (see `frontend/vite.config.js`), so
the browser talks to one origin and no `VITE_API_URL` or CORS setup is needed.
Set `VITE_API_URL` only when the backend really is on another host.

## Reproducing the numbers

The accuracy table above is not something you have to take on trust. `eval/` is a
standalone harness that imports and calls `analyze_audio` exactly as the app
does, and never modifies it.

```bash
pip install -r eval/requirements.txt
python eval/fetch_datasets.py --key
python eval/run_eval.py --key
```

Results land in `eval/results/`. Be aware of the cost before starting:

- The GiantSteps+ audio download is about **817 MB**, and roughly **1.7 GB on
  disk** once extracted, because the archive is kept alongside the audio.
- A full 567-track scored run takes about **20 minutes** on a modern laptop
  (measured at 1.85 seconds per track over a 20-track sample).
- Start with `python eval/run_eval.py --key --limit 20` to confirm the pipeline
  end to end in about a minute before committing to the full run.

If Zenodo blocks the automated download, [`eval/README.md`](eval/README.md) has
the manual fallback, along with the full scoring method and the dataset choices.

## Known limitations

- The tempo figure is the weakest output and has no benchmark. See tier 3.
- Energy, danceability and mix points are unvalidated heuristics with EDM-derived
  constants. See tier 2.
- Key accuracy is benchmarked on EDM only and may not transfer.
- Analysis is a background task with no job table, so progress is coarse and an
  interrupted run has to be restarted per track.
- The beat grid is served but not drawn in the interface.
- No transition detection.

## Contributing

Contributions are welcome. [`CONTRIBUTING.md`](CONTRIBUTING.md) has the setup,
the working habits, and the one rule that matters most here: **do not claim what
you have not measured.** If you change the DSP, run `eval/` and report the delta.
Negative results are welcome and get documented rather than discarded; several
already are.

Please also read the [Code of Conduct](CODE_OF_CONDUCT.md).

For security reports, read [`SECURITY.md`](SECURITY.md) first. The absence of
authentication is documented design, not a vulnerability.

## Origin and credits

Harmonia began as a third-year LEI capstone at [Instituto Superior de Engenharia
do Porto](https://www.isep.ipp.pt/), supervised by Prof. Carlos Ferreira. The
state of the code at defence is preserved on the `academic` branch and the
`v0.1.0-academic` tag. Everything since is a rebuild toward a locally deployable
open-source tool.

| | |
| --- | --- |
| Adam Abdelkefi | Backend, DSP pipeline, web frontend |
| Inas Mezouri | Mobile app (Android) |

The companion Android app, by Inas Mezouri, lives at
[Harmonia-mobile](https://github.com/Harmonia-isep/Harmonia-mobile). **Note that
it targets the original authenticated API and has not been updated for the
auth-free endpoints**, so it will not work against this version without changes.

Evaluation data: GiantSteps+ EDM Key (CC BY-SA 4.0) and GTZAN. Neither is
redistributed here; both are downloaded on demand. See [`eval/NOTICE`](eval/NOTICE).

## License

MIT. See [LICENSE](LICENSE).
