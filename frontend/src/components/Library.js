import React, { useEffect, useState, useRef } from 'react';
import { getUserTracks, getAnalysis, searchTracks, exportCSV, getArtworkUrl, getUserPlaylists, addToPlaylist, getRecommendations } from '../api';
import Waveform from './Waveform';
import Spectrum from './Spectrum';
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

  // playlists for the "add to playlist" menu
  const [playlists, setPlaylists] = useState([]);
  const [menuOpen, setMenuOpen] = useState(null); // track id whose menu is open
  const [toast, setToast] = useState('');
  const [recs, setRecs] = useState([]);
  const selectedIdRef = useRef(null);

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
    getUserPlaylists(user.user_id).then(res => setPlaylists(res.data)).catch(() => {});
  }, [user]);

  // search when user stops typing for 400ms
  useEffect(() => {
    const timer = setTimeout(() => fetchTracks(), 400);
    return () => clearTimeout(timer);
  }, [searchText, filterKey, bpmMin, bpmMax]);

  const selectTrack = async (track) => {
    selectedIdRef.current = track.id;
    setSelected(track);
    setAnalysis(null);
    setRecs([]);
    setAnalyzing(true);

    // analysis runs in the background on the server and may not be ready
    // the instant we ask. So we poll: check every 2s, up to ~30s, and show
    // the results the moment they appear - no need to click away and back.
    const maxTries = 15;
    let found = null;

    for (let attempt = 0; attempt < maxTries; attempt++) {
      try {
        const res = await getAnalysis(track.id);
        found = res.data;
        break; // got it
      } catch {
        // not ready yet - wait 2 seconds and try again
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
    }

    // if the user clicked a different track while we were polling, drop this
    if (selectedIdRef.current !== track.id) return;

    setAnalysis(found);
    setAnalyzing(false);

    // once analysis exists, load harmonic mixing recommendations
    if (found && selectedIdRef.current === track.id) {
      try {
        const rec = await getRecommendations(track.id);
        if (selectedIdRef.current === track.id) {
          setRecs(rec.data.recommendations || []);
        }
      } catch {
        setRecs([]);
      }
    }
  };

  // add a track to a chosen playlist
  const handleAddToPlaylist = async (trackId, playlistId, playlistName) => {
    setMenuOpen(null);
    try {
      await addToPlaylist(playlistId, trackId);
      setToast(`Added to ${playlistName}`);
      setTimeout(() => setToast(''), 2000);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Could not add track';
      setToast(msg);
      setTimeout(() => setToast(''), 2000);
    }
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
            <div className="add-wrapper">
              <button
                className="add-btn"
                onClick={(e) => { e.stopPropagation(); setMenuOpen(menuOpen === t.id ? null : t.id); }}
              >
                +
              </button>
              {menuOpen === t.id && (
                <div className="add-menu" onClick={(e) => e.stopPropagation()}>
                  {playlists.length === 0 && <p className="add-menu-empty">No playlists yet</p>}
                  {playlists.map(p => (
                    <button
                      key={p.id}
                      className="add-menu-item"
                      onClick={() => handleAddToPlaylist(t.id, p.id, p.name)}
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              )}
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
            {analyzing && <p className="loading analyzing-pulse">Analyzing track... this can take a few seconds</p>}
            {!analyzing && !analysis && <p className="empty">Analysis is taking longer than expected. Try selecting the track again.</p>}
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
            {analysis && <Spectrum trackId={selected.id} />}
            {analysis && (
              <div className="recs">
                <span className="recs-label">Mixes Well With</span>
                {recs.length === 0 && (
                  <p className="recs-empty">No harmonic matches in your library yet.</p>
                )}
                {recs.map((r) => (
                  <div
                    key={r.track_id}
                    className="rec-item"
                    onClick={() => {
                      const t = tracks.find((x) => x.id === r.track_id);
                      if (t) selectTrack(t);
                    }}
                  >
                    <span className="rec-camelot">{r.camelot}</span>
                    <div className="rec-info">
                      <p className="rec-title">{r.title}</p>
                      <p className="rec-meta">{r.artist || 'Unknown artist'}</p>
                    </div>
                    <span className="rec-bpm">{Math.round(r.bpm)} BPM</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
