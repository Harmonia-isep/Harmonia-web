import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.audio.analyzer import analyze_audio
from backend.models.database import get_db
from backend.models.models import Analysis, Track

router = APIRouter()

@router.post("/analyze/{track_id}")
def analyze_track(track_id: int, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if not os.path.exists(track.file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    background_tasks.add_task(run_analysis, track_id, track.file_path, request.app.state.sessionmaker)
    return {"message": "Analysis started", "track_id": track_id}

def run_analysis(track_id: int, file_path: str, session_factory):
    # Runs as a background task after the response is sent, outside any request,
    # so it is handed the app's session factory explicitly rather than reaching
    # for module-level state.
    db = session_factory()
    try:
        result = analyze_audio(file_path)
        # Explicit field mapping, not Analysis(**result): the analyzer's output
        # keys and the database schema stay independently changeable, and a new
        # analyzer key can no longer crash the write with an opaque error.
        existing = db.query(Analysis).filter(Analysis.track_id == track_id).first()
        if existing:
            existing.bpm = result["bpm"]
            existing.key = result["key"]
            existing.scale = result["scale"]
            existing.energy = result["energy"]
            existing.danceability = result["danceability"]
            existing.beat_grid = result["beats"]
            existing.intro_end = result["intro_end"]
            existing.outro_start = result["outro_start"]
        else:
            db.add(Analysis(
                track_id=track_id,
                bpm=result["bpm"],
                key=result["key"],
                scale=result["scale"],
                energy=result["energy"],
                danceability=result["danceability"],
                beat_grid=result["beats"],
                intro_end=result["intro_end"],
                outro_start=result["outro_start"],
            ))
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


@router.get("/{track_id}/beats")
def get_beats(track_id: int, db: Session = Depends(get_db)):
    """The beat grid (beat times in seconds) for a track, for the beat overlay."""
    analysis = db.query(Analysis).filter(Analysis.track_id == track_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this track")
    return {"track_id": track_id, "beats": analysis.beat_grid or []}


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
    source = db.query(Analysis).filter(Analysis.track_id == track_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="No analysis for this track")

    source_code = to_camelot(source.key, source.scale)
    source_bpm = source.bpm or 0

    # One query: every other analyzed track joined to its Track row, with the +/- 5
    # BPM beatmatch window applied in SQL. Camelot compatibility stays in Python (a
    # fixed 24-node graph, not worth pushing into SQL).
    rows = (
        db.query(Analysis, Track)
        .join(Track, Track.id == Analysis.track_id)
        .filter(Analysis.track_id != track_id)
        .filter(func.abs(func.coalesce(Analysis.bpm, 0) - source_bpm) <= 5)
        .all()
    )

    recommendations = []
    for other, other_track in rows:
        other_code = to_camelot(other.key, other.scale)
        if camelot_compatible(source_code, other_code):
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
