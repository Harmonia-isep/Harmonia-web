# Unit tests: pure logic, no database, no network.
# Covers the Camelot wheel mapping, the three harmonic-compatibility rules,
# and the DSP descriptor math on a cheap synthetic tone.

import librosa
import numpy as np

from backend.api.analysis import camelot_compatible, to_camelot
from backend.audio.analyzer import (
    _CENTROID_P2,
    _CENTROID_P98,
    _PUNCH_RATIO_P2,
    _PUNCH_RATIO_P98,
    _RMS_P2,
    _RMS_P98,
    _STEADINESS_P2,
    _STEADINESS_P98,
    _scale01,
    analyze_audio,
)


class TestCamelotMapping:
    def test_minor_key_maps_to_A_code(self):
        assert to_camelot("A", "minor") == "8A"
        assert to_camelot("G", "minor") == "6A"

    def test_major_key_maps_to_B_code(self):
        assert to_camelot("C", "major") == "8B"
        assert to_camelot("B", "major") == "1B"

    def test_flat_spelling_supported(self):
        assert to_camelot("Ab", "minor") == "1A"
        assert to_camelot("Eb", "major") == "5B"

    def test_missing_key_or_scale_returns_none(self):
        assert to_camelot(None, "minor") is None
        assert to_camelot("C", None) is None


class TestCamelotCompatibility:
    def test_rule1_same_code(self):
        assert camelot_compatible("8A", "8A") is True

    def test_rule2_relative_major_minor(self):
        # same number, opposite letter
        assert camelot_compatible("8A", "8B") is True
        assert camelot_compatible("5B", "5A") is True

    def test_rule3_wheel_adjacency(self):
        assert camelot_compatible("8A", "7A") is True
        assert camelot_compatible("8A", "9A") is True

    def test_rule3_wrap_12_to_1(self):
        assert camelot_compatible("12A", "1A") is True
        assert camelot_compatible("1B", "12B") is True

    def test_incompatible_pairs(self):
        assert camelot_compatible("8A", "10A") is False   # two steps apart
        assert camelot_compatible("8A", "3B") is False     # unrelated

    def test_missing_code_is_incompatible(self):
        assert camelot_compatible("8A", None) is False
        assert camelot_compatible(None, None) is False


def _reproduce_descriptors(path):
    """Recompute energy and danceability with the exact same steps as
    analyzer.analyze_audio, so the test pins the published weightings
    (energy = 0.6*loudness + 0.4*brightness, danceability = 0.8*punch + 0.2*steadiness).
    Component scaling uses the analyzer's own corpus-derived p2/p98 constants, so
    this tracks the formula structure rather than hardcoding the constants."""
    y, sr = librosa.load(path, sr=22050, mono=True)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    _, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)

    rms_mean = float(np.mean(librosa.feature.rms(y=y)))
    loudness = _scale01(rms_mean, _RMS_P2, _RMS_P98)
    centroid_mean = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    brightness = _scale01(centroid_mean, _CENTROID_P2, _CENTROID_P98)
    energy = float(round(0.6 * loudness + 0.4 * brightness, 4))

    if len(beat_frames) > 2:
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        intervals = np.diff(beat_times)
        cv = np.std(intervals) / (np.mean(intervals) + 1e-6)
        steadiness = _scale01(1.0 - cv, _STEADINESS_P2, _STEADINESS_P98)
        beat_strength = np.mean(onset_env[beat_frames])
        overall = np.mean(onset_env) + 1e-6
        punch = _scale01(beat_strength / overall, _PUNCH_RATIO_P2, _PUNCH_RATIO_P98)
        danceability = float(round(0.8 * punch + 0.2 * steadiness, 4))
    else:
        danceability = 0.0
    return energy, danceability


class TestDescriptorMath:
    def test_key_detection_on_concert_A(self, make_tone):
        assert analyze_audio(make_tone(freq=440.0))["key"] == "A"

    def test_key_detection_on_middle_C(self, make_tone):
        assert analyze_audio(make_tone(freq=261.63))["key"] == "C"

    def test_energy_weighting_is_0_6_loudness_0_4_brightness(self, make_tone):
        path = make_tone(freq=261.63)
        expected_energy, _ = _reproduce_descriptors(path)
        assert analyze_audio(path)["energy"] == expected_energy

    def test_danceability_weighting_is_0_8_punch_0_2_steadiness(self, make_tone):
        path = make_tone(freq=261.63)
        _, expected_dance = _reproduce_descriptors(path)
        assert analyze_audio(path)["danceability"] == expected_dance

    def test_descriptors_are_bounded_and_well_formed(self, make_tone):
        r = analyze_audio(make_tone(freq=329.63))
        assert 0.0 <= r["energy"] <= 1.0
        assert 0.0 <= r["danceability"] <= 1.0
        assert r["scale"] in ("major", "minor")
        assert isinstance(r["bpm"], (int, float))
