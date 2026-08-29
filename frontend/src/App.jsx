import React, { useState, useEffect } from 'react';
import Landing from './components/Landing';
import Library from './components/Library';
import Upload from './components/Upload';
import Playlists from './components/Playlists';
import SharedPlaylist from './components/SharedPlaylist';
import Compare from './components/Compare';
import './App.css';

// Harmonia is local-first and single-user, so there are no accounts and no
// login gate. `/` is a front door describing the tool, `/library` is the app
// itself, and `/shared/<token>` is a standalone public playlist page.
export default function App() {
  const [path, setPath] = useState(window.location.pathname);
  const [page, setPage] = useState('library');

  // One-time cleanup of the account object left behind by pre-1.0 builds.
  // Nothing reads it any more, so this is hygiene rather than a fix. Drop this
  // effect after the first public release.
  useEffect(() => {
    localStorage.removeItem('harmonia_user');
  }, []);

  // Client-side routing without a router: three routes do not justify one.
  // Deep links are served by the backend SPA catch-all, which returns
  // index.html for any non-API path.
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const navigate = (to) => {
    window.history.pushState({}, '', to);
    setPath(to);
    window.scrollTo({ top: 0 });
  };

  // Scroll listener for nav border reveal
  useEffect(() => {
    const onScroll = () => {
      document.querySelector('.header')?.classList.toggle('scrolled', window.scrollY > 0);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  // shared playlist links open a standalone public page
  const sharedMatch = path.match(/^\/shared\/(.+)$/);
  if (sharedMatch) {
    return (
      <div className="app">
        <header className="header">
          <h1 className="logo" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
            Harmonia
          </h1>
        </header>
        <main className="main">
          <SharedPlaylist token={sharedMatch[1]} />
        </main>
      </div>
    );
  }

  // Anything that is not the library is the front door.
  const isLanding = !/^\/library\/?$/.test(path);

  return (
    <div className="app">
      <header className={`header ${isLanding ? 'header-landing' : ''}`}>
        <h1
          className="logo"
          onClick={() => {
            if (isLanding) window.scrollTo({ top: 0, behavior: 'smooth' });
            else navigate('/');
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
              <button className={page === 'playlists' ? 'active' : ''} onClick={() => setPage('playlists')}>Playlists</button>
              <button className={page === 'compare' ? 'active' : ''} onClick={() => setPage('compare')}>Compare</button>
            </>
          )}
        </nav>
        <div className="nav-right">
          {isLanding ? (
            <button className="nav-signup" onClick={() => navigate('/library')}>Open Library</button>
          ) : (
            <button className="nav-back" onClick={() => navigate('/')}>Home</button>
          )}
        </div>
      </header>

      {isLanding ? (
        <Landing onOpenLibrary={() => navigate('/library')} />
      ) : (
        <main className="main">
          {page === 'library' && <Library />}
          {page === 'upload' && <Upload onUploaded={() => setPage('library')} />}
          {page === 'playlists' && <Playlists />}
          {page === 'compare' && <Compare />}
        </main>
      )}
    </div>
  );
}
