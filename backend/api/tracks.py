from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from backend.models.database import get_db
from backend.models.models import Track, User
import shutil, os, uuid

router = APIRouter()

UPLOAD_DIR = "uploads"

@router.post("/upload")
async def upload_track(
    file: UploadFile = File(...),
    title: str = Form(...),
    artist: str = Form(None),
    album: str = Form(None),
    user_id: int = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    track = Track(
        title=title,
        artist=artist,
        album=album,
        file_path=file_path,
        user_id=user_id
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return {"id": track.id, "title": track.title, "file_path": track.file_path}

@router.get("/user/{user_id}")
def get_user_tracks(user_id: int, db: Session = Depends(get_db)):
    tracks = db.query(Track).filter(Track.user_id == user_id).all()
    return [{"id": t.id, "title": t.title, "artist": t.artist, "album": t.album, "uploaded_at": t.uploaded_at} for t in tracks]

@router.get("/{track_id}")
def get_track(track_id: int, db: Session = Depends(get_db)):
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return {"id": track.id, "title": track.title, "artist": track.artist, "analysis": track.analysis}

@router.get("/{track_id}/audio")
def get_track_audio(track_id: int, db: Session = Depends(get_db)):
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if not os.path.exists(track.file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(track.file_path, media_type="audio/mpeg")

@router.delete("/{track_id}")
def delete_track(track_id: int, db: Session = Depends(get_db)):
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if os.path.exists(track.file_path):
        os.remove(track.file_path)
    db.delete(track)
    db.commit()
    return {"message": "Track deleted"}
