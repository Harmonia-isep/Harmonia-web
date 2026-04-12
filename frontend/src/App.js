import React, { useState } from 'react';
import Auth from './components/Auth';
import Library from './components/Library';
import Upload from './components/Upload';
import './App.css';

export default function App() {
  const [user, setUser] = useState(null);
  const [page, setPage] = useState('library');

  if (!user) return <Auth onLogin={setUser} />;

  return (
    <div className="app">
      <header className="header">
        <h1 className="logo">🎵 Harmonia</h1>
        <nav>
          <button className={page === 'library' ? 'active' : ''} onClick={() => setPage('library')}>Library</button>
          <button className={page === 'upload' ? 'active' : ''} onClick={() => setPage('upload')}>Upload</button>
          <button className="logout" onClick={() => setUser(null)}>Logout ({user.username})</button>
        </nav>
      </header>
      <main className="main">
        {page === 'library' && <Library user={user} />}
        {page === 'upload' && <Upload user={user} onUploaded={() => setPage('library')} />}
      </main>
    </div>
  );
}
