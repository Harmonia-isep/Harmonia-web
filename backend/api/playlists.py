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

# add a track to a playlist
@router.post("/{playlist_id}/add/{track_id}")
def add_track_to_playlist(playlist_id: int, track_id: int, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    # check if track is already in the playlist
    exists = db.query(PlaylistTrack).filter(
        PlaylistTrack.playlist_id == playlist_id,
        PlaylistTrack.track_id == track_id
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="Track already in playlist")

    # figure out the next position
    last = db.query(PlaylistTrack).filter(
        PlaylistTrack.playlist_id == playlist_id
    ).count()

    entry = PlaylistTrack(playlist_id=playlist_id, track_id=track_id, position=last)
    db.add(entry)
    db.commit()

    return {"message": f"Track added to playlist at position {last}"}

# remove a track from a playlist
@router.delete("/{playlist_id}/remove/{track_id}")
def remove_track_from_playlist(playlist_id: int, track_id: int, db: Session = Depends(get_db)):
    entry = db.query(PlaylistTrack).filter(
        PlaylistTrack.playlist_id == playlist_id,
        PlaylistTrack.track_id == track_id
    ).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Track not in playlist")

    db.delete(entry)
    db.commit()

    return {"message": "Track removed from playlist"}

# get all tracks in a playlist, ordered by position
@router.get("/{playlist_id}/tracks")
def get_playlist_tracks(playlist_id: int, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    entries = db.query(PlaylistTrack).filter(
        PlaylistTrack.playlist_id == playlist_id
    ).order_by(PlaylistTrack.position).all()

    result = []
    for entry in entries:
        track = db.query(Track).filter(Track.id == entry.track_id).first()
        if track:
            result.append({
                "track_id": track.id,
                "title": track.title,
                "artist": track.artist,
                "position": entry.position
            })

    return result

# reorder tracks — pass a list of track ids in the new order
@router.put("/{playlist_id}/reorder")
def reorder_playlist(playlist_id: int, track_ids: list[int], db: Session = Depends(get_db)):
    for i, track_id in enumerate(track_ids):
        entry = db.query(PlaylistTrack).filter(
            PlaylistTrack.playlist_id == playlist_id,
            PlaylistTrack.track_id == track_id
        ).first()

        if entry:
            entry.position = i

    db.commit()
    return {"message": "Playlist reordered"}

# delete a playlist (tracks stay in the library)
@router.delete("/{playlist_id}")
def delete_playlist(playlist_id: int, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # remove all the track links first
    db.query(PlaylistTrack).filter(PlaylistTrack.playlist_id == playlist_id).delete()
    db.delete(playlist)
    db.commit()

    return {"message": "Playlist deleted"}

# US16 - view a shared playlist by its token (no login needed)
@router.get("/shared/{share_token}")
def get_shared_playlist(share_token: str, db: Session = Depends(get_db)):
    playlist = db.query(Playlist).filter(Playlist.share_token == share_token).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    entries = db.query(PlaylistTrack).filter(
        PlaylistTrack.playlist_id == playlist.id
    ).order_by(PlaylistTrack.position).all()

    tracks = []
    for entry in entries:
        track = db.query(Track).filter(Track.id == entry.track_id).first()
        if track:
            tracks.append({
                "title": track.title,
                "artist": track.artist,
                "position": entry.position
            })

    return {
        "name": playlist.name,
        "tracks": tracks
    }
