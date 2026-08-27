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

## Phase 6 key work: summary and stopping point

Key accuracy is **closed at 0.713 weighted / 63.5% exact** (GiantSteps+, 567
scored). The full trajectory, and every change measured along the way:

| Stage | Weighted | Exact | Shipped? |
| --- | --- | --- | --- |
| Baseline (argmax tonic + binary maj/min templates) | 0.478 | 0.347 (197/567) | - |
| + weighted key profiles + 24-rotation correlation, EDMA (step 1) | 0.687 | 0.605 (343/567) | yes |
| + full track, drop the 45 s cap (step 2) | **0.713** | **0.635 (360/567)** | **yes** |

Changes measured but **not shipped** (each detailed in its own section above):

| Change | Measurement | Outcome |
| --- | --- | --- |
| Tuning correction | already active via librosa's `chroma_stft` default; ablation (disabled) = -0.007 weighted / -7 exact | kept the default - it was never our addition |
| HPSS (harmonic chroma) | +0.0007 weighted / -1 exact, like-for-like on 150 tracks; 6.2x per-track cost | reverted |
| chroma_cqt | -0.094 weighted / -11 exact, like-for-like on 150 tracks; 1.3x cost | reverted |

**Why key accuracy plateaued, and why we stopped.** The two large levers were the
profile/correlation rewrite (+0.209 weighted) and full-track analysis (+0.026).
After those, three successive audio-side changes - tuning (already on), HPSS, and
chroma_cqt - each returned no gain or a loss. Front-end tuning is exhausted on
this corpus with this approach. The remaining error budget at 0.713 (of 567
scored: `other` 89 = 15.7%, `fifth` 62 = 10.9%, `parallel` 35 = 6.2%, `relative`
21 = 3.7%) would need a different class of method - a learned model, or
key-change-aware segmentation - not more front-end tweaking. Further key work is
not pursued.

**CQT hypothesis (UNVERIFIED).** chroma_cqt losing 0.094 may be a profile-chroma
interaction: the EDMA profile was derived against STFT-style chroma, so its
correlation may fit the STFT chromagram's shape better than the CQT's. This is a
hypothesis only - we did not re-derive a profile against CQT chroma to test it,
so it must not be stated as a cause.

**Corpus-match caveat (EDMA).** EDMA wins because it was built from electronic
dance music and this benchmark is electronic dance music. The 0.713 figure is
**EDM-specific**; the profile ranking, and possibly the whole key result, may not
transfer to other genres, whose tonal profiles differ. KS and Temperley stay
selectable via `--key-profile` / `HARMONIA_KEY_PROFILE` so this is testable, not
assumed. Do not quote 0.713 as a genre-independent number.

## Energy and danceability recalibration (heuristics, NO ground truth)

Unlike key - which is benchmarked against GiantSteps+ annotations - energy and
danceability have **no ground truth**. There is nothing to be "accurate" against;
the only goal is that each descriptor uses its full [0, 1] range on this corpus
instead of bunching. **Success here is distributional spread, not accuracy.** The
old constants (loudness `rms/0.3`, brightness `centroid/4000`, punch
`(ratio-3)/6`) were ad-hoc thresholds that clipped the descriptors into a narrow
band.

Recalibration replaces each ad-hoc threshold with a robust min-max map from the
intermediate's measured 2nd..98th percentile on GiantSteps+ (600 tracks, full
track) onto [0, 1]. Each constant is a measured percentile, so a reader can see
where it came from:

    scale(x, lo, hi) = clip((x - lo) / (hi - lo), 0, 1)

    loudness   = scale(rms_mean,           0.131, 0.386)   # RMS energy
    brightness = scale(centroid_mean,      1353,  3676)    # spectral centroid (Hz)
    energy     = 0.6 * loudness + 0.4 * brightness

    punch      = scale(beat/mean-onset,    2.133, 5.959)   # pulse-strength ratio
    steadiness = scale(1 - CV(beat ivals), 0.929, 0.984)   # beat regularity
    danceability = 0.8 * punch + 0.2 * steadiness

The weightings (0.6/0.4, 0.8/0.2) are unchanged; only the per-component scaling
was recalibrated. **The constants are corpus-derived from EDM and may not
transfer** - recalibrate if the target corpus changes.

