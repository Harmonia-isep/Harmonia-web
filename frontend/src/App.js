import React, { useState, useEffect } from 'react';
import Auth from './components/Auth';
import Library from './components/Library';
import Upload from './components/Upload';
import { createGuestUser } from './api';
import './App.css';

export default function App() {
  const [user, setUser] = useState(null);
  const [page, setPage] = useState('library');
  const [showAuth, setShowAuth] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem('harmonia_user');
    if (stored) {
      setUser(JSON.parse(stored));
    } else {
      createGuestUser().then(res => {
        const guest = { ...res.data, is_guest: true };
        localStorage.setItem('harmonia_user', JSON.stringify(guest));
        setUser(guest);
      }).catch(() => {});
    }
  }, []);

  const handleLogin = (userData) => {
    const loggedIn = { ...userData, is_guest: false };
    localStorage.setItem('harmonia_user', JSON.stringify(loggedIn));
    setUser(loggedIn);
    setShowAuth(false);
    setPage('library');
  };

  const handleSignOut = async () => {
    try {
      const res = await createGuestUser();
      const guest = { ...res.data, is_guest: true };
      localStorage.setItem('harmonia_user', JSON.stringify(guest));
      setUser(guest);
    } catch {
      localStorage.removeItem('harmonia_user');
      setUser(null);
    }
    setPage('library');
  };

  if (!user) return null;

  return (
    <div className="app">
      <header className="header">
        <h1 className="logo">Harmonia</h1>
        <nav>
          <button className={page === 'library' ? 'active' : ''} onClick={() => setPage('library')}>Library</button>
          <button className={page === 'upload' ? 'active' : ''} onClick={() => setPage('upload')}>Upload</button>
          <div className="nav-separator" />
          {user.is_guest ? (
            <button className="sign-in-btn" onClick={() => setShowAuth(true)}>Sign In</button>
          ) : (
            <>
              <span className="nav-user">{user.username}</span>
              <button className="logout" onClick={handleSignOut}>Sign Out</button>
            </>
          )}
        </nav>
      </header>
      <main className="main">
        {page === 'library' && <Library user={user} />}
        {page === 'upload' && <Upload user={user} onUploaded={() => setPage('library')} />}
      </main>
      {showAuth && <Auth onLogin={handleLogin} onClose={() => setShowAuth(false)} />}
    </div>
  );
}
