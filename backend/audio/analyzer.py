import librosa
import numpy as np

KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def analyze_audio(file_path: str) -> dict:
    try:
        y, sr = librosa.load(file_path, sr=None, duration=60)

        # BPM
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(round(tempo, 2))

        # Key detection using chroma
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_mean = chroma.mean(axis=1)
        key_index = int(np.argmax(chroma_mean))
        key = KEYS[key_index]

        # Major vs minor (simple heuristic)
        major_profile = np.array([1,0,1,0,1,1,0,1,0,1,0,1], dtype=float)
        minor_profile = np.array([1,0,1,1,0,1,0,1,1,0,1,0], dtype=float)
        major_corr = np.corrcoef(chroma_mean, np.roll(major_profile, key_index))[0,1]
        minor_corr = np.corrcoef(chroma_mean, np.roll(minor_profile, key_index))[0,1]
        scale = "major" if major_corr > minor_corr else "minor"

        # Energy (RMS)
        rms = librosa.feature.rms(y=y)
        energy = float(round(float(np.mean(rms)), 4))

        # Danceability proxy (beat strength consistency)
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        danceability = float(round(float(np.std(onset_env) / (np.mean(onset_env) + 1e-6)), 4))

        return {
            "bpm": bpm,
            "key": key,
            "scale": scale,
            "energy": energy,
            "danceability": danceability
        }
    except Exception as e:
        return {
            "bpm": 0.0,
            "key": "Unknown",
            "scale": "Unknown",
            "energy": 0.0,
            "danceability": 0.0
        }
