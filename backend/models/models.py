from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    tracks = relationship("Track", back_populates="owner")

class Track(Base):
    __tablename__ = "tracks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    artist = Column(String)
    album = Column(String)
    file_path = Column(String, nullable=False)
    artwork_path = Column(String)  # path to extracted album art, if the file had any
    duration = Column(Float)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="tracks")
    analysis = relationship("Analysis", back_populates="track", uselist=False)

class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(Integer, primary_key=True, index=True)
    track_id = Column(Integer, ForeignKey("tracks.id"))
    bpm = Column(Float)
    key = Column(String)
    scale = Column(String)
    energy = Column(Float)
    danceability = Column(Float)
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    track = relationship("Track", back_populates="analysis")

# playlist that belongs to a user
class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    share_token = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User")
    tracks = relationship("PlaylistTrack", back_populates="playlist")

# links playlists to tracks, with ordering
class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"))
    track_id = Column(Integer, ForeignKey("tracks.id"))
    position = Column(Integer, default=0)

    playlist = relationship("Playlist", back_populates="tracks")
    track = relationship("Track")
