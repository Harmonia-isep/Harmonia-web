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
    background_tasks.add_task(run_analysis, track_id, track.file_path, db)
    return {"message": "Analysis started", "track_id": track_id}

def run_analysis(track_id: int, file_path: str, db: Session):
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
    y, sr = librosa.load(track.file_path, sr=None, duration=30)

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

    # split into equal bands and average each one
    band_size = len(fft) // num_bands
    bands = []
    for i in range(num_bands):
        start = i * band_size
        end = start + band_size
        chunk = fft[start:end]
        if len(chunk) > 0:
            bands.append(float(np.mean(chunk)))

    # normalize so the tallest band is 1.0 (makes it easy to draw)
    peak = max(bands) if bands else 1.0
    bands = [round(b / peak, 4) for b in bands]

    return {"track_id": track_id, "bands": bands}
