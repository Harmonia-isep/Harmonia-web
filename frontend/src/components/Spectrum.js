import React, { useEffect, useRef, useState } from 'react';
import { getSpectrum } from '../api';
import './Spectrum.css';

export default function Spectrum({ trackId }) {
  const canvasRef = useRef(null);
  const [bands, setBands] = useState(null);
  const [loading, setLoading] = useState(true);

  // fetch the spectrum data when the track changes
  useEffect(() => {
    setLoading(true);
    getSpectrum(trackId)
      .then((res) => {
        setBands(res.data.bands);
        setLoading(false);
      })
      .catch(() => {
        setBands(null);
        setLoading(false);
      });
  }, [trackId]);

  // draw the bars on the canvas whenever we have data
  useEffect(() => {
    if (!bands || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    const barWidth = width / bands.length;
    const accent = getComputedStyle(document.documentElement)
      .getPropertyValue('--accent')
      .trim() || '#ff3b30';

    bands.forEach((value, i) => {
      const barHeight = value * height;
      const x = i * barWidth;
      const y = height - barHeight;

      // fade the bars - taller (louder) bands are more opaque
      ctx.fillStyle = accent;
      ctx.globalAlpha = 0.4 + value * 0.6;
      ctx.fillRect(x, y, barWidth - 1, barHeight);
    });

    ctx.globalAlpha = 1;
  }, [bands]);

  if (loading) return <p className="spectrum-loading">Loading spectrum...</p>;
  if (!bands) return null;

  return (
    <div className="spectrum">
      <div className="spectrum-header">
        <span className="spectrum-label">Frequency Spectrum</span>
      </div>
      <canvas ref={canvasRef} width={500} height={120} className="spectrum-canvas" />
      <div className="spectrum-axis">
        <span>Bass</span>
        <span>Mids</span>
        <span>Highs</span>
      </div>
    </div>
  );
}
