from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.models.database import get_db
from backend.models.models import Playlist, PlaylistTrack, Track
import uuid

router = APIRouter()

# create a new playlist
@router.post("/create")
def create_playlist(name: str, user_id: int, db: Session = Depends(get_db)):
    # each playlist gets a unique share token so it can be shared later
    token = str(uuid.uuid4())[:8]

    playlist = Playlist(name=name, user_id=user_id, share_token=token)
    db.add(playlist)
    db.commit()
    db.refresh(playlist)

    return {"id": playlist.id, "name": playlist.name, "share_token": playlist.share_token}

# get all playlists for a user
@router.get("/user/{user_id}")
def get_user_playlists(user_id: int, db: Session = Depends(get_db)):
    playlists = db.query(Playlist).filter(Playlist.user_id == user_id).all()

    result = []
    for p in playlists:
        track_count = db.query(PlaylistTrack).filter(PlaylistTrack.playlist_id == p.id).count()
        result.append({
            "id": p.id,
            "name": p.name,
            "track_count": track_count,
            "share_token": p.share_token,
            "created_at": p.created_at
        })

    return result
