import librosa
import numpy as np

from backend.audio.key_profiles import estimate_key

KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Energy and danceability are heuristics with NO ground truth (unlike key, which
# is benchmarked against GiantSteps+). The constants below are the 2nd and 98th
# percentiles of each intermediate MEASURED over the GiantSteps+ corpus (see
# eval/baseline.md), NOT physical thresholds. They map each intermediate onto
# [0, 1] so the descriptors spread across their full range on this corpus.
# Success here is distributional spread, not accuracy. These are corpus-derived
# from EDM and may not transfer; recalibrate if the target corpus changes.
_RMS_P2, _RMS_P98 = 0.131, 0.386                   # mean RMS energy
_CENTROID_P2, _CENTROID_P98 = 1353.0, 3676.0       # mean spectral centroid (Hz)
_PUNCH_RATIO_P2, _PUNCH_RATIO_P98 = 2.133, 5.959   # beat / mean-onset strength ratio
_STEADINESS_P2, _STEADINESS_P98 = 0.929, 0.984     # 1 - CV of beat intervals


def _scale01(value: float, lo: float, hi: float) -> float:
    """Map a value from its corpus range [lo, hi] onto [0, 1], clipped."""
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def analyze_audio(file_path: str) -> dict:
    try:
        # Load the full track, mono at 22050 Hz. Phase 6 step 2 dropped the old
        # 45-second cap: analyzing only the intro hurt key accuracy, and the
        # free-tier memory ceiling the cap protected no longer applies now that
        # this runs locally.
        y, sr = librosa.load(file_path, sr=22050, mono=True)

        # Compute the onset envelope ONCE - both BPM and danceability use it.
        # Reusing it avoids running the expensive beat tracker twice.
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
        bpm = round(float(tempo[0]))
        # The beat grid (beat times in seconds). Computed once here and persisted
        # for the beat overlay (US04); previously it was derived only inside the
        # danceability branch and then discarded.
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)

        # Key detection uses chroma_stft (FFT-based), not chroma_cqt. chroma_cqt
        # was measured (eval/baseline.md) and was worse here: -0.094 weighted on
        # a like-for-like 150-track slice with the EDMA profile, at 1.3x the cost.
        # On this corpus STFT is both cheaper and more accurate, not merely a
        # RAM-saving approximation.
        # tuning=None (librosa's default) makes chroma_stft auto-estimate and
        # apply tuning correction internally (see librosa feature/spectral.py).
        # This is our tuning correction; do NOT remove it or hardcode tuning=0.0.
        # Ablation (eval/baseline.md): disabling it costs ~0.007 weighted and 7
        # tracks on GiantSteps+ (~24% of the corpus sits >10 cents off A440).
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        chroma_mean = chroma.mean(axis=1)

        # Correlate the mean chroma against all 24 rotations (12 tonics x
        # major/minor) of a published key profile and take the best. This
        # replaces the old argmax tonic plus one-pitch-class binary templates,
        # whose near-coin-flip mode discrimination dominated the Phase 4 key
        # errors. Profile is selectable (default Faraldo EDMA); see
        # backend/audio/key_profiles.py.
        estimate = estimate_key(chroma_mean)
        key = estimate.key
        scale = estimate.scale

        # Energy - blend loudness (RMS) with brightness (spectral centroid), each
        # mapped from its corpus p2..p98 range onto [0, 1]. Heuristic, no ground
        # truth; constants recalibrated for spread (see eval/baseline.md).
        rms_mean = float(np.mean(librosa.feature.rms(y=y)))
        loudness = _scale01(rms_mean, _RMS_P2, _RMS_P98)
        centroid_mean = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
        brightness = _scale01(centroid_mean, _CENTROID_P2, _CENTROID_P98)
        energy = float(round(0.6 * loudness + 0.4 * brightness, 4))

        # Danceability - blend pulse strength (punch) with beat steadiness, each
        # mapped from its corpus p2..p98 range onto [0, 1]. Heuristic, no ground
        # truth. Steadiness barely varies on EDM (p2..p98 = 0.929..0.984, see
        # baseline.md), so its 0.2 weight is close to a constant offset here; the
        # weighting is left unchanged on purpose (that is a separate experiment).
        if len(beat_frames) > 2:
            intervals = np.diff(beat_times)

            cv = np.std(intervals) / (np.mean(intervals) + 1e-6)
            steadiness = _scale01(1.0 - cv, _STEADINESS_P2, _STEADINESS_P98)

            beat_strength = np.mean(onset_env[beat_frames])
            overall = np.mean(onset_env) + 1e-6
            punch = _scale01(beat_strength / overall, _PUNCH_RATIO_P2, _PUNCH_RATIO_P98)

            danceability = float(round(0.8 * punch + 0.2 * steadiness, 4))
        else:
            danceability = 0.0

        # free the big array as soon as we're done with it
        del y

        return {
            "bpm": bpm,
            "key": key,
            "scale": scale,
            "energy": energy,
            "danceability": danceability,
            "beats": [round(float(t), 3) for t in beat_times],
        }
    except Exception as e:
        print(f"Analysis error: {e}")
        raise
