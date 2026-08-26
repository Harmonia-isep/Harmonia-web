"""Scoring functions for the Harmonia evaluation harness.

Pure functions with no third-party dependencies, so they are fast and trivial
to unit test in isolation. The runner (run_eval.py) feeds analyzer output and
reference annotations through these; nothing here imports the analyzer, mirdata,
librosa, or numpy.

Key scoring follows the MIREX weighted convention:
    correct           1.0
    perfect fifth     0.5
    relative maj/min  0.3
    parallel maj/min  0.2
    otherwise         0.0

We also return a category label per comparison so the runner can report the raw
exact-match rate and a confusion breakdown (how many fifths / relatives /
parallels / others) alongside the single weighted number.

Tempo scoring follows the standard Accuracy1 / Accuracy2 convention:
    Accuracy1  estimate within TOL (default 4%) of the reference
    Accuracy2  Accuracy1, or within TOL of the reference scaled by a common
               metrical factor (1/3, 1/2, 2, 3) - i.e. octave/triple errors
"""

from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# Key scoring
# --------------------------------------------------------------------------- #

# Note name -> pitch class (0..11), C = 0. Covers naturals, sharps and flats,
# including the enharmonics that turn up in key annotations (Cb, B#, E#, Fb).
_NOTE_TO_PC = {
    "C": 0, "B#": 0,
    "C#": 1, "Db": 1,
    "D": 2,
    "D#": 3, "Eb": 3,
    "E": 4, "Fb": 4,
    "F": 5, "E#": 5,
    "F#": 6, "Gb": 6,
    "G": 7,
    "G#": 8, "Ab": 8,
    "A": 9,
    "A#": 10, "Bb": 10,
    "B": 11, "Cb": 11,
}

# Mode synonyms seen across analyzer output and dataset annotations.
_MAJOR_WORDS = {"major", "maj", "M"}
_MINOR_WORDS = {"minor", "min", "m"}

# MIREX category -> weight. "other" (and unresolved comparisons) score 0.0.
KEY_WEIGHTS = {
    "correct": 1.0,
    "fifth": 0.5,
    "relative": 0.3,
    "parallel": 0.2,
    "other": 0.0,
}
KEY_CATEGORIES = ("correct", "fifth", "relative", "parallel", "other")


@dataclass(frozen=True)
class Key:
    """A parsed key: pitch class 0..11 and mode 'major' or 'minor'."""

    pc: int
    mode: str


def parse_key(text: str | None) -> Key | None:
    """Parse a key string into a Key, or None if it cannot be understood.

    Accepts the analyzer's own output (e.g. tonic 'A' + we pass 'A minor') and
    dataset annotations in the common '<tonic> <mode>' / '<tonic>\\t<mode>'
    forms, with sharps or flats. Returns None for empty, 'silence', 'none', or
    otherwise unparseable values so the runner can count and exclude them rather
    than silently scoring them as wrong.
    """
    if text is None:
        return None
    raw = text.strip()
    if not raw:
        return None

    # Take the first line and split on whitespace / tab. A handful of GiantSteps
    # files list two keys; scoring the first is the documented convention.
    first = raw.splitlines()[0].strip()
    # Normalise common separators (tab already covered by split()).
    parts = first.replace("\t", " ").split()
    if not parts:
        return None

    tonic_raw = parts[0]
    mode_raw = parts[1] if len(parts) > 1 else ""

    # Sentinels that mean "no key".
    if tonic_raw.lower() in {"silence", "none", "n/a", "-", "unknown"}:
        return None

    tonic = _normalize_tonic(tonic_raw)
    if tonic is None or tonic not in _NOTE_TO_PC:
        return None

    mode = _normalize_mode(mode_raw)
    if mode is None:
        return None

    return Key(pc=_NOTE_TO_PC[tonic], mode=mode)


