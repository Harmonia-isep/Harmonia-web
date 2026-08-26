"""Unit tests for eval/scoring.py.

These are pure and dependency-free (no audio, no mirdata, no librosa), so they
run anywhere in well under a second. Run from the eval directory, e.g.:

    PYTHONPATH=eval python -m pytest eval/tests/test_scoring.py
"""

import pytest
from scoring import (
    Key,
    best_key_score,
    key_category,
    key_score,
    parse_key,
    parse_key_labels,
    tempo_accuracy1,
    tempo_accuracy2,
    tempo_is_octave_error,
)

# --------------------------------------------------------------------------- #
# Key parsing
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text,expected",
    [
        ("C major", Key(0, "major")),
        ("A minor", Key(9, "minor")),
        ("Db minor", Key(1, "minor")),
        ("C# major", Key(1, "major")),  # sharp/flat enharmonic collapse
        ("Gb major", Key(6, "major")),
        ("F# major", Key(6, "major")),  # same pc as Gb
        ("Cb minor", Key(11, "minor")),
        ("B# major", Key(0, "major")),
        ("c\tmin", Key(0, "minor")),  # tab separator + short mode word
        ("  Eb   maj  ", Key(3, "major")),  # extra whitespace
        ("A minor\nD minor", Key(9, "minor")),  # two keys -> take the first
    ],
)
def test_parse_key_valid(text, expected):
    assert parse_key(text) == expected


@pytest.mark.parametrize(
    "text",
    [None, "", "   ", "silence", "none", "C", "H major", "X minor", "7 major"],
)
def test_parse_key_unparseable_returns_none(text):
    assert parse_key(text) is None


# --------------------------------------------------------------------------- #
# Key scoring / categories
# --------------------------------------------------------------------------- #


def _cat(ref, est):
    return key_category(parse_key(ref), parse_key(est))


def test_key_correct():
    assert _cat("C major", "C major") == "correct"
    assert key_score(parse_key("C major"), parse_key("C major")) == (1.0, "correct")


def test_key_perfect_fifth_is_directional():
    # mir_eval credits only a fifth ABOVE (+7). We match that for comparability.
    assert _cat("C major", "G major") == "fifth"  # +7, the dominant
    assert _cat("A minor", "E minor") == "fifth"  # +7 in minor mode too
    # A fifth below (== +5, the subdominant) is NOT credited - it is "other".
    assert _cat("C major", "F major") == "other"
    # A fifth away but opposite mode is not a fifth match either.
    assert _cat("C major", "G minor") == "other"


def test_key_relative():
    assert _cat("C major", "A minor") == "relative"  # major -> relative minor
    assert _cat("A minor", "C major") == "relative"  # minor -> relative major
    assert key_score(parse_key("C major"), parse_key("A minor")) == (0.3, "relative")


def test_key_parallel():
    assert _cat("C major", "C minor") == "parallel"
    assert _cat("A minor", "A major") == "parallel"
    assert key_score(parse_key("C major"), parse_key("C minor")) == (0.2, "parallel")


def test_key_other():
    assert _cat("C major", "D major") == "other"
    assert key_score(parse_key("C major"), parse_key("D major")) == (0.0, "other")


def test_key_categories_are_mutually_exclusive_over_all_pairs():
    # For every reference key, each of the 24 candidate estimates lands in
    # exactly one category, and the tallies match the MIREX structure with a
    # directional fifth: 1 correct, 1 fifth, 1 relative, 1 parallel, 20 other.
    from collections import Counter

    for ref_pc in range(12):
        for ref_mode in ("major", "minor"):
            ref = Key(ref_pc, ref_mode)
            counts = Counter(
                key_category(ref, Key(pc, mode))
                for pc in range(12)
                for mode in ("major", "minor")
            )
            assert counts["correct"] == 1
            assert counts["fifth"] == 1
            assert counts["relative"] == 1
            assert counts["parallel"] == 1
            assert counts["other"] == 20


# --------------------------------------------------------------------------- #
# Multi-label references (best-of rule)
# --------------------------------------------------------------------------- #


