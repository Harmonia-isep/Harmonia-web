import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from backend.models.database import get_db
from backend.models.models import Track, Analysis
from backend.audio.analyzer import analyze_audio

router = APIRouter()

@router.post("/analyze/{track_id}")
async def analyze_track(track_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if not os.path.exists(track.file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    background_tasks.add_task(run_analysis, track_id, track.file_path)
    return {"message": "Analysis started", "track_id": track_id}

def run_analysis(track_id: int, file_path: str):
    # This runs as a background task AFTER the request has returned, so it
    # must open its own database session - the request's session is already
    # closed by then. pool_pre_ping (set on the engine) ensures this session
    # gets a live connection even if Neon dropped an idle one.
    from backend.models.database import SessionLocal
    db = SessionLocal()
    try:
        result = analyze_audio(file_path)
        existing = db.query(Analysis).filter(Analysis.track_id == track_id).first()
        if existing:
            existing.bpm = result["bpm"]
            existing.key = result["key"]
            existing.scale = result["scale"]
            existing.energy = result["energy"]
            existing.danceability = result["danceability"]
        else:
            analysis = Analysis(track_id=track_id, **result)
            db.add(analysis)
        db.commit()
    finally:
        db.close()

@router.get("/{track_id}")
def get_analysis(track_id: int, db: Session = Depends(get_db)):
    analysis = db.query(Analysis).filter(Analysis.track_id == track_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this track")
    return {
        "track_id": track_id,
        "bpm": analysis.bpm,
        "key": analysis.key,
        "scale": analysis.scale,
        "energy": analysis.energy,
        "danceability": analysis.danceability,
        "analyzed_at": analysis.analyzed_at
    }


# returns frequency spectrum data for a track, used to draw the FFT chart
@router.get("/{track_id}/spectrum")
def get_spectrum(track_id: int, db: Session = Depends(get_db)):
    import librosa
    import numpy as np

    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if not os.path.exists(track.file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")

    # load a chunk of the track
    # mono at 22050 Hz keeps memory low (free-tier hosting has limited RAM).
    # 30s is enough to represent the track's frequency content.
    y, sr = librosa.load(track.file_path, sr=22050, mono=True, duration=30)

    # run an FFT to get the frequency content
    fft = np.abs(np.fft.rfft(y))
    freqs = np.fft.rfftfreq(len(y), 1 / sr)

    # we don't need thousands of points - group frequencies into bands
    # focus on the audible/musical range up to ~16kHz
    num_bands = 64
    max_freq = 16000
    mask = freqs <= max_freq
    freqs = freqs[mask]
    fft = fft[mask]

    # group frequencies into bands on a LOG scale across the frequency axis.
    # human hearing is logarithmic - we perceive octaves, not linear Hz - so
    # log-spaced bands give a far more natural looking spectrum than equal ones.
    log_edges = np.logspace(np.log10(20), np.log10(max_freq), num_bands + 1)

    bands = []
    for i in range(num_bands):
        lo, hi = log_edges[i], log_edges[i + 1]
        idx = np.where((freqs >= lo) & (freqs < hi))[0]
        if len(idx) > 0:
            bands.append(float(np.mean(fft[idx])))
        else:
            bands.append(0.0)

    # convert magnitudes to decibels (log scale on the amplitude axis too).
    # this tames the huge bass spike and lifts the quieter high frequencies,
    # which is exactly how real spectrum analyzers display sound.
    bands = np.array(bands)
    bands = 20 * np.log10(bands + 1e-6)  # to dB

    # shift so the quietest is 0, then normalize so the loudest is 1
    bands = bands - bands.min()
    peak = bands.max() if bands.max() > 0 else 1.0
    bands = [round(float(b / peak), 4) for b in bands]

    return {"track_id": track_id, "bands": bands}


# ---- Harmonic mixing: the Camelot wheel ----
# Every musical key maps to a Camelot code: a number 1-12 plus a letter
# (A = minor, B = major). Two tracks mix well harmonically when their codes
# are the same, one step apart on the wheel (same letter, number +/-1, wrapping
# 12->1), or the relative major/minor (same number, opposite letter).
# Reference: Mark Davis' Camelot wheel, the DJ standard for harmonic mixing.

# minor keys -> Camelot A codes. Both sharp and flat spellings included
# because different tools name the black keys differently.
CAMELOT_MINOR = {
    "G#": "1A", "Ab": "1A",
    "D#": "2A", "Eb": "2A",
    "A#": "3A", "Bb": "3A",
    "F": "4A",
    "C": "5A",
    "G": "6A",
    "D": "7A",
    "A": "8A",
    "E": "9A",
    "B": "10A",
    "F#": "11A", "Gb": "11A",
    "C#": "12A", "Db": "12A",
}

# major keys -> Camelot B codes.
CAMELOT_MAJOR = {
    "B": "1B",
    "F#": "2B", "Gb": "2B",
    "C#": "3B", "Db": "3B",
    "G#": "4B", "Ab": "4B",
    "D#": "5B", "Eb": "5B",
    "A#": "6B", "Bb": "6B",
    "F": "7B",
    "C": "8B",
    "G": "9B",
    "D": "10B",
    "A": "11B",
    "E": "12B",
}


def to_camelot(key: str, scale: str):
    """Turn a key + scale (e.g. 'G' 'minor') into a Camelot code (e.g. '6A')."""
    if not key or not scale:
        return None
    if scale.lower() == "minor":
        return CAMELOT_MINOR.get(key)
    else:
        return CAMELOT_MAJOR.get(key)


def camelot_compatible(code_a: str, code_b: str) -> bool:
    """
    True if two Camelot codes are harmonically compatible.
    The three safe DJ moves:
      1. same code            (e.g. 8A -> 8A)
      2. same number, A<->B   (relative major/minor, e.g. 8A -> 8B)
      3. adjacent number, same letter, wrapping 12<->1 (e.g. 8A -> 7A or 9A)
    """
    if not code_a or not code_b:
        return False

    # split each code into its number and letter parts
    num_a, letter_a = int(code_a[:-1]), code_a[-1]
    num_b, letter_b = int(code_b[:-1]), code_b[-1]

    # rule 1: exactly the same
    if code_a == code_b:
        return True

    # rule 2: relative major/minor - same number, different letter
    if num_a == num_b and letter_a != letter_b:
        return True

    # rule 3: one step around the wheel, same letter (12 wraps to 1)
    if letter_a == letter_b:
        diff = abs(num_a - num_b)
        if diff == 1 or diff == 11:  # 11 covers the 12<->1 wrap
            return True

    return False


# recommend tracks from the library that mix well with a given track
@router.get("/{track_id}/recommendations")
def get_recommendations(track_id: int, db: Session = Depends(get_db)):
    # the track we want matches for
    source = db.query(Analysis).filter(Analysis.track_id == track_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="No analysis for this track")

    source_track = db.query(Track).filter(Track.id == track_id).first()
    source_code = to_camelot(source.key, source.scale)

    # look at every other analyzed track belonging to the same user
    others = db.query(Analysis).filter(Analysis.track_id != track_id).all()

    recommendations = []
    for other in others:
        other_track = db.query(Track).filter(Track.id == other.track_id).first()
        # only recommend tracks owned by the same user
        if not other_track or other_track.user_id != source_track.user_id:
            continue

        # BPM must be within +/- 5 BPM to beatmatch comfortably
        bpm_close = abs((other.bpm or 0) - (source.bpm or 0)) <= 5

        # keys must be harmonically compatible on the Camelot wheel
        other_code = to_camelot(other.key, other.scale)
        key_ok = camelot_compatible(source_code, other_code)

        # a track is recommended only if BOTH conditions hold
        if bpm_close and key_ok:
            recommendations.append({
                "track_id": other_track.id,
                "title": other_track.title,
                "artist": other_track.artist,
                "bpm": other.bpm,
                "key": other.key,
                "scale": other.scale,
                "camelot": other_code,
            })

    return {
        "track_id": track_id,
        "camelot": source_code,
        "recommendations": recommendations,
    }
