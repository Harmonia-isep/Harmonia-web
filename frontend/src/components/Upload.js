import React, { useState, useEffect } from 'react';
import { uploadTrack, analyzeTrack } from '../api';
import './Upload.css';

// Parse "Artist - Title.mp3" or "Title.mp3" into { title, artist }
function parseFilename(filename) {
  const nameNoExt = filename.replace(/\.[^.]+$/, '').replace(/_/g, ' ');
  const dashSplit = nameNoExt.split(' - ');
  if (dashSplit.length >= 2) {
    return { artist: dashSplit[0].trim(), title: dashSplit.slice(1).join(' - ').trim() };
  }
  return { artist: '', title: nameNoExt.trim() };
}

export default function Upload({ user, onUploaded }) {
  // Each queue item: { file, title, artist, album, status, progress, error }
  // status: 'pending' | 'uploading' | 'analyzing' | 'done' | 'error'
  const [queue, setQueue] = useState([]);
  const [running, setRunning] = useState(false);
  const [summary, setSummary] = useState('');
  const [dragOver, setDragOver] = useState(false);

  const handleFiles = (fileList) => {
    const files = Array.from(fileList);
    const newItems = files.map((file) => {
      const { title, artist } = parseFilename(file.name);
      return { file, title, artist, album: '', status: 'pending', progress: 0, error: null };
    });
    setQueue((q) => [...q, ...newItems]);
    setSummary('');
  };

  const updateItem = (index, updates) => {
    setQueue((q) => q.map((item, i) => (i === index ? { ...item, ...updates } : item)));
  };

  const removeItem = (index) => {
    setQueue((q) => q.filter((_, i) => i !== index));
  };

  const clearQueue = () => {
    setQueue([]);
    setSummary('');
  };

  // Animate progress for whichever item is currently 'analyzing'
  useEffect(() => {
    const activeIndex = queue.findIndex((item) => item.status === 'analyzing');
    if (activeIndex === -1) return;
    const interval = setInterval(() => {
      setQueue((q) => q.map((item, i) => {
        if (i !== activeIndex || item.status !== 'analyzing') return item;
        if (item.progress >= 95) return item;
        const step = Math.max(0.5, (95 - item.progress) / 20);
        return { ...item, progress: Math.min(95, item.progress + step) };
      }));
    }, 200);
    return () => clearInterval(interval);
  }, [queue]);

  const uploadAll = async () => {
    setRunning(true);
    setSummary('');
    let succeeded = 0;
    let failed = 0;

    for (let i = 0; i < queue.length; i++) {
      const item = queue[i];
      if (item.status === 'done') { succeeded++; continue; }
      if (!item.title) {
        updateItem(i, { status: 'error', error: 'Missing title' });
        failed++;
        continue;
      }

      try {
        updateItem(i, { status: 'uploading', progress: 0, error: null });
        const fd = new FormData();
        fd.append('file', item.file);
        fd.append('title', item.title);
        fd.append('artist', item.artist);
        fd.append('album', item.album);
        fd.append('user_id', user.user_id);
        const res = await uploadTrack(fd);

        updateItem(i, { status: 'analyzing', progress: 0 });
        await analyzeTrack(res.data.id);

        updateItem(i, { status: 'done', progress: 100 });
        succeeded++;
      } catch (err) {
        const msg = err.response?.data?.detail || err.message;
        updateItem(i, { status: 'error', error: msg, progress: 0 });
        failed++;
      }
    }

    setRunning(false);
    setSummary(`${succeeded} of ${queue.length} succeeded${failed > 0 ? `, ${failed} failed` : ''}.`);
    if (succeeded > 0) setTimeout(onUploaded, 1500);
  };

  const statusLabel = (item) => {
    if (item.status === 'error') return item.error;
    if (item.status === 'analyzing') return `Analyzing... ${Math.round(item.progress)}%`;
    return item.status.charAt(0).toUpperCase() + item.status.slice(1);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  };

  return (
    <div className="upload-page">
      <h2>Upload Tracks</h2>

      <div
        className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
        onClick={() => document.getElementById('fileInput').click()}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="drop-zone-icon">&#8593;</div>
        <p>Drop audio files here, or click to browse</p>
        <span className="hint">MP3, WAV, FLAC</span>
        <input
          id="fileInput"
          type="file"
          accept="audio/*"
          multiple
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {queue.length > 0 && (
        <div className="queue">
          <div className="queue-header">
            <span>{queue.length} file{queue.length > 1 ? 's' : ''} queued</span>
            {!running && <button className="link-btn" onClick={clearQueue}>Clear all</button>}
          </div>

          {queue.map((item, i) => (
            <div key={i} className={`queue-item status-${item.status}`}>
              <div className="queue-row">
                <span className="queue-status-dot" />
                <span className="queue-filename">{item.file.name}</span>
                {!running && item.status === 'pending' && (
                  <button className="link-btn" onClick={() => removeItem(i)}>Remove</button>
                )}
              </div>

              {(item.status === 'pending' || item.status === 'error') && (
                <div className="queue-fields">
                  <input
                    placeholder="Title *"
                    value={item.title}
                    onChange={(e) => updateItem(i, { title: e.target.value })}
                    disabled={running}
                  />
                  <input
                    placeholder="Artist"
                    value={item.artist}
                    onChange={(e) => updateItem(i, { artist: e.target.value })}
                    disabled={running}
                  />
                  <input
                    placeholder="Album"
                    value={item.album}
                    onChange={(e) => updateItem(i, { album: e.target.value })}
                    disabled={running}
                  />
                </div>
              )}

              {item.status === 'analyzing' && (
                <div className="progress-wrapper">
                  <div className="progress-bar" style={{ width: `${item.progress}%` }} />
                </div>
              )}

              {item.status !== 'pending' && (
                <div className="queue-status-text">{statusLabel(item)}</div>
              )}
            </div>
          ))}
        </div>
      )}

      {summary && <p className="summary-text">{summary}</p>}

      {queue.length > 0 && (
        <button className="upload-btn" onClick={uploadAll} disabled={running}>
          {running ? 'Processing...' : `Upload ${queue.length} track${queue.length > 1 ? 's' : ''}`}
        </button>
      )}
    </div>
  );
}
