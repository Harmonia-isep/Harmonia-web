import librosa
import numpy as np

KEYS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def analyze_audio(file_path: str) -> dict:
    try:
        # load mono at 22050 Hz (not the full 44100) and cap at 60s.
        # this roughly halves the memory librosa needs, which keeps us
        # under the hosting RAM limit. 22050 Hz is plenty for BPM, key,
        # energy and spectrum analysis - the musical info lives well below
        # the 11 kHz ceiling that sample rate captures.
        y, sr = librosa.load(file_path, sr=22050, mono=True, duration=60)

        # BPM
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = round(float(tempo[0]))

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

        # Energy - how intense/energetic the track feels.
        # We combine two things: loudness (RMS) and brightness (spectral
        # centroid - energetic songs have more high-frequency content).
        rms = librosa.feature.rms(y=y)
        rms_mean = float(np.mean(rms))

        # loudness part: RMS typically sits around 0.05-0.3, so scale it up
        # into a 0-1 range (0.3 RMS and above counts as fully loud)
        loudness = min(1.0, rms_mean / 0.3)

        # brightness part: spectral centroid is the "center of mass" of the
        # frequencies. Higher = brighter = more energetic. Normalize against
        # a typical ceiling of 4000 Hz.
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        brightness = min(1.0, float(np.mean(centroid)) / 4000.0)

        # blend them - loudness matters a bit more than brightness
        energy = float(round(0.6 * loudness + 0.4 * brightness, 4))

        # Danceability - combines two things that make a track danceable:
        #   1. a steady beat (consistent spacing between beats)
        #   2. a strong, punchy rhythm (how much the beats stand out)
        # Using only steadiness made every produced track score ~99%, since
        # they all have regular beats. Adding pulse strength spreads the
        # scores out so a driving groove scores higher than a soft one.
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        _, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)

        if len(beat_frames) > 2:
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)
            intervals = np.diff(beat_times)

            # steadiness: low variation in beat spacing = steady (0-1)
            cv = np.std(intervals) / (np.mean(intervals) + 1e-6)
            steadiness = max(0.0, min(1.0, 1.0 - cv))

            # pulse strength: how strong the beats are relative to the
            # overall signal. We compare the onset strength AT the beats
            # to the average onset strength everywhere.
            beat_strength = np.mean(onset_env[beat_frames])
            overall = np.mean(onset_env) + 1e-6
            punch = beat_strength / overall
            # punch realistically ranges ~3 (soft) to ~9 (very punchy) for
            # music, so map that window into 0-1 to get real separation.
            punch = max(0.0, min(1.0, (punch - 3.0) / 6.0))

            # punch carries most of the signal since steadiness is nearly
            # constant across produced tracks; it acts as a small modifier.
            danceability = float(round(0.8 * punch + 0.2 * steadiness, 4))
        else:
            danceability = 0.0

        return {
            "bpm": bpm,
            "key": key,
            "scale": scale,
            "energy": energy,
            "danceability": danceability
        }
    except Exception as e:
        print(f"Analysis error: {e}")
        raise e
