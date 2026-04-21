import React, { useState, useEffect } from 'react';
import Auth from './components/Auth';
import Landing from './components/Landing';
import Library from './components/Library';
import Upload from './components/Upload';
import { createGuestUser } from './api';
import './App.css';

export default function App() {
  const [user, setUser] = useState(null);
  const [page, setPage] = useState('library');
  const [showAuth, setShowAuth] = useState(false);
  const [authMode, setAuthMode] = useState('login');
  const [loading, setLoading] = useState(true);

  // Restore user from localStorage
  useEffect(() => {
    const stored = localStorage.getItem('harmonia_user');
    if (stored) setUser(JSON.parse(stored));
    setLoading(false);
  }, []);

  // Scroll listener for nav border reveal
  useEffect(() => {
    const onScroll = () => {
      document.querySelector('.header')?.classList.toggle('scrolled', window.scrollY > 0);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleLogin = (userData) => {
    const loggedIn = { ...userData, is_guest: false };
    localStorage.setItem('harmonia_user', JSON.stringify(loggedIn));
    setUser(loggedIn);
    setShowAuth(false);
    setPage('library');
  };

  const handleSignOut = () => {
    localStorage.removeItem('harmonia_user');
    setUser(null);
  };

  const handleTryFree = async () => {
    try {
      const res = await createGuestUser();
      const guest = { ...res.data, is_guest: true };
      localStorage.setItem('harmonia_user', JSON.stringify(guest));
      setUser(guest);
    } catch {}
  };

  const openAuth = (mode) => {
    setAuthMode(mode);
    setShowAuth(true);
  };

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  if (loading) return null;

  const isLanding = !user;

  return (
    <div className="app">
      <header className={`header ${isLanding ? 'header-landing' : ''}`}>
        <h1
          className="logo"
          onClick={() => {
            if (isLanding) window.scrollTo({ top: 0, behavior: 'smooth' });
            else if (user?.is_guest) { localStorage.removeItem('harmonia_user'); setUser(null); }
            else setPage('library');
          }}
          style={{ cursor: 'pointer' }}
        >
          Harmonia
        </h1>
        <nav className="nav-center">
          {isLanding ? (
            <>
              <a href="#features" onClick={(e) => { e.preventDefault(); scrollTo('features'); }}>Features</a>
              <a href="#how" onClick={(e) => { e.preventDefault(); scrollTo('how'); }}>How it works</a>
              <a href="#demo" onClick={(e) => { e.preventDefault(); scrollTo('demo'); }}>Demo</a>
            </>
          ) : (
            <>
              <button className={page === 'library' ? 'active' : ''} onClick={() => setPage('library')}>Library</button>
              <button className={page === 'upload' ? 'active' : ''} onClick={() => setPage('upload')}>Upload</button>
            </>
          )}
        </nav>
        <div className="nav-right">
          {isLanding ? (
            <>
              <button className="nav-login" onClick={() => openAuth('login')}>Log in</button>
              <button className="nav-signup" onClick={() => openAuth('register')}>Sign up</button>
            </>
          ) : user.is_guest ? (
            <>
              <button className="nav-back" onClick={() => { localStorage.removeItem('harmonia_user'); setUser(null); }}>Home</button>
              <button className="sign-in-btn" onClick={() => openAuth('login')}>Sign In</button>
            </>
          ) : (
            <>
              <span className="nav-user">{user.username}</span>
              <button className="logout" onClick={handleSignOut}>Sign Out</button>
            </>
          )}
        </div>
      </header>

      {isLanding ? (
        <Landing onTryFree={handleTryFree} onOpenAuth={openAuth} />
      ) : (
        <main className="main">
          {page === 'library' && <Library user={user} />}
          {page === 'upload' && <Upload user={user} onUploaded={() => setPage('library')} />}
        </main>
      )}

      {showAuth && (
        <Auth
          onLogin={handleLogin}
          onClose={() => setShowAuth(false)}
          defaultMode={authMode}
        />
      )}
    </div>
  );
}
