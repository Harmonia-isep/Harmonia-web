import React, { useState, useEffect } from 'react';
import { uploadTrack, analyzeTrack } from '../api';
import './Upload.css';

export default function Upload({ user, onUploaded }) {
  const [form, setForm] = useState({ title: '', artist: '', album: '' });
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);

  const handle = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  // Progress bar only animates during the analyzing phase
  useEffect(() => {
    if (!analyzing) return;
    const interval = setInterval(() => {
      setProgress((p) => {
        if (p >= 95) return 95;
        const step = Math.max(0.5, (95 - p) / 20);
        return Math.min(95, p + step);
      });
    }, 200);
    return () => clearInterval(interval);
  }, [analyzing]);

  const submit = async () => {
    if (!file || !form.title) { setStatus('Please add a file and title.'); return; }
    setLoading(true);
    setProgress(0);
    setStatus('Uploading...');
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('title', form.title);
      fd.append('artist', form.artist);
      fd.append('album', form.album);
      fd.append('user_id', user.user_id);
      const res = await uploadTrack(fd);

      // Upload done, analysis starting — NOW show the progress bar
      setAnalyzing(true);
      setStatus('Analyzing audio...');
      await analyzeTrack(res.data.id);

      // Analysis done
      setProgress(100);
      setAnalyzing(false);
      setStatus('Done! Track uploaded and analysis complete.');
      setTimeout(() => {
        onUploaded();
        setProgress(0);
      }, 1500);
    } catch (err) {
      setStatus('Upload failed: ' + (err.response?.data?.detail || err.message));
      setProgress(0);
      setAnalyzing(false);
    }
    setLoading(false);
  };

  return (
    <div className="upload-box">
      <h2>Upload a Track</h2>
      <div className="drop-zone" onClick={() => document.getElementById('fileInput').click()}>
        {file ? <p>✅ {file.name}</p> : <p>Click to select an audio file (MP3, WAV)</p>}
        <input id="fileInput" type="file" accept="audio/*" hidden onChange={(e) => setFile(e.target.files[0])} />
      </div>
      <input name="title" placeholder="Track title *" value={form.title} onChange={handle} />
      <input name="artist" placeholder="Artist" value={form.artist} onChange={handle} />
      <input name="album" placeholder="Album" value={form.album} onChange={handle} />

      {(analyzing || progress === 100) && (
        <div className="progress-wrapper">
          <div className="progress-bar" style={{ width: `${progress}%` }} />
          <span className="progress-label">{Math.round(progress)}%</span>
        </div>
      )}

      {status && <p className="status">{status}</p>}
      <button onClick={submit} disabled={loading}>{loading ? 'Processing...' : 'Upload & Analyze'}</button>
    </div>
  );
}
