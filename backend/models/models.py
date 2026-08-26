from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, MetaData, String
from sqlalchemy.orm import declarative_base, relationship

# Stable, explicit constraint names so migrations can reference constraints by
# name. Required for Alembic batch operations on SQLite (e.g. adding ondelete in
# a later phase), which SQLite performs by recreating the table.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

Base = declarative_base(metadata=MetaData(naming_convention=NAMING_CONVENTION))

class Track(Base):
    __tablename__ = "tracks"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    artist = Column(String)
    album = Column(String)
    file_path = Column(String, nullable=False)
    artwork_path = Column(String)  # path to extracted album art, if the file had any
    duration = Column(Float)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    analysis = relationship("Analysis", back_populates="track", uselist=False, passive_deletes=True)

class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(Integer, primary_key=True)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"))
    bpm = Column(Float)
    key = Column(String)
    scale = Column(String)
    energy = Column(Float)
    danceability = Column(Float)
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    track = relationship("Track", back_populates="analysis")

# a playlist and its ordered tracks
class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    share_token = Column(String, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tracks = relationship("PlaylistTrack", back_populates="playlist", passive_deletes=True)

# links playlists to tracks, with ordering
class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    id = Column(Integer, primary_key=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id", ondelete="CASCADE"))
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"))
    position = Column(Integer, default=0)

    playlist = relationship("Playlist", back_populates="tracks")
    track = relationship("Track")
