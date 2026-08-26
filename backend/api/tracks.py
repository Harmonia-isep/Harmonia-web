import os
import shutil
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.audio.artwork import extract_artwork
from backend.models.database import get_db
from backend.models.models import Analysis, PlaylistTrack, Track, User

router = APIRouter()

UPLOAD_DIR = "uploads"

@router.post("/upload")
def upload_track(
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

    # guard against oversized files. The free-tier server has limited RAM,
    # and analysing a very large file can exceed it. A normal song is well
    # under 20 MB, so reject anything bigger with a clear message.
    max_size = 20 * 1024 * 1024  # 20 MB
    if os.path.getsize(file_path) > max_size:
        os.remove(file_path)
        raise HTTPException(
            status_code=413,
            detail="File too large. Please upload a track under 20 MB (a normal-length song)."
        )

    # try to pull album art out of the file's metadata
    artwork_path = extract_artwork(file_path)

    track = Track(
        title=title,
        artist=artist,
        album=album,
        file_path=file_path,
        artwork_path=artwork_path,
        user_id=user_id
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return {"id": track.id, "title": track.title, "file_path": track.file_path}

@router.get("/user/{user_id}")
def get_user_tracks(
    user_id: int,
    search: str | None = None,
    key: str | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    db: Session = Depends(get_db)
):
    from backend.models.models import Analysis
    query = db.query(Track).filter(Track.user_id == user_id)

    if search:
        query = query.filter(
            (Track.title.ilike(f"%{search}%")) | (Track.artist.ilike(f"%{search}%"))
        )

    if key or bpm_min or bpm_max:
        query = query.join(Analysis, Analysis.track_id == Track.id)
        if key:
            query = query.filter(Analysis.key == key)
        if bpm_min:
            query = query.filter(Analysis.bpm >= bpm_min)
        if bpm_max:
            query = query.filter(Analysis.bpm <= bpm_max)

    tracks = query.all()
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
    # remove dependent rows first so Postgres FK constraints (NO ACTION) hold.
    db.query(PlaylistTrack).filter(PlaylistTrack.track_id == track_id).delete()
    db.query(Analysis).filter(Analysis.track_id == track_id).delete()
    db.delete(track)
    db.commit()
    return {"message": "Track deleted"}

# US18 - Export all tracks + analysis as a CSV file the user can download
@router.get("/user/{user_id}/export")
def export_tracks_csv(user_id: int, db: Session = Depends(get_db)):
    import csv
    import io

    from fastapi.responses import StreamingResponse

    from backend.models.models import Analysis

    # grab all the user's tracks
    tracks = db.query(Track).filter(Track.user_id == user_id).all()

    # write everything into a CSV in memory
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    # header row
    writer.writerow(["Title", "Artist", "Album", "BPM", "Key", "Scale", "Energy", "Danceability"])

    # one row per track, pull analysis if it exists
    for track in tracks:
        a = db.query(Analysis).filter(Analysis.track_id == track.id).first()

        row = [
            track.title,
            track.artist or "",
            track.album or "",
        ]

        # if the track has been analyzed, add those columns too
        if a:
            row += [a.bpm, a.key, a.scale, a.energy, a.danceability]
        else:
            row += ["", "", "", "", ""]

        writer.writerow(row)

    buffer.seek(0)

    # send it back as a downloadable file
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=harmonia_export.csv"}
    )

# serve a track's album art image
@router.get("/{track_id}/artwork")
def get_track_artwork(track_id: int, db: Session = Depends(get_db)):
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    # the track might not have artwork, or the file might be missing
    if not track.artwork_path or not os.path.exists(track.artwork_path):
        raise HTTPException(status_code=404, detail="No artwork for this track")

    return FileResponse(track.artwork_path, media_type="image/jpeg")
