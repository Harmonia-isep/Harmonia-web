import librosa
import numpy as np

from backend.audio.key_profiles import estimate_key

KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def analyze_audio(file_path: str) -> dict:
    try:
        # Load mono at 22050 Hz, capped at 45 seconds. Mono + lower sample
        # rate + shorter window keeps memory low enough for the free-tier
        # server. This is plenty of audio to measure BPM, key, energy etc.
        y, sr = librosa.load(file_path, sr=22050, mono=True, duration=45)

        # Compute the onset envelope ONCE - both BPM and danceability use it.
        # Reusing it avoids running the expensive beat tracker twice.
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
        bpm = round(float(tempo[0]))

        # Key detection. We use chroma_stft (FFT-based) instead of chroma_cqt:
        # the CQT is far more memory-hungry, and the STFT version gives
        # essentially the same key result at a fraction of the RAM.
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        chroma_mean = chroma.mean(axis=1)

        # Correlate the mean chroma against all 24 rotations (12 tonics x
        # major/minor) of a published key profile and take the best. This
        # replaces the old argmax tonic plus one-pitch-class binary templates,
        # whose near-coin-flip mode discrimination dominated the Phase 4 key
        # errors. Profile is selectable (default Krumhansl-Kessler); see
        # backend/audio/key_profiles.py.
        estimate = estimate_key(chroma_mean)
        key = estimate.key
        scale = estimate.scale

        # Energy - blend loudness (RMS) with brightness (spectral centroid)
        rms_mean = float(np.mean(librosa.feature.rms(y=y)))
        loudness = min(1.0, rms_mean / 0.3)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        brightness = min(1.0, float(np.mean(centroid)) / 4000.0)
        energy = float(round(0.6 * loudness + 0.4 * brightness, 4))

        # Danceability - blend beat steadiness with pulse strength (punch),
        # reusing the onset envelope and beats we already computed above.
        if len(beat_frames) > 2:
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)
            intervals = np.diff(beat_times)

            cv = np.std(intervals) / (np.mean(intervals) + 1e-6)
            steadiness = max(0.0, min(1.0, 1.0 - cv))

            beat_strength = np.mean(onset_env[beat_frames])
            overall = np.mean(onset_env) + 1e-6
            punch = beat_strength / overall
            punch = max(0.0, min(1.0, (punch - 3.0) / 6.0))

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
            "danceability": danceability
        }
    except Exception as e:
        print(f"Analysis error: {e}")
        raise