Before (the current shipped, full-track analyzer) vs after, over all 600 tracks:

| Descriptor | mean | std | min - max | shape |
| --- | --- | --- | --- | --- |
| energy, before | 0.736 | 0.123 | 0.34 - 0.99 | bunched in [0.6, 0.9] |
| **energy, after** | 0.480 | 0.183 | 0.00 - 1.00 | spread across [0, 1] |
| danceability, before | 0.309 | 0.115 | 0.19 - 0.95 | bunched in [0.1, 0.4] |
| **danceability, after** | 0.481 | 0.207 | 0.05 - 1.00 | spread across [0, 1] |

Decile counts (0->1), after: energy `10 24 70 94 138 109 79 52 20 4`;
danceability `5 45 73 102 116 88 70 55 27 19`. Both spreads roughly doubled and
both descriptors now use their full range.

**Note on the "before" numbers.** The Phase 4 distributions recorded earlier in
this file (energy mean 0.713, danceability mean 0.320) were measured on the
pre-step-2 analyzer (45-second cap), so they no longer match. The current shipped
analyzer is full-track, so its distribution (energy mean 0.736, danceability mean
0.309) is the honest "before" for this recalibration.

### Open question: steadiness is near-constant on EDM

The beat-steadiness intermediate (`1 - CV` of beat intervals) spans only **0.929
to 0.984** (p2..p98) across the corpus - it barely varies, because essentially
every EDM track has a rock-steady grid. So its 20% weight in danceability is close
to a **constant offset** on this corpus and adds little discriminative signal. The
weighting is **left unchanged** here (changing it is a separate experiment). Open
question: whether to drop or reweight steadiness, or replace it with a rhythm
feature that actually varies - to be decided on a corpus where it does.

## Tempo: octave correction not pursued, and a reference gap

Unlike key, tempo has no obtainable genre-correct benchmark: the GiantSteps Tempo
audio is unavailable (Beatport), and GTZAN is genre-mismatched (dev-regression
only). Before attempting the planned octave correction, we tried to build an EDM
tempo reference from the Beatport tempo carried in the GiantSteps+ metadata (491
of 600 tracks have it; the audio is already local) and validated it against the
hand-verified GiantSteps Tempo gold on the beatport-id overlap.

**The reference failed validation.** Of the 43 overlapping tracks, 24 have both a
metadata tempo and a gold annotation:

- metadata agrees with gold on **2 of 24 within 4%** (0 of 24 exact).
- **10 of the 22 disagreements are octave relations**, systematically half-time:
  88 vs 175, 70 vs 140, 87 vs 174, 86 vs 173, 88 vs 175. Beatport lists high-BPM
  genres (drum and bass, hardcore) at half tempo as a labelling convention.

This **disqualifies the metadata for evaluating octave correction**: the
reference carries the *same* half/double bias as the error under test, so it
cannot tell a corrected octave from an uncorrected one. (It remains fine as the
key benchmark - key does not depend on tempo.)

**Current tempo baseline (43 gold tracks: local audio + hand-verified tempo):**

| Metric | Value |
| --- | --- |
| Accuracy1 (within 4%) | 18/43 = **0.419** |
| Accuracy2 (+ octave) | 22/43 = 0.512 |
| octave errors (Acc2 not Acc1) | 4/43 |

Caveats: 43 tracks is a small sample, and GiantSteps Tempo skews hard (it was
built from difficult Beatport excerpts). Treat these as indicative, not a
benchmark figure.

**Decision: octave correction is not pursued.** The addressable population is only
**4 of 43** tracks (the octave errors); the maximum possible gain is ~+0.09 Acc1
on a 43-track sample, indistinguishable from noise. No genre-correct reference
large enough to measure it exists, because the GiantSteps Tempo audio is
unobtainable. Shipping an unmeasurable change to a working tempo detector is worse
than not shipping it.

**Open question (NOT closed): tempo detection has a different problem than the
plan assumed.** Acc1 of 0.419 is low for EDM - lower than expected for the Ellis
(2007) dynamic-programming beat tracker on strongly-metered dance music - and only
**4 of the 25 misses are octave errors**; the other 21 are unrelated tempo values,
not half/double. So the dominant tempo error is *not* the octave ambiguity the
plan set out to fix: the detector is getting the tempo outright wrong on many
tracks. This is unresolved, and cannot be resolved to a number, for lack of a
genre-correct reference. See the plan's open questions.

