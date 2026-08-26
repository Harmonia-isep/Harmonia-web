# Harmonia analyzer baseline

The committed, human-readable record of the Phase 4 key baseline. The analyzer is
measured **as-is** (imported and called, not modified). The raw machine output lives in
`eval/results/` (`baseline.txt` / `baseline.json`), which is gitignored; this file is the
record that travels with the repo.

## Run metadata

- **Date:** 2026-08-27
- **Analyzer measured:** `backend/audio/analyzer.py` at commit `4f9f17f` (unchanged
  since; the run was performed at repo HEAD `444f7f8` with a clean analyzer working tree).
- **Dependencies** (from `requirements.lock`): librosa 0.11.0, numpy 2.4.6, scipy 1.17.1,
  soundfile 0.13.1, numba 0.67.0. The eval virtualenv resolved numpy 2.4.4 (a patch
  difference from the lock); it does not affect the results.
- **Dataset:** GiantSteps+ EDM Key, 600 tracks (Zenodo record 1095691), mirdata
  `giantsteps_key` index version `+`. This is the re-annotated 600, not the original 604,
  so the numbers are **not directly comparable** to papers on the 604-track set.
- **Command:** `python eval/run_eval.py --key` (full set; saturation-audit sample = 150).

## Key accuracy (MIREX-weighted)

600 tracks total. **567 scored.** 33 excluded because the reference mode is
`<tonic> other` (no major/minor ground truth, so a major/minor detector cannot be scored
against them). 90 references were multi-label (two acceptable keys) and were scored
best-of. **0 analysis errors.**

| Metric | Value |
| --- | --- |
| **Weighted score (MIREX)** | **0.478** |
| **Raw exact-match rate** | **0.347** (197/567) |

Confusion breakdown (of 567 scored):

| Category | Count | Share |
| --- | --- | --- |
| correct | 197 | 34.7% |
| fifth | 99 | 17.5% |
| relative | 34 | 6.0% |
| parallel | 73 | 12.9% |
| other | 164 | 28.9% |

**Reading.** Exact key is right about a third of the time. The largest error bucket is
`other` (an unrelated key, 28.9%), which means tonic selection is frequently wrong, not
just the mode. Fifths (17.5%) and parallel / wrong-mode errors (12.9%) follow. The
parallel bucket is large enough to matter on its own: the binary major/minor templates in
the analyzer differ by a single pitch class, so the mode decision is close to a coin flip.
This is what reorders Phase 6 (key profiles and 24-rotation correlation move first);
audio-side changes will not fix an algorithmic tonic/mode problem.

**25-track sample, for comparison.** An earlier `--limit 25` run gave weighted **0.475**
and exact-match **0.292** (7/24), with `parallel` and `fifth` roughly equal at that
scale. The full run confirms the low weighted score, and shifts the error mix: fifths
edge out parallels, and `other` becomes the largest bucket. Treat the sample's category
split as noise; the full-set split above is the record.

## Feature distributions (567 tracks, analyzer output)

**Energy** - min 0.142, max 0.999, mean 0.713, stdev 0.144. Spread across the upper half,
peaking in [0.8, 0.9]. Not saturated and not near-constant.

| bin | count |
| --- | --- |
| [0.1, 0.2) | 1 |
| [0.3, 0.4) | 13 |
| [0.4, 0.5) | 40 |
| [0.5, 0.6) | 73 |
| [0.6, 0.7) | 108 |
| [0.7, 0.8) | 142 |
| [0.8, 0.9) | 152 |
| [0.9, 1.0) | 38 |

(Bins [0.0, 0.1) and [0.2, 0.3) were empty.)

**Danceability** - min 0.000, max 0.992, mean 0.320, stdev 0.132. Heavily low-skewed:
about 78% of tracks fall in [0.1, 0.4], and only ~11% exceed 0.5. The full [0, 1] range
is reachable (the 25-track sample topped out at 0.49, which was a small-sample artifact),
but the mass sits low.

| bin | count |
| --- | --- |
| [0.0, 0.1) | 1 |
| [0.1, 0.2) | 133 |
| [0.2, 0.3) | 152 |
| [0.3, 0.4) | 157 |
| [0.4, 0.5) | 80 |
| [0.5, 0.6) | 25 |
| [0.6, 0.7) | 6 |
| [0.7, 0.8) | 6 |
| [0.8, 0.9) | 4 |
| [0.9, 1.0) | 3 |

## Internal saturation audit (150 files, recomputed from analyzer.py)

The analyzer does not expose its internal `loudness` and `punch` terms, so these were
recomputed from the same audio (a faithful mirror of the analyzer's energy/danceability
block) to test the two suspected pathologies.

- **`loudness = min(1.0, rms/0.3)` - partial saturation.** Hit the 1.0 ceiling in
  **27/150 (18.0%)**. Raw `rms/0.3` ranged 0.09 to 1.38, mean 0.78. It does not
  universally clip, but roughly one track in five does, and the mean sits near the
  ceiling. The concern is real but not total.
- **`punch = max(0, min(1, (ratio-3)/6))` - low-skew with a hard floor.** Clamped to 0.0
  in **28/150 (18.7%)**. The beat / mean-onset ratio ranged 1.69 to 10.37 (mean 3.95).
  The bulk sit in [2.5, 5.2] (punch roughly [0, 0.37]), which is why danceability skews
  low, but the tail reaches punch ~1.0. So punch is **not** structurally capped at ~0.4
  (that was a 25-track-sample artifact); the real finding is a low-skewed distribution
  with the 0.0 floor hit about 19% of the time.

## What this drives

- Phase 6 is reordered: weighted key profiles + 24-rotation correlation move first,
  because the `parallel` and `other` errors are algorithmic, not audio-quality.
- The energy/danceability rebuild (Phase 6) recalibrates its constants against the
  measured ranges above rather than the current ad-hoc `-3` / divide-by-6.

Reproduce: see `eval/README.md`.
