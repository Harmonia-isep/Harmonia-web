import React, { useEffect, useState } from 'react';
import { getTracks, getAnalysis } from '../api';
import Spectrum from './Spectrum';
import './Compare.css';

export default function Compare() {
  const [tracks, setTracks] = useState([]);
  const [loading, setLoading] = useState(true);

  // the two tracks being compared (left and right)
  const [leftId, setLeftId] = useState('');
  const [rightId, setRightId] = useState('');
  const [leftAnalysis, setLeftAnalysis] = useState(null);
  const [rightAnalysis, setRightAnalysis] = useState(null);

  useEffect(() => {
    getTracks()
      .then((res) => {
        setTracks(res.data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  // load analysis whenever a side changes
  useEffect(() => {
    if (leftId) getAnalysis(leftId).then((res) => setLeftAnalysis(res.data)).catch(() => setLeftAnalysis(null));
  }, [leftId]);

  useEffect(() => {
    if (rightId) getAnalysis(rightId).then((res) => setRightAnalysis(res.data)).catch(() => setRightAnalysis(null));
  }, [rightId]);

  if (loading) return <p className="loading">Loading...</p>;

  // one side of the comparison
  const renderSide = (id, setId, analysis, otherId) => (
    <div className="compare-side">
      <select value={id} onChange={(e) => setId(e.target.value)}>
        <option value="">Select a track...</option>
        {tracks.map((t) => (
          <option key={t.id} value={t.id} disabled={String(t.id) === otherId}>
            {t.title}
          </option>
        ))}
      </select>

      {id && analysis && (
        <div>
          <div className="compare-stats">
            <div className="compare-stat">
              <span className="label">BPM</span>
              <span className="value">{analysis.bpm}</span>
            </div>
            <div className="compare-stat">
              <span className="label">Key</span>
              <span className="value">{analysis.key} {analysis.scale}</span>
            </div>
            <div className="compare-stat">
              <span className="label">Energy</span>
              <span className="value">{(analysis.energy * 100).toFixed(0)}%</span>
            </div>
          </div>
          <Spectrum trackId={parseInt(id)} />
        </div>
      )}

      {id && !analysis && <p className="empty">No analysis for this track.</p>}
    </div>
  );

  return (
    <div className="compare-page">
      <h2>Compare Tracks</h2>
      <p className="compare-hint">Pick two tracks to compare their frequency content side by side.</p>

      <div className="compare-grid">
        {renderSide(leftId, setLeftId, leftAnalysis, rightId)}
        {renderSide(rightId, setRightId, rightAnalysis, leftId)}
      </div>
    </div>
  );
}
