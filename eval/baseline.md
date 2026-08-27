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

## Tuning correction (ablation, not an improvement step)

The plan listed "tuning correction" as a Phase 6 step. It turned out to be
**already active, and not an addition by us**: `chroma_stft(y=y, sr=sr)` uses
`tuning=None`, and librosa auto-estimates and applies tuning internally
(`feature/spectral.py`). So tuning correction was never absent - it came for free
with librosa's default. To quantify what it is worth, we ran an **ablation** with
tuning disabled (`tuning=0.0`), everything else identical, then reverted (we do
not ship tuning disabled).

Corpus tuning deviation from A440 (120-track sample): mean -1.2 cents, std 11.5;
**63% within +/-5 cents**, 76% within +/-10 cents, but **~24% beyond +/-10 cents**
(range -32 to +48). Most tracks are near A440, with a detuned tail.

| Analyzer (EDMA, full track) | Weighted (MIREX) | Exact-match | correct | fifth | relative | parallel | other |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tuning on (librosa default, **shipped**) | 0.713 | 0.635 (360/567) | 360 | 62 | 21 | 35 | 89 |
| tuning off (`tuning=0.0`, ablation) | 0.706 | 0.623 (353/567) | 353 | 68 | 21 | 35 | 90 |

Disabling tuning correction costs **0.007 weighted and 7 exact matches**
(360 -> 353), the losses going mostly to fifth errors (62 -> 68). Small but
positive: it earns its keep on the detuned tail, and it is already on. We keep
librosa's default (`tuning=None`); the analyzer carries a comment at the
`chroma_stft` call warning not to hardcode `tuning=0.0`. Run metadata as in the
step-2 section (date 2026-08-27; requirements.lock librosa 0.11.0 / numpy 2.4.6 /
scipy 1.17.1; dataset GiantSteps+ 600, mirdata version `+`; 567 scored).

## HPSS (measured negative result, reverted)

Phase 6 step 3 (after the reorder): compute chroma on the harmonic component only
(`librosa.effects.hpss`), so percussion stops leaking into pitch-class bins. HPSS
is expensive, so we compared it **like-for-like on the same 150 tracks** (first
150 of the corpus, 137 scored). Comparing a 150-track HPSS run against the
full-567 figure (0.713) would repeat the Phase 4 sample artifact - this subset is
harder and scores 0.647 without HPSS, so the honest baseline is the same-tracks
non-HPSS run.

| Analyzer (EDMA, full track), same 150 tracks | Weighted (MIREX) | Exact-match | correct | fifth | relative | parallel | other |
| --- | --- | --- | --- | --- | --- | --- | --- |
| non-HPSS (shipped) | 0.6467 | 0.555 (76/137) | 76 | 18 | 2 | 15 | 26 |
| + HPSS (harmonic chroma) | 0.6474 | 0.547 (75/137) | 75 | 20 | 3 | 14 | 25 |

Delta: **+0.0007 weighted, -1 exact match** (75 vs 76) - within noise, no
accuracy gain. Cost: **6.2x slower per track** (8.34 s vs 1.34 s; a full-600 run
would take ~83 min vs ~14).

Per the decision rule fixed before the run (gain over +0.03 weighted -> run the
full 567; under -> revert and record), HPSS was **reverted**. It is not a win on
this EDM corpus: EDM is harmonically dense and `chroma_stft` already captures the
tonal content well, so removing percussion does not move the key result. A real
negative result: a 6.2x cost bought nothing here. Revisit only if a later change
(e.g. `chroma_cqt`) changes the picture.

## chroma_cqt (measured negative result, reverted)

Phase 6 step 4 (after the reorder): swap `chroma_stft` for `chroma_cqt`
(log-spaced, semitone-aligned bins). Before running we diffed the two functions'
defaults, because the tuning finding showed librosa's defaults carry weight.
**Both auto-estimate tuning** when `tuning=None` (chroma_stft via
`estimate_tuning(S)`; chroma_cqt by forwarding `tuning=None` to `cqt`, which
auto-estimates), and `norm` (inf), `hop_length` (512) and `n_chroma` (12) are
identical - so the comparison is fair, differing only in the transform. Compared
**like-for-like on the same 150 tracks** (137 scored) against the shipped
chroma_stft analyzer.

| Analyzer (EDMA, full track), same 150 tracks | Weighted (MIREX) | Exact-match | correct | fifth | relative | parallel | other |
| --- | --- | --- | --- | --- | --- | --- | --- |
| chroma_stft (shipped) | 0.6467 | 0.555 (76/137) | 76 | 18 | 2 | 15 | 26 |
| chroma_cqt | 0.5526 | 0.474 (65/137) | 65 | 13 | 4 | 15 | 40 |

Delta: **-0.094 weighted, -11 exact matches** (65 vs 76) - a large regression,
the damage concentrated in `other` (unrelated key) errors (26 -> 40). Cost was
only 1.3x per track (1.78 s vs 1.34 s), so cost was not the issue; accuracy was.
Per the decision rule fixed before the run (gain over +0.03 -> full run; under ->
revert), chroma_cqt was **reverted**.

This overturns the original code comment that STFT gave "essentially the same key
result" as CQT: on this corpus STFT is not equivalent, it is **better**. A
plausible but **untested** reason is a profile-chroma interaction - the EDMA
profile was derived against STFT-style chroma, so its correlation may fit the
STFT chromagram's shape better than the CQT's. Recorded as a measured negative
and a hypothesis for later, not a verified cause.
