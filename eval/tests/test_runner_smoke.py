"""End-to-end smoke test of the runner on synthetic audio.

Proves the wiring - analyze_audio -> scoring -> aggregation -> audit -> report -
without any dataset download or mirdata. It does NOT assert the analyzer gets
key/tempo *right* on these toy signals (that is the baseline's job on real
data); it asserts the harness runs, aggregates coherently, and that the
saturation audit fires correctly on controlled inputs.

Run:  PYTHONPATH=eval python -m pytest eval/tests/test_runner_smoke.py
"""

import audit
import numpy as np
import pytest
import run_eval
import soundfile as sf

SR = 22050


def _make_beat_tone(path, bpm, freq, dur=8.0, amp=0.3):
    """A tonal signal with a click train at `bpm`, peak-normalised to 0.9."""
    t = np.arange(int(dur * SR)) / SR
    tone = amp * np.sin(2 * np.pi * freq * t)
    click = np.zeros_like(t)
    period = 60.0 / bpm
    idx = (np.arange(0, dur, period) * SR).astype(int)
    click[idx[idx < len(click)]] = 1.0
    y = tone + click
    y = 0.9 * y / np.max(np.abs(y))
    sf.write(path, y.astype(np.float32), SR)
    return str(path)


def _make_pure_tone(path, freq=220.0, dur=6.0, amp=0.3):
    """A pure sine at a fixed amplitude (RMS = amp / sqrt(2)); no normalisation."""
    t = np.arange(int(dur * SR)) / SR
    y = amp * np.sin(2 * np.pi * freq * t)
    sf.write(path, y.astype(np.float32), SR)
    return str(path)


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    d = tmp_path_factory.mktemp("clips")
    return [
        _make_beat_tone(d / "a.wav", bpm=120, freq=220.0),
        _make_beat_tone(d / "b.wav", bpm=90, freq=261.63),
        _make_beat_tone(d / "c.wav", bpm=140, freq=329.63),
    ]


def test_evaluate_key_aggregates_coherently(clips):
    pairs = [(clips[0], "A minor"), (clips[1], "C major"), (clips[2], "E minor")]
    rep = run_eval.evaluate_key(pairs)

    assert rep["n"] == 3
    assert 0.0 <= rep["weighted_score"] <= 1.0
    assert 0.0 <= rep["exact_match_rate"] <= 1.0
    # Every scored track lands in exactly one category.
    assert sum(rep["confusion"].values()) == rep["n"]
    assert rep["exact_matches"] == rep["confusion"]["correct"]
    assert len(rep["energy"]) == 3 and len(rep["danceability"]) == 3


def test_evaluate_key_counts_unparseable_reference(clips):
    pairs = [(clips[0], "A minor"), (clips[1], "silence")]
    rep = run_eval.evaluate_key(pairs)
    assert rep["n"] == 1  # the "silence" reference is skipped, not scored
    assert rep["n_unparseable_ref"] == 1


def test_evaluate_tempo_aggregates_coherently(clips):
    pairs = [(clips[0], 120.0), (clips[1], 90.0), (clips[2], 140.0)]
    rep = run_eval.evaluate_tempo(pairs)

    assert rep["n"] == 3
    assert 0.0 <= rep["accuracy1"] <= 1.0
    assert 0.0 <= rep["accuracy2"] <= 1.0
    # Accuracy2 is a superset of Accuracy1; octave errors are the difference.
    assert rep["accuracy2_hits"] >= rep["accuracy1_hits"]
    assert rep["octave_error_hits"] == rep["accuracy2_hits"] - rep["accuracy1_hits"]


def test_tempo_missing_reference_is_skipped(clips):
    rep = run_eval.evaluate_tempo([(clips[0], 0.0), (clips[1], 90.0)])
    assert rep["n"] == 1
    assert rep["n_missing_ref"] == 1


def test_feature_histograms_and_report_render(clips):
    pairs = [(c, 120.0) for c in clips]
    tempo = run_eval.evaluate_tempo(pairs)
    feats = run_eval.feature_histograms(tempo["energy"], tempo["danceability"])
    assert feats["energy"]["n"] == 3
    # Bin counts must total the sample size.
    assert sum(b["count"] for b in feats["energy"]["bins"]) == 3

    report = {"tempo": tempo, "features": feats,
              "audit": run_eval.audit_features(clips, sample=None)}
    text = run_eval.render_report(report)
    assert "TEMPO" in text and "FEATURE DISTRIBUTIONS" in text


def test_saturation_audit_fires_on_loud_not_quiet(tmp_path):
    # loudness = min(1.0, rms/0.3); saturates when rms >= 0.3.
    # A 0.7-amplitude sine has rms ~0.495 (saturates); 0.05 has rms ~0.035 (not).
    loud = _make_pure_tone(tmp_path / "loud.wav", amp=0.7)
    quiet = _make_pure_tone(tmp_path / "quiet.wav", amp=0.05)

    assert audit.audit_intermediates(loud).loudness_saturated is True
    assert audit.audit_intermediates(quiet).loudness_saturated is False

    rep = run_eval.audit_features([loud, quiet], sample=None)
    assert rep["n_audited"] == 2
    assert rep["loudness_saturated_count"] == 1
    assert rep["loudness_saturation_rate"] == 0.5
