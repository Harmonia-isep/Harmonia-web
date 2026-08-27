"""Key-profile templates and 24-rotation correlation for key detection.

This replaces the analyzer's original approach (argmax of the mean chroma to
pick the tonic, then a one-pitch-class binary major/minor template to pick the
mode) with proper template correlation: for a mean chroma vector, correlate
against all 12 tonic rotations of both the major and the minor profile - 24
candidates - and take the best. Correlation is Pearson, which is invariant to
the scaling of a profile, so profiles published at different scales are
interchangeable here.

Each profile is a (major, minor) pair of 12-element vectors, tonic first (C=0).
The numeric constants are the values published in the cited works; the
correlation is implemented here independently (no third-party key-detection
code was copied).

Profiles
--------
- "ks" - Krumhansl-Kessler probe-tone key profiles (Krumhansl & Kessler, 1982),
  as tabulated in Krumhansl, C. L. (1990). Cognitive Foundations of Musical
  Pitch. Oxford University Press. This is the profile pair used by the classic
  Krumhansl-Schmuckler key-finding algorithm.
- "temperley" - the modified profiles from Temperley, D. (1999). "What's key for
  key? The Krumhansl-Schmuckler key-finding algorithm reconsidered." Music
  Perception 17(1): 65-100; also Temperley, D. (2001). The Cognition of Basic
  Musical Structures. MIT Press.
- "edma" - the automatically-derived electronic-dance-music profiles from
  Faraldo, A., Gomez, E., Jorda, S., & Herrera, P. (2016). "Key Estimation in
  Electronic Dance Music." In ECIR 2016, LNCS 9626, pp. 335-347. The values are
  the normalized ECIR-2016 EDMA profiles.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

# Pitch-class names, index 0 = C. Mirrors analyzer.KEYS.
KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# (major, minor) profile pairs, tonic at index 0.
PROFILES: dict[str, tuple[list[float], list[float]]] = {
    # Krumhansl & Kessler (1982), tabulated in Krumhansl (1990).
    "ks": (
        [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88],
        [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17],
    ),
    # Temperley (1999), Music Perception 17(1); also Temperley (2001).
    "temperley": (
        [5.0, 2.0, 3.5, 2.0, 4.5, 4.0, 2.0, 4.5, 2.0, 3.5, 1.5, 4.0],
        [5.0, 2.0, 3.5, 4.5, 2.0, 4.0, 2.0, 4.5, 3.5, 2.0, 1.5, 4.0],
    ),
    # Faraldo et al. (2016), ECIR - normalized EDMA profiles.
    "edma": (
        [0.16519551, 0.04749026, 0.08293076, 0.06687112, 0.09994645, 0.09274123,
         0.05294487, 0.13159476, 0.05218986, 0.07443653, 0.06940723, 0.06425150],
        [0.17235348, 0.05336489, 0.07610090, 0.10043649, 0.05621498, 0.08527853,
         0.04979150, 0.13451001, 0.07458916, 0.05003023, 0.09187879, 0.05545106],
    ),
}

# EDMA is the default: on the GiantSteps+ EDM corpus it beat KS and Temperley
# (see eval/baseline.md). It is corpus-matched (EDM profile, EDM corpus); KS and
# Temperley stay selectable so that ranking can be retested on other genres.
DEFAULT_PROFILE = "edma"
_ENV_VAR = "HARMONIA_KEY_PROFILE"


def resolve_profile(profile: str | None = None) -> str:
    """Resolve the profile name: explicit arg, else the env var, else the default."""
    name = (profile or os.environ.get(_ENV_VAR) or DEFAULT_PROFILE).lower()
    if name not in PROFILES:
        msg = f"unknown key profile {name!r}; choose from {sorted(PROFILES)}"
        raise ValueError(msg)
    return name


@dataclass(frozen=True)
class KeyEstimate:
    """A key estimate: winner, its confidence, and the runner-up, per profile."""

    key: str            # tonic name, e.g. "A"
    scale: str          # "major" or "minor"
    confidence: float   # Pearson r of the winning rotated template
    runner_up_key: str
    runner_up_scale: str
    runner_up_confidence: float
    profile: str


def estimate_key(chroma_mean, profile: str | None = None) -> KeyEstimate:
    """Detect key by correlating the mean chroma against all 24 profile rotations.

    Returns the best-correlating (tonic, mode) as the estimate, plus the
    second-best as the runner-up and the winning Pearson r as a confidence. The
    correlation is scale-invariant, so profile normalisation does not matter.
    """
    name = resolve_profile(profile)
    major = np.asarray(PROFILES[name][0], dtype=float)
    minor = np.asarray(PROFILES[name][1], dtype=float)
    cm = np.asarray(chroma_mean, dtype=float)

    scored: list[tuple[float, int, str]] = []
    for tonic in range(12):
        scored.append((float(np.corrcoef(cm, np.roll(major, tonic))[0, 1]), tonic, "major"))
        scored.append((float(np.corrcoef(cm, np.roll(minor, tonic))[0, 1]), tonic, "minor"))

    # A flat chroma yields NaN correlations; sort those to the bottom.
    scored.sort(key=lambda s: np.nan_to_num(s[0], nan=-np.inf), reverse=True)
    best, runner = scored[0], scored[1]

    return KeyEstimate(
        key=KEYS[best[1]],
        scale=best[2],
        confidence=best[0],
        runner_up_key=KEYS[runner[1]],
        runner_up_scale=runner[2],
        runner_up_confidence=runner[0],
        profile=name,
    )
