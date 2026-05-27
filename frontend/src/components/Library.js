import React, { useEffect, useState } from 'react';
import { getUserTracks, getAnalysis, searchTracks, exportCSV, getArtworkUrl } from '../api';
import Waveform from './Waveform';
import './Library.css';

export default function Library({ user }) {
  const [tracks, setTracks] = useState([]);
  const [selected, setSelected] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  // search and filter state
  const [searchText, setSearchText] = useState('');
  const [filterKey, setFilterKey] = useState('');
  const [bpmMin, setBpmMin] = useState('');
  const [bpmMax, setBpmMax] = useState('');

  // fetch tracks, re-runs when filters change
  const fetchTracks = () => {
    setLoading(true);
    const params = {};
    if (searchText) params.search = searchText;
    if (filterKey) params.key = filterKey;
    if (bpmMin) params.bpm_min = bpmMin;
    if (bpmMax) params.bpm_max = bpmMax;

    searchTracks(user.user_id, params).then(res => {
      setTracks(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchTracks();
  }, [user]);

  // search when user stops typing for 400ms
  useEffect(() => {
    const timer = setTimeout(() => fetchTracks(), 400);
    return () => clearTimeout(timer);
  }, [searchText, filterKey, bpmMin, bpmMax]);

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

        {/* search and filter bar */}
        <div className="search-bar">
          <input
            type="text"
            placeholder="Search by title or artist..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
        </div>
        <div className="filter-bar">
          <select value={filterKey} onChange={(e) => setFilterKey(e.target.value)}>
            <option value="">All keys</option>
            {['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'].map(k => (
              <option key={k} value={k}>{k}</option>
            ))}
          </select>
          <input type="number" placeholder="BPM min" value={bpmMin} onChange={(e) => setBpmMin(e.target.value)} />
          <input type="number" placeholder="BPM max" value={bpmMax} onChange={(e) => setBpmMax(e.target.value)} />
          <a href={exportCSV(user.user_id)} className="export-btn" download>Export CSV</a>
        </div>
        {tracks.length === 0 && <p className="empty">No tracks yet. Upload your first track!</p>}
        {tracks.map(t => (
          <div key={t.id} className={`track-item ${selected?.id === t.id ? 'active' : ''}`} onClick={() => selectTrack(t)}>
            <div className="track-icon">
              <img
                src={getArtworkUrl(t.id)}
                alt=""
                onError={(e) => { e.target.style.display = 'none'; e.target.nextSibling.style.display = 'flex'; }}
              />
              <span className="track-icon-fallback">&#9834;</span>
            </div>
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
            <Waveform trackId={selected.id} />
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
