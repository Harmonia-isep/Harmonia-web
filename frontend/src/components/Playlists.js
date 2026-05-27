import React, { useEffect, useState } from 'react';
import {
  getUserPlaylists,
  createPlaylist,
  getPlaylistTracks,
  deletePlaylist,
  removeFromPlaylist,
} from '../api';
import './Playlists.css';

export default function Playlists({ user }) {
  const [playlists, setPlaylists] = useState([]);
  const [selected, setSelected] = useState(null);
  const [tracks, setTracks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);

  // load all the user's playlists
  const loadPlaylists = () => {
    setLoading(true);
    getUserPlaylists(user.user_id)
      .then((res) => {
        setPlaylists(res.data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    loadPlaylists();
  }, [user]);

  // open a playlist and load the tracks inside it
  const openPlaylist = async (playlist) => {
    setSelected(playlist);
    setTracks([]);
    try {
      const res = await getPlaylistTracks(playlist.id);
      setTracks(res.data);
    } catch {
      setTracks([]);
    }
  };

  // make a new playlist
  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await createPlaylist(newName.trim(), user.user_id);
      setNewName('');
      loadPlaylists();
    } catch {
      // ignore for now
    }
    setCreating(false);
  };

  // delete a whole playlist
  const handleDelete = async (playlistId) => {
    try {
      await deletePlaylist(playlistId);
      if (selected?.id === playlistId) {
        setSelected(null);
        setTracks([]);
      }
      loadPlaylists();
    } catch {
      // ignore
    }
  };

  // take a track out of the open playlist
  const handleRemoveTrack = async (trackId) => {
    try {
      await removeFromPlaylist(selected.id, trackId);
      setTracks((t) => t.filter((x) => x.track_id !== trackId));
    } catch {
      // ignore
    }
  };

  if (loading) return <p className="loading">Loading your playlists...</p>;

  return (
    <div className="playlists">
      {/* left side - list of playlists + create */}
      <div className="playlist-list">
        <h2>
          Your Playlists <span>({playlists.length})</span>
        </h2>

        <div className="create-row">
          <input
            type="text"
            placeholder="New playlist name..."
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          />
          <button onClick={handleCreate} disabled={creating || !newName.trim()}>
            Create
          </button>
        </div>

        {playlists.length === 0 && (
          <p className="empty">No playlists yet. Create your first one above.</p>
        )}

        {playlists.map((p) => (
          <div
            key={p.id}
            className={`playlist-item ${selected?.id === p.id ? 'active' : ''}`}
            onClick={() => openPlaylist(p)}
          >
            <div className="playlist-info">
              <p className="playlist-name">{p.name}</p>
              <p className="playlist-meta">
                {p.track_count} track{p.track_count !== 1 ? 's' : ''}
              </p>
            </div>
            <button
              className="delete-btn"
              onClick={(e) => {
                e.stopPropagation();
                handleDelete(p.id);
              }}
            >
              Delete
            </button>
          </div>
        ))}
      </div>

      {/* right side - tracks inside the selected playlist */}
      <div className="playlist-detail">
        {!selected && (
          <div className="no-selection">
            <p>Select a playlist to view its tracks</p>
          </div>
        )}

        {selected && (
          <div>
            <h2>{selected.name}</h2>
            {tracks.length === 0 && (
              <p className="empty">
                This playlist is empty. Add tracks from your library.
              </p>
            )}
            {tracks.map((t) => (
              <div key={t.track_id} className="detail-track">
                <span className="detail-pos">{t.position + 1}</span>
                <div className="detail-info">
                  <p className="detail-title">{t.title}</p>
                  <p className="detail-artist">{t.artist || 'Unknown artist'}</p>
                </div>
                <button
                  className="remove-btn"
                  onClick={() => handleRemoveTrack(t.track_id)}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
