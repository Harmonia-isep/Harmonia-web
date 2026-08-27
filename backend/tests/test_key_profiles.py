"""Unit tests for backend/audio/key_profiles.py.

Pure and fast: no audio, just the profile vectors and the correlation logic.
"""

import numpy as np
import pytest

from backend.audio.key_profiles import (
    DEFAULT_PROFILE,
    KEYS,
    PROFILES,
    estimate_key,
    resolve_profile,
)


def test_all_profiles_are_two_twelve_element_vectors():
    assert set(PROFILES) == {"ks", "temperley", "edma"}
    for name, (major, minor) in PROFILES.items():
        assert len(major) == 12, name
        assert len(minor) == 12, name


def test_resolve_profile_default_env_and_explicit(monkeypatch):
    monkeypatch.delenv("HARMONIA_KEY_PROFILE", raising=False)
    assert resolve_profile() == DEFAULT_PROFILE == "edma"
    assert resolve_profile("edma") == "edma"
    assert resolve_profile("TEMPERLEY") == "temperley"  # case-insensitive
    monkeypatch.setenv("HARMONIA_KEY_PROFILE", "edma")
    assert resolve_profile() == "edma"  # env picked up
    assert resolve_profile("ks") == "ks"  # explicit arg still wins


def test_resolve_profile_unknown_raises():
    with pytest.raises(ValueError):
        resolve_profile("not-a-profile")


@pytest.mark.parametrize("profile", ["ks", "temperley", "edma"])
@pytest.mark.parametrize("tonic", range(12))
def test_estimate_recovers_planted_major_key(profile, tonic):
    # Feed the profile's own major vector, rotated to `tonic`, as the chroma.
    # The best of 24 correlations must be that exact major key.
    major = np.asarray(PROFILES[profile][0], dtype=float)
    chroma = np.roll(major, tonic)
    est = estimate_key(chroma, profile=profile)
    assert est.key == KEYS[tonic]
    assert est.scale == "major"
    assert est.confidence == pytest.approx(1.0, abs=1e-9)
    assert est.profile == profile


@pytest.mark.parametrize("profile", ["ks", "temperley", "edma"])
def test_estimate_recovers_planted_minor_key(profile):
    minor = np.asarray(PROFILES[profile][1], dtype=float)
    chroma = np.roll(minor, 9)  # A minor
    est = estimate_key(chroma, profile=profile)
    assert est.key == "A"
    assert est.scale == "minor"


def test_runner_up_is_populated_and_not_above_winner():
    chroma = np.asarray(PROFILES["ks"][0], dtype=float)  # C major
    est = estimate_key(chroma, profile="ks")
    assert est.runner_up_key in KEYS
    assert est.runner_up_scale in ("major", "minor")
    # The runner-up cannot be the identical (key, scale) as the winner.
    assert (est.runner_up_key, est.runner_up_scale) != (est.key, est.scale)
    assert est.runner_up_confidence <= est.confidence


def test_estimate_respects_env_selection(monkeypatch):
    monkeypatch.setenv("HARMONIA_KEY_PROFILE", "edma")
    chroma = np.asarray(PROFILES["edma"][0], dtype=float)
    est = estimate_key(chroma)  # no explicit profile -> uses env
    assert est.profile == "edma"
