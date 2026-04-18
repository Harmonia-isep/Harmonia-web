import React, { useEffect, useState } from 'react';
import { getUserTracks, getAnalysis } from '../api';
import './Library.css';

export default function Library({ user }) {
  const [tracks, setTracks] = useState([]);
  const [selected, setSelected] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    getUserTracks(user.user_id).then(res => {
      setTracks(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [user]);

  const selectTrack = async (track) => {
    setSelected(track);
    setAnalysis(null);
    setAnalyzing(true);
    try {
      const res = await getAnalysis(track.id);
      setAnalysis(res.data);
    } catch {
      setAnalysis(null);
    }
    setAnalyzing(false);
  };

  if (loading) return <p className="loading">Loading your library...</p>;

  return (
    <div className="library">
      <div className="track-list">
        <h2>Your Library <span>({tracks.length})</span></h2>
        {tracks.length === 0 && <p className="empty">No tracks yet. Upload your first track!</p>}
        {tracks.map(t => (
          <div key={t.id} className={`track-item ${selected?.id === t.id ? 'active' : ''}`} onClick={() => selectTrack(t)}>
            <div className="track-icon">&#9834;</div>
            <div className="track-info">
              <p className="track-title">{t.title}</p>
              <p className="track-meta">{t.artist || 'Unknown artist'} {t.album ? `· ${t.album}` : ''}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="analysis-panel">
        {!selected && <div className="no-selection"><p>Select a track to view its analysis</p></div>}
        {selected && (
          <div>
            <h2>{selected.title}</h2>
            <p className="track-meta">{selected.artist || 'Unknown artist'}</p>
            {analyzing && <p className="loading">Loading analysis...</p>}
            {!analyzing && !analysis && <p className="empty">No analysis yet. Re-upload to trigger analysis.</p>}
            {analysis && (
              <div className="analysis-grid">
                <div className="analysis-card">
                  <span className="label">BPM</span>
                  <span className="value">{analysis.bpm}</span>
                </div>
                <div className="analysis-card">
                  <span className="label">Key</span>
                  <span className="value">{analysis.key} {analysis.scale}</span>
                </div>
                <div className="analysis-card">
                  <span className="label">Energy</span>
                  <span className="value">{(analysis.energy * 100).toFixed(1)}%</span>
                </div>
                <div className="analysis-card">
                  <span className="label">Danceability</span>
                  <span className="value">{(analysis.danceability * 100).toFixed(1)}%</span>
                </div>
                <div className="analysis-card wide">
                  <span className="label">Analyzed</span>
                  <span className="value small">{new Date(analysis.analyzed_at).toLocaleString()}</span>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