## Structural segmentation: mix points shipped, transitions deferred

Scope was mix-point detection for DJing - intro end, outro start, and major
transition boundaries - NOT section labelling. Intro/outro shipped; transition
detection is deferred; the investigation is the useful part.

**Approach.** Foote novelty over a beat-synchronous MFCC self-similarity matrix
for transitions (no section labels, so it cannot drift into verse/chorus
classification), plus a beat-synchronous energy envelope for intro end / outro
start. Laplacian segmentation (the plan's suggestion) was rejected: it clusters
frames into labelled sections - the labelling we were avoiding - and is heavier.
Everything is beat-synchronous (using the persisted beat grid), which keeps the
self-similarity matrix tiny (~250x250) and lands boundaries on beats by
construction.

**Measurements (30 fixed GiantSteps+ tracks).** Per-track cost 0.27 s (~+20% on
the ~1.3 s analyze - cheap, because beat-syncing keeps the matrix small).
Stability 0.91 boundary retention under +/-1 step of kernel width and peak
threshold (not fitting noise). Transition count in [2, 8] on 28/30 tracks.

**The evaluation problem, and how the null baseline resolved it.** There is no
ground truth for mix points. The proxy was phrase-alignment: how often detected
boundaries land on the 8-bar phrase grid, where real EDM mix points sit.
Validated against a NULL baseline of random matched-count beats:

| Metric | Detector | Null (random beats) |
| --- | --- | --- |
| Anchored (phrase grid at beat 0) | 0.268 | 0.084 |
| Best-phase (best of 32 grid offsets) | 0.554 | 0.474 |

The null did two jobs: it validated the anchored metric (detector 3.2x chance)
and it **exposed the best-phase variant as gameable** - with only ~3.6 boundaries
per track, best-of-32 offsets aligns random beats too (null 0.47 ~ detector
0.55), so best-phase measures nothing. Discarded. But anchoring the phrase grid at
beat 0 is wrong: beat tracking yields beats, not downbeats, so the grid is out of
phase and the anchored 0.27 is a deflated lower bound. A correct anchor needs a
per-track downbeat.

**Why the downbeat-phase estimate failed - the root cause.** We estimated the
phrase phase from low-band (kick/bass) energy on candidate downbeats and validated
the estimate's confidence (winner-vs-runner-up margin) per track:

| Grid | mean margin | tracks > 0.10 margin |
| --- | --- | --- |
| Bar (period 4) | 0.040 | 4/30 |
| Phrase (period 32) | 0.022 | 0/30 |

**No track has a phrase-phase margin above 0.10 - the estimate is a coin flip.**
Anchoring the metric to it made the detector alignment worse than beat 0 (0.029 vs
0.268) and below null (0.073). The root cause is **structural to the genre, not a
tuning failure: GiantSteps+ is four-on-the-floor EDM, where the kick lands on every
beat, not just downbeats, so low-band energy is nearly flat across beat phases and
carries almost no downbeat phase information.** The method is sound in principle
but the signal it needs is absent in this genre. A reliable phrase anchor would
require a trained downbeat model (e.g. madmom's DBN), ruled out on licence and
Python-version grounds (see HARMONIA_REBUILD_PLAN.md constraints).

Three measurement instruments in a row failed validation here - Beatport tempo
metadata (octave-biased), best-phase (gameable), the low-band phase estimate (coin
flip). Validating each before use caught all three; each would otherwise have
produced a confident-looking but meaningless number.

**What shipped.** Major-transition detection is **deferred** - it cannot be
validated on this corpus without a downbeat model. Intro end and outro start ship
as `intro_end` / `outro_start` float columns on `analyses`, from the
beat-synchronous energy envelope. These are **heuristics with sanity checks only,
no ground truth - the same evidential class as energy and danceability, NOT the
benchmarked key.** The only checks are plausibility: on the 30 tracks intro_end
fell in the first quarter on **27/30** and outro_start in the last quarter on
**29/30** - plausibility counts, not accuracy. No downbeat phase is stored (it
cannot be estimated reliably), so bar/phrase lines are unavailable to the overlay -
only the beat grid and these two points.
