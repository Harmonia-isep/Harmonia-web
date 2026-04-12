import React, { useState } from 'react';
import { uploadTrack, analyzeTrack } from '../api';
import './Upload.css';

export default function Upload({ user, onUploaded }) {
  const [form, setForm] = useState({ title: '', artist: '', album: '' });
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);

  const handle = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const submit = async () => {
    if (!file || !form.title) { setStatus('Please add a file and title.'); return; }
    setLoading(true); setStatus('Uploading...');
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('title', form.title);
      fd.append('artist', form.artist);
      fd.append('album', form.album);
      fd.append('user_id', user.user_id);
      const res = await uploadTrack(fd);
      setStatus('Analyzing audio...');
      await analyzeTrack(res.data.id);
      setStatus('Done! Track uploaded and analysis started.');
      setTimeout(onUploaded, 1500);
    } catch (err) {
      setStatus('Upload failed: ' + (err.response?.data?.detail || err.message));
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
      {status && <p className="status">{status}</p>}
      <button onClick={submit} disabled={loading}>{loading ? 'Processing...' : 'Upload & Analyze'}</button>
    </div>
  );
}
