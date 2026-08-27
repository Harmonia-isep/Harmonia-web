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

## Phase 6 step 1: weighted key profiles + 24-rotation correlation

Replaced the argmax-tonic plus one-pitch-class binary major/minor templates with
Pearson correlation of the mean chroma against all 24 rotations (12 tonics x
major and minor) of a selectable published key profile. This is one change: the
analyzer's load parameters, chroma, tempo, energy, and danceability are
unchanged, so the rows below are directly comparable to the baseline row.

Run metadata:

- **Date:** 2026-08-27
- **Analyzer measured:** `backend/audio/analyzer.py` at commit `bcababb` (the
  24-rotation change); the profile was selected per run via `--key-profile`.
- **Dependencies** (`requirements.lock`): librosa 0.11.0, numpy 2.4.6, scipy
  1.17.1 (eval venv resolved numpy 2.4.4).
- **Dataset:** GiantSteps+ EDM Key, 600 tracks; mirdata `giantsteps_key` version
  `+`. **567 scored** (33 excluded as `<tonic> other`; 90 multi-label scored
  best-of; 0 analysis errors) - identical accounting to the baseline row.

| Profile | Weighted (MIREX) | Exact-match | correct | fifth | relative | parallel | other |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline (argmax + binary templates) | 0.478 | 0.347 (197/567) | 197 | 99 | 34 | 73 | 164 |
| Temperley (1999/2001) | 0.512 | 0.397 (225/567) | 225 | 92 | 47 | 25 | 178 |
| Krumhansl-Kessler (`ks`) | 0.615 | 0.519 (294/567) | 294 | 79 | 23 | 42 | 129 |
| **Faraldo EDMA** (default) | **0.687** | **0.605 (343/567)** | 343 | 67 | 18 | 37 | 102 |

All three profiles beat the baseline. EDMA wins by a clear margin (+0.209
weighted, +0.258 exact over the baseline; 197 -> 343 correct), and is now the
analyzer default. It cuts exactly the errors the baseline was worst at: `other`
(unrelated key) 164 -> 102, and `parallel` (wrong mode) 73 -> 37.

**Why EDMA wins, and a caveat.** EDMA was derived from a corpus of electronic
dance music, and this evaluation corpus is electronic dance music. This is a
**corpus-matched** result: EDMA is expected to fit an EDM test set well. The
ranking may not hold on other genres - a classical or pop corpus could favour
Krumhansl-Kessler or Temperley, whose profiles come from a different tradition.
Do not read "EDMA is best" as genre-independent. All three profiles stay
selectable (`--key-profile` / `HARMONIA_KEY_PROFILE`) precisely so this can be
retested on other corpora rather than assumed.

## Phase 6 step 2: full track instead of the 45-second cap

One change: dropped `duration=45` from the analyzer's `librosa.load`, so the
whole excerpt is analyzed instead of only the first 45 seconds. Everything else
(EDMA profile, chroma, tempo, energy, danceability) is unchanged. Same 567
scored (33 excluded, 90 multi-label, 0 analysis errors).

Run metadata:

- **Date:** 2026-08-27
- **Analyzer measured:** EDMA default with the 45-second cap removed (the Phase 6
  step 2 change).
- **Dependencies** (`requirements.lock`): librosa 0.11.0, numpy 2.4.6, scipy
  1.17.1 (eval venv resolved numpy 2.4.4).
- **Dataset:** GiantSteps+ EDM Key, 600 tracks; mirdata `giantsteps_key` version
  `+`. 567 scored, identical accounting to the rows above.

| Analyzer | Weighted (MIREX) | Exact-match | correct | fifth | relative | parallel | other |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EDMA, 45s cap | 0.687 | 0.605 (343/567) | 343 | 67 | 18 | 37 | 102 |
| **EDMA, full track** | **0.713** | **0.635 (360/567)** | 360 | 62 | 21 | 35 | 89 |

Full track improves over the 45-second cap by +0.026 weighted and +0.030 exact
(343 -> 360 correct). The gain is mostly in tonic selection: `other` (unrelated
key) drops 102 -> 89, because the analyzer no longer judges the whole track from
its intro. It is a real but **modest** win - far smaller than the profile change
in step 1 - which confirms the Phase 6 reorder: the profile and correlation work
was the large lever, full track a smaller increment. Cost: about 2.5x slower per
track (1.34 s vs 0.54 s on these 2-minute excerpts), acceptable for a local tool.
