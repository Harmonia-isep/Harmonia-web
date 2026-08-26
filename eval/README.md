# Harmonia evaluation harness

A standalone harness that measures `backend/audio/analyzer.py` against public
MIR reference datasets. It imports and calls `analyze_audio` exactly as the app
does and **never modifies it**: the analyzer is measured as-is, so the numbers
reflect the code that actually ships.

It reports:

- **Key** accuracy on GiantSteps+ EDM Key, MIREX-weighted plus a raw
  exact-match rate and a confusion breakdown.
- **Tempo** accuracy on GTZAN, Accuracy1 and Accuracy2 (with the octave-error
  share called out separately).
- **Energy / danceability** distributions, plus an audit of two suspected
  saturation pathologies inside the analyzer.

Nothing is vendored. Datasets download on demand into `eval/datasets/`, which is
gitignored; no audio or annotation file is ever committed. See `NOTICE` for
credits and licenses.

## Layout

| File | Purpose |
| --- | --- |
| `scoring.py` | Pure MIREX key + tempo Accuracy1/2 scoring. No heavy deps. |
| `audit.py` | Distribution summaries + recomputed loudness/punch intermediates. |
| `eval_datasets.py` | mirdata wrappers + GTZAN audio fetch; yields `(audio_path, reference)` pairs. |
| `fetch_datasets.py` | CLI: download the datasets. |
| `run_eval.py` | CLI: run the analyzer over the data, score, write the report. |
| `tests/` | Unit tests for scoring + a synthetic end-to-end smoke test. |
| `datasets/`, `results/` | Downloaded data and generated reports (gitignored). |

## Dataset choices (and why they differ from the original plan)

**Key: GiantSteps+ EDM Key (600 tracks), not the original GiantSteps Key (604).**
The original 604-track audio is hosted per-track on Beatport and is no longer
reliably obtainable; GiantSteps+ re-annotates essentially the same Beatport
excerpts and ships the audio in one Zenodo archive (record 1095691). Because it
is a different, corrected annotation set of 600 (not 604) tracks, **these key
numbers are not directly comparable** to papers that report on the original 604.

**Tempo: GTZAN, as a development regression check only.** The plan intended to
reuse the GiantSteps key audio for the tempo baseline (the "run tempo on the
overlap" option). We verified the overlap first: the GiantSteps key set and the
GiantSteps tempo set share only **43 Beatport IDs** (out of 664 tempo tracks),
so that path yields at most ~43 tempo tracks - too few to benchmark. GTZAN
provides freely obtainable audio (public Hugging Face mirror) plus single-BPM
tempo ground truth. It is wired into this harness **only as a development
regression check** - to catch shifts in tempo behaviour across analyzer edits -
**not as an accuracy claim.** GTZAN is not EDM and is not the GiantSteps Tempo
benchmark, so **no GTZAN tempo number belongs in the project README.**

> **Tempo benchmark gap (open).** Harmonia has no accuracy benchmark for tempo.
> GiantSteps Tempo annotations exist, but their Beatport audio is dead, and the
> obtainable GiantSteps+ key audio overlaps the tempo set by only 43 tracks -
> too small to benchmark. Revisit if a usable EDM tempo set with obtainable
> audio turns up, or if we hand-annotate one. This is open, not closed.

## How scoring works

**Key (MIREX weighted).** Each estimate is scored against the reference:

| Relationship | Score |
| --- | --- |
| Same key and mode | 1.0 |
| Estimate a perfect fifth **above** the reference (+7 semitones, same mode) | 0.5 |
| Relative major/minor | 0.3 |
| Parallel major/minor | 0.2 |
| Otherwise | 0.0 |

The fifth is **directional** (only +7), matching `mir_eval.key.weighted_score`;
the subdominant confusion (a fifth below) scores as "other", exactly as
mir_eval does. The test suite cross-checks our scoring against mir_eval across
all 576 key pairs. We report the weighted score, the raw exact-match rate, and
the confusion counts (fifth / relative / parallel / other) side by side.

**Ambiguous (multi-label) keys.** mirdata returns the first line of each
GiantSteps+ annotation as the reference key. GiantSteps+ is a single-key
dataset, but the harness does not assume it. If a reference lists more than one
acceptable key (delimited by `|`, `/`, `,`, `;`, or `and`), the estimate is
scored against every listed key and the **highest** MIREX weight is kept
(best-of), with the category taken from that best match. A single analyzer emits
one key, so best-of never penalises it for choosing any acceptable label. The
run reports how many multi-label references were seen (`n_multi_label`);
references that parse to no key at all are excluded and counted
(`n_unparseable_ref`). One limitation: because mirdata reads only the first
line, any acceptable keys on later lines are not visible to the harness.

**Tempo (Accuracy1 / Accuracy2).**

- **Accuracy1**: estimate within 4% of the reference.
- **Accuracy2**: Accuracy1, or within 4% of the reference scaled by 1/3, 1/2, 2
  or 3 (the half/double/third/triple confusions).
- We also report how many Accuracy2 hits were **octave errors** (passed
  Accuracy2 but not Accuracy1).

**Feature audit.** `analyze_audio` does not expose its internal `loudness` and
`punch` terms, and Phase 4 forbids changing the analyzer, so `audit.py`
recomputes exactly those lines from the same audio to test two suspicions:

- `loudness = min(1.0, rms_mean / 0.3)` saturating at 1.0, and
- `punch = max(0.0, min(1.0, (ratio - 3) / 6))` clamping to 0.0.

The report states, over the audited files, how often each actually hit its
ceiling/floor - confirming or refuting the concern with data rather than
argument.

## Setup

From the repository root, in the app's Python environment:

```bash
pip install -r eval/requirements.txt
```

This installs the eval-only dependencies (mirdata, mir_eval, requests).
librosa, numpy, scipy and soundfile come from the main app requirements.

## Reproduce the baseline

```bash
# 1. Download the datasets (into eval/datasets/, gitignored).
python eval/fetch_datasets.py --all      # or --key / --tempo

# 2. Run the analyzer over the data and write the report.
python eval/run_eval.py --all            # or --key / --tempo
```

Outputs land in `eval/results/`:

- `baseline.txt` - human-readable report (scores, confusion, histograms, audit).
- `baseline.json` - the same numbers as structured data (raw per-track series
  omitted).

Useful flags:

- `--limit N` caps tracks per dataset for a quick smoke run.
- `--audit-sample N` sets how many files feed the saturation audit (default 150).

**Expect the full run to take a while.** The datasets total a few GB to
download, and running librosa over ~1600 tracks is CPU-bound and can take hours
on a laptop. Start with `--limit 20` to confirm the pipeline end to end, then
run the full set.

### If Zenodo blocks the automated key download

Zenodo occasionally rejects automated requests. If `fetch_datasets.py --key`
fails, download `audio.zip` and `keys.zip` manually from
<https://zenodo.org/record/1095691>, place them under
`eval/datasets/giantsteps_key/` following mirdata's layout, and rerun
`run_eval.py --key` (it validates what is present).

## Tests

The scoring tests are pure and fast; the smoke test synthesizes a few WAVs and
runs the whole pipeline (no download, no mirdata):

```bash
PYTHONPATH=eval python -m pytest eval/tests/ --noconftest
```

`--noconftest` skips the repository's root `conftest.py` (which pulls in the app
test fixtures and Alembic); the eval tests need none of it.

## Data policy

- **Vendor nothing.** All data downloads at runtime into `eval/datasets/`.
- **Never commit audio.** `datasets/` and `results/` are gitignored.
- Only the harness code, tests, and docs are tracked.
