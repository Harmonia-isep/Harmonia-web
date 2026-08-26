"""Distribution stats and an internal-saturation audit for analyzer features.

Two jobs:

1. `summarize` / `format_histogram` - min/max/mean/stdev plus a rough text
   histogram, used by the runner to describe the spread of `energy` and
   `danceability` across a dataset.

2. `audit_intermediates` - the Phase 4 audit of two suspected pathologies in
   backend/audio/analyzer.py:
      - loudness = min(1.0, rms_mean / 0.3)          # saturates at 1.0
      - punch    = max(0.0, min(1.0, (ratio - 3)/6)) # clamps to 0.0
   analyze_audio does not return these intermediates, and Phase 4 forbids
   modifying the analyzer, so we recompute exactly those lines here from the
   same audio the analyzer would load. This is a faithful MIRROR of
   analyzer.py's energy/danceability block - if that block changes, this must
   be updated to match. It exists only to measure, never to replace.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass

import librosa
import numpy as np

# Mirror of analyzer.py's load parameters so the intermediates line up with the
# values the analyzer actually computes.
_SR = 22050
_DURATION = 45


# --------------------------------------------------------------------------- #
# Distribution summary
# --------------------------------------------------------------------------- #


def summarize(
    values: list[float],
    bins: int = 10,
    lo: float | None = None,
    hi: float | None = None,
) -> dict:
    """min/max/mean/stdev plus a `bins`-way histogram over [lo, hi].

    lo/hi default to the observed min/max. Returns a plain dict (JSON-friendly).
    """
    vals = [float(v) for v in values]
    n = len(vals)
    if n == 0:
        return {"n": 0, "min": None, "max": None, "mean": None, "stdev": None,
                "bins": []}

    vmin, vmax = min(vals), max(vals)
    lo = vmin if lo is None else lo
    hi = vmax if hi is None else hi

    # Guard a degenerate range so binning does not divide by zero.
    span = hi - lo
    edges = [lo + span * i / bins for i in range(bins + 1)] if span > 0 else None
    counts = [0] * bins
    if edges is not None:
        for v in vals:
            # Clamp into range, last bin inclusive of the top edge.
            idx = int((v - lo) / span * bins)
            idx = min(max(idx, 0), bins - 1)
            counts[idx] += 1
    else:
        counts[0] = n  # all values identical

    bin_rows = []
    for i in range(bins):
        blo = edges[i] if edges else lo
        bhi = edges[i + 1] if edges else hi
        bin_rows.append({"lo": blo, "hi": bhi, "count": counts[i]})

    return {
        "n": n,
        "min": vmin,
        "max": vmax,
        "mean": statistics.fmean(vals),
        "stdev": statistics.pstdev(vals) if n > 1 else 0.0,
        "bins": bin_rows,
    }


def format_histogram(summary: dict, width: int = 40, label: str = "") -> str:
    """Render a `summarize` result as an aligned text histogram."""
    if summary["n"] == 0:
        return f"{label}: (no data)"
    lines = []
    if label:
        lines.append(label)
    lines.append(
        "  n={n}  min={min:.4f}  max={max:.4f}  mean={mean:.4f}  stdev={stdev:.4f}".format(
            **summary
        )
    )
    peak = max((b["count"] for b in summary["bins"]), default=0) or 1
    for b in summary["bins"]:
        bar = "#" * round(b["count"] / peak * width)
        lines.append(f"  [{b['lo']:.3f}, {b['hi']:.3f})  {b['count']:5d} |{bar}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Internal-saturation audit
# --------------------------------------------------------------------------- #


@dataclass
class Intermediates:
    """Recomputed internal values from analyzer.py's energy/danceability block."""

    rms_mean: float
    loudness_raw: float          # rms_mean / 0.3, before the min(1.0, .) clamp
    loudness: float              # min(1.0, loudness_raw)
    loudness_saturated: bool     # loudness hit the 1.0 ceiling
    brightness: float
    punch_ratio: float           # beat_strength / mean(onset_env), before rescale
    punch: float                 # max(0, min(1, (ratio - 3) / 6))
    punch_clamped_zero: bool     # punch hit the 0.0 floor
    had_beats: bool              # analyzer's `len(beat_frames) > 2` branch


def audit_intermediates(file_path: str) -> Intermediates:
    """Recompute analyzer.py's loudness and punch intermediates for one file.

    Kept deliberately line-for-line with analyzer.py's energy/danceability
    section (as of the commit under test) so the audit reflects the real code
    path, not an approximation.
    """
    y, sr = librosa.load(file_path, sr=_SR, mono=True, duration=_DURATION)

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    _, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)

    # --- loudness (analyzer.py lines 36-37) ---
    rms_mean = float(np.mean(librosa.feature.rms(y=y)))
    loudness_raw = rms_mean / 0.3
    loudness = min(1.0, loudness_raw)

    # --- brightness (analyzer.py lines 38-39), reported for context ---
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    brightness = min(1.0, float(np.mean(centroid)) / 4000.0)

    # --- punch (analyzer.py lines 44-54) ---
    had_beats = len(beat_frames) > 2
    if had_beats:
        beat_strength = float(np.mean(onset_env[beat_frames]))
        overall = float(np.mean(onset_env)) + 1e-6
        punch_ratio = beat_strength / overall
        punch = max(0.0, min(1.0, (punch_ratio - 3.0) / 6.0))
    else:
        # analyzer sets danceability = 0.0 outright in this branch; there is no
        # punch value to speak of. Record NaN ratio and a zero punch.
        punch_ratio = math.nan
        punch = 0.0

    return Intermediates(
        rms_mean=rms_mean,
        loudness_raw=loudness_raw,
        loudness=loudness,
        loudness_saturated=loudness_raw >= 1.0,
        brightness=brightness,
        punch_ratio=punch_ratio,
        punch=punch,
        punch_clamped_zero=(had_beats and punch <= 0.0),
        had_beats=had_beats,
    )


def intermediates_as_dict(i: Intermediates) -> dict:
    return asdict(i)