def test_parse_key_labels_single():
    assert parse_key_labels("A minor") == [Key(9, "minor")]


def test_parse_key_labels_empty():
    assert parse_key_labels(None) == []
    assert parse_key_labels("silence") == []


@pytest.mark.parametrize(
    "text",
    [
        "C major | A minor",
        "C major/A minor",
        "C major, A minor",
        "C major and A minor",
        "C major\nA minor",
    ],
)
def test_parse_key_labels_multi_delimiters(text):
    assert parse_key_labels(text) == [Key(0, "major"), Key(9, "minor")]


def test_parse_key_labels_dedupes_enharmonic_repeats():
    # F# and Gb are the same pitch class; keep one label.
    assert parse_key_labels("F# major | Gb major") == [Key(6, "major")]


def test_best_key_score_takes_the_highest_weight():
    refs = [Key(0, "major"), Key(9, "minor")]  # C major or A minor acceptable
    # An A-minor estimate is exact against the second label -> 1.0, not the 0.3
    # relative it would score against C major alone.
    assert best_key_score(refs, Key(9, "minor")) == (1.0, "correct")
    # A G-major estimate is a fifth above C major (0.5) and unrelated to A minor;
    # best-of keeps the 0.5.
    assert best_key_score(refs, Key(7, "major")) == (0.5, "fifth")


def test_best_key_score_single_label_matches_key_score():
    ref = Key(2, "minor")
    for est_pc in range(12):
        for est_mode in ("major", "minor"):
            est = Key(est_pc, est_mode)
            assert best_key_score([ref], est) == key_score(ref, est)


# --------------------------------------------------------------------------- #
# Tempo scoring
# --------------------------------------------------------------------------- #


def test_accuracy1_within_and_outside_tolerance():
    assert tempo_accuracy1(120.0, 122.0) is True  # 1.7%
    assert tempo_accuracy1(120.0, 130.0) is False  # 8.3%


def test_accuracy1_boundary_is_inclusive():
    assert tempo_accuracy1(100.0, 104.0) is True  # exactly +4%
    assert tempo_accuracy1(100.0, 96.0) is True  # exactly -4%
    assert tempo_accuracy1(100.0, 104.01) is False


@pytest.mark.parametrize("est", [240.0, 60.0, 40.0, 360.0])
def test_accuracy2_forgives_octave_and_triple_errors(est):
    ref = 120.0
    assert tempo_accuracy1(ref, est) is False
    assert tempo_accuracy2(ref, est) is True
    assert tempo_is_octave_error(ref, est) is True


def test_accuracy2_exact_match_is_not_an_octave_error():
    assert tempo_accuracy2(120.0, 121.0) is True
    assert tempo_is_octave_error(120.0, 121.0) is False


def test_accuracy2_true_miss():
    # 150 is not within 4% of 120, 60, 40, 240 or 360.
    assert tempo_accuracy2(120.0, 150.0) is False
    assert tempo_is_octave_error(120.0, 150.0) is False


def test_tempo_guards_nonpositive_reference():
    assert tempo_accuracy1(0.0, 120.0) is False
    assert tempo_accuracy2(0.0, 120.0) is False


# --------------------------------------------------------------------------- #
# Optional cross-check against mir_eval, when it is installed.
# --------------------------------------------------------------------------- #


def test_matches_mir_eval_weighted_score_when_available():
    mir_eval_key = pytest.importorskip("mir_eval.key")
    names = {0: "C", 1: "C#", 2: "D", 3: "D#", 4: "E", 5: "F",
             6: "F#", 7: "G", 8: "G#", 9: "A", 10: "A#", 11: "B"}
    for ref_pc in range(12):
        for ref_mode in ("major", "minor"):
            for est_pc in range(12):
                for est_mode in ("major", "minor"):
                    ref = Key(ref_pc, ref_mode)
                    est = Key(est_pc, est_mode)
                    ours, _ = key_score(ref, est)
                    theirs = mir_eval_key.weighted_score(
                        f"{names[ref_pc]} {ref_mode}",
                        f"{names[est_pc]} {est_mode}",
                    )
                    assert ours == theirs, (ref, est, ours, theirs)
