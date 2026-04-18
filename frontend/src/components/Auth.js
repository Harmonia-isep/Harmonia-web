import React, { useState } from 'react';
import { registerUser, loginUser } from '../api';
import './Auth.css';

export default function Auth({ onLogin, onClose }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ username: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handle = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const submit = async () => {
    setLoading(true); setError('');
    try {
      if (mode === 'register') {
        await registerUser(form);
        setMode('login');
        setError('Registered! Please log in.');
      } else {
        const res = await loginUser({ username: form.username, password: form.password });
        onLogin(res.data);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong');
    }
    setLoading(false);
  };

  return (
    <div className="auth-overlay" onClick={onClose}>
      <div className="auth-box" onClick={(e) => e.stopPropagation()}>
        <button className="auth-close" onClick={onClose}>&times;</button>
        <h1>Harmonia</h1>
        <p className="subtitle">Sign in to sync your library</p>
        <div className="tabs">
          <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Login</button>
          <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Register</button>
        </div>
        <input name="username" placeholder="Username" value={form.username} onChange={handle} />
        <input name="password" type="password" placeholder="Password" value={form.password} onChange={handle} />
        {error && <p className="error">{error}</p>}
        <button className="submit" onClick={submit} disabled={loading}>
          {loading ? 'Please wait...' : mode === 'login' ? 'Login' : 'Register'}
        </button>
      </div>
    </div>
  );
}
