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