def _normalize_tonic(token: str) -> str | None:
    """Title-case the note letter, keep accidentals as-is (#, b)."""
    token = token.strip()
    if not token:
        return None
    letter = token[0].upper()
    accidentals = token[1:]
    # Normalise unicode/style accidentals to ASCII # and b.
    accidentals = (
        accidentals.replace("♯", "#")  # ♯
        .replace("♭", "b")  # ♭
        .replace("S", "#")
    )
    return letter + accidentals


def _normalize_mode(token: str) -> str | None:
    token = token.strip()
    if token in _MAJOR_WORDS or token.lower() in {w.lower() for w in _MAJOR_WORDS}:
        return "major"
    if token in _MINOR_WORDS or token.lower() in {w.lower() for w in _MINOR_WORDS}:
        return "minor"
    # No mode given -> ambiguous; refuse rather than guess.
    return None


def key_category(reference: Key, estimate: Key) -> str:
    """Classify an estimate against a reference into a MIREX category.

    Categories are mutually exclusive by construction: 'correct' (same pc, same
    mode), 'fifth' (same mode, estimate a perfect fifth above the reference),
    'relative' (major<->minor a minor third apart), 'parallel' (same pc,
    opposite mode), else 'other'.
    """
    if reference.pc == estimate.pc and reference.mode == estimate.mode:
        return "correct"

    # Perfect fifth: same mode, estimate a perfect fifth ABOVE the reference
    # (+7 semitones). This is directional on purpose - it matches mir_eval's
    # weighted_score ("estimated key is a perfect fifth above reference key"),
    # so the numbers stay comparable to the standard MIREX tooling. The
    # fifth-below / subdominant confusion (+5) scores as "other", as it does
    # there.
    if estimate.mode == reference.mode and (estimate.pc - reference.pc) % 12 == 7:
        return "fifth"

    if estimate.mode != reference.mode:
        # Relative: C major <-> A minor. The minor tonic sits 3 semitones below
        # the major tonic (== +9), the major tonic 3 semitones above the minor.
        if reference.mode == "major" and estimate.pc == (reference.pc + 9) % 12:
            return "relative"
        if reference.mode == "minor" and estimate.pc == (reference.pc + 3) % 12:
            return "relative"
        # Parallel: same tonic, opposite mode (C major <-> C minor).
        if estimate.pc == reference.pc:
            return "parallel"

    return "other"


def key_score(reference: Key, estimate: Key) -> tuple[float, str]:
    """Return (MIREX weight, category) for an estimate against a reference."""
    category = key_category(reference, estimate)
    return KEY_WEIGHTS[category], category


# --------------------------------------------------------------------------- #
# Tempo scoring
# --------------------------------------------------------------------------- #

# Metrical factors that Accuracy2 forgives (double/half/triple/third tempo).
_OCTAVE_FACTORS = (1.0 / 3.0, 1.0 / 2.0, 2.0, 3.0)


def tempo_accuracy1(reference: float, estimate: float, tol: float = 0.04) -> bool:
    """True if the estimate is within `tol` (relative) of the reference."""
    if reference <= 0:
        return False
    return abs(estimate - reference) <= tol * reference


def tempo_accuracy2(reference: float, estimate: float, tol: float = 0.04) -> bool:
    """Accuracy1, or within `tol` of the reference scaled by a metrical factor."""
    if reference <= 0:
        return False
    if tempo_accuracy1(reference, estimate, tol):
        return True
    for factor in _OCTAVE_FACTORS:
        target = factor * reference
        if abs(estimate - target) <= tol * target:
            return True
    return False


def tempo_is_octave_error(reference: float, estimate: float, tol: float = 0.04) -> bool:
    """True when Accuracy2 accepts the estimate only via a metrical factor.

    That is: it fails Accuracy1 but passes Accuracy2 - the classic half/double
    (or third/triple) tempo confusion. Used to report how many Accuracy2 hits
    were octave errors rather than exact matches.
    """
    return tempo_accuracy2(reference, estimate, tol) and not tempo_accuracy1(
        reference, estimate, tol
    )
