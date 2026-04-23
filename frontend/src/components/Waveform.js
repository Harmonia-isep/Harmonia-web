import React, { useRef, useState, useEffect, useCallback } from 'react';
import { getAudioUrl } from '../api';
import './Waveform.css';

const BAR_COUNT = 200;
const BAR_GAP = 2;

export default function Waveform({ trackId }) {
  const canvasRef = useRef(null);
  const audioRef = useRef(null);
  const animFrameRef = useRef(null);
  const [peaks, setPeaks] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);

  // Decode audio and extract peaks
  useEffect(() => {
    setPeaks(null);
    setLoading(true);
    setError(false);
    setPlaying(false);
    setProgress(0);
    setCurrentTime(0);
    setDuration(0);

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
    }

    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const url = getAudioUrl(trackId);

    fetch(url)
      .then(res => {
        if (!res.ok) throw new Error('fetch failed');
        return res.arrayBuffer();
      })
      .then(buf => audioCtx.decodeAudioData(buf))
      .then(decoded => {
        const raw = decoded.getChannelData(0);
        const step = Math.floor(raw.length / BAR_COUNT);
        const bars = [];
        for (let i = 0; i < BAR_COUNT; i++) {
          let sum = 0;
          for (let j = 0; j < step; j++) {
            sum += Math.abs(raw[i * step + j]);
          }
          bars.push(sum / step);
        }
        const max = Math.max(...bars);
        setPeaks(bars.map(b => b / max));
        setLoading(false);

        // Set up HTML Audio for playback
        const audio = new Audio(url);
        audio.preload = 'auto';
        audioRef.current = audio;
        audio.addEventListener('loadedmetadata', () => setDuration(audio.duration));
        audio.addEventListener('ended', () => {
          setPlaying(false);
          setProgress(1);
        });
      })
      .catch(() => {
        setError(true);
        setLoading(false);
      });

    return () => {
      audioCtx.close();
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = '';
      }
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [trackId]);

  // Animation loop for progress tracking
  useEffect(() => {
    if (!playing) {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
      return;
    }
    const tick = () => {
      const audio = audioRef.current;
      if (audio && audio.duration) {
        setProgress(audio.currentTime / audio.duration);
        setCurrentTime(audio.currentTime);
      }
      animFrameRef.current = requestAnimationFrame(tick);
    };
    animFrameRef.current = requestAnimationFrame(tick);
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [playing]);

  // Draw waveform
  const drawWaveform = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !peaks) return;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    ctx.clearRect(0, 0, w, h);

    const barWidth = (w - (BAR_COUNT - 1) * BAR_GAP) / BAR_COUNT;
    const playedBars = Math.floor(progress * BAR_COUNT);

    const accent = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#ff3b30';

    for (let i = 0; i < BAR_COUNT; i++) {
      const barH = Math.max(2, peaks[i] * (h - 4));
      const x = i * (barWidth + BAR_GAP);
      const y = (h - barH) / 2;

      if (i < playedBars) {
        ctx.fillStyle = '#ffffff';
      } else if (i === playedBars) {
        ctx.fillStyle = '#ffffff';
      } else {
        ctx.fillStyle = hexToRgba(accent, 0.3);
      }

      ctx.beginPath();
      roundedRect(ctx, x, y, barWidth, barH, 1);
      ctx.fill();
    }
  }, [peaks, progress]);

  useEffect(() => {
    drawWaveform();
  }, [drawWaveform]);

  // Redraw on resize
  useEffect(() => {
    const onResize = () => drawWaveform();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [drawWaveform]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
      setPlaying(false);
    } else {
      audio.play();
      setPlaying(true);
    }
  };

  const handleCanvasClick = (e) => {
    const audio = audioRef.current;
    if (!audio || !audio.duration) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = x / rect.width;
    audio.currentTime = pct * audio.duration;
    setProgress(pct);
    setCurrentTime(audio.currentTime);
    if (!playing) {
      audio.play();
      setPlaying(true);
    }
  };

  const formatTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="waveform-container">
        <div className="waveform-loading">
          <div className="waveform-loading-bars">
            {Array.from({ length: 20 }, (_, i) => (
              <span key={i} style={{ animationDelay: `${i * 0.05}s` }} />
            ))}
          </div>
          <p>Loading waveform...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="waveform-container">
        <div className="waveform-error">
          <p>Could not load audio file</p>
        </div>
      </div>
    );
  }

  return (
    <div className="waveform-container">
      <div className="waveform-controls">
        <button className="waveform-play" onClick={togglePlay}>
          {playing ? (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <rect x="3" y="2" width="4" height="12" rx="1" />
              <rect x="9" y="2" width="4" height="12" rx="1" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M4 2.5v11l9-5.5z" />
            </svg>
          )}
        </button>
        <div className="waveform-time">
          <span>{formatTime(currentTime)}</span>
          <span className="waveform-time-sep">/</span>
          <span>{formatTime(duration)}</span>
        </div>
      </div>
      <canvas
        ref={canvasRef}
        className="waveform-canvas"
        onClick={handleCanvasClick}
      />
    </div>
  );
}

function hexToRgba(hex, alpha) {
  hex = hex.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function roundedRect(ctx, x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
}
