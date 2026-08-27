import React, { useEffect, useState } from 'react';
import { getSharedPlaylist } from '../api';
import './Playlists.css';

export default function SharedPlaylist({ token }) {
  const [playlist, setPlaylist] = useState(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    getSharedPlaylist(token)
      .then((res) => {
        setPlaylist(res.data);
        setLoading(false);
      })
      .catch(() => {
        setNotFound(true);
        setLoading(false);
      });
  }, [token]);

  if (loading) return <p className="loading">Loading playlist...</p>;
  if (notFound) return <p className="empty">This playlist could not be found.</p>;

  return (
    <div className="shared-page">
      <div className="shared-header">
        <span className="shared-label">Shared Playlist</span>
        <h1>{playlist.name}</h1>
        <p className="shared-count">
          {playlist.tracks.length} track{playlist.tracks.length !== 1 ? 's' : ''}
        </p>
      </div>

      <div className="shared-tracks">
        {playlist.tracks.map((t, i) => (
          <div key={i} className="detail-track">
            <span className="detail-pos">{t.position + 1}</span>
            <div className="detail-info">
              <p className="detail-title">{t.title}</p>
              <p className="detail-artist">{t.artist || 'Unknown artist'}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
