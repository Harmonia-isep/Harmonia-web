import React, { useState } from 'react';
import { registerUser, loginUser } from '../api';
import './Auth.css';

export default function Auth({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ username: '', email: '', password: '' });
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
        const res = await loginUser({ email: form.email, password: form.password });
        onLogin(res.data);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong');
    }
    setLoading(false);
  };

  return (
    <div className="auth-bg">
      <div className="auth-box">
        <h1>🎵 Harmonia</h1>
        <p className="subtitle">Music Analysis & Library</p>
        <div className="tabs">
          <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>Login</button>
          <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>Register</button>
        </div>
        {mode === 'register' && (
          <input name="username" placeholder="Username" value={form.username} onChange={handle} />
        )}
        <input name="email" placeholder="Email" value={form.email} onChange={handle} />
        <input name="password" type="password" placeholder="Password" value={form.password} onChange={handle} />
        {error && <p className="error">{error}</p>}
        <button className="submit" onClick={submit} disabled={loading}>
          {loading ? 'Please wait...' : mode === 'login' ? 'Login' : 'Register'}
        </button>
      </div>
    </div>
  );
}
