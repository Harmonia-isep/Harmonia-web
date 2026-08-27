import React, { useState, useEffect } from 'react';
import { Activity, Library, Compass, ChevronDown, Upload, Music } from 'lucide-react';
import './Landing.css';

const DEMO_ANALYSIS = {
  bpm: 128,
  key: "A",
  scale: "minor",
  energy: 0.78,
  danceability: 0.85,
};

export default function Landing({ onTryFree, onOpenAuth }) {
  const [demoFile, setDemoFile] = useState(null);
  const [demoProgress, setDemoProgress] = useState(0);
  const [demoPhase, setDemoPhase] = useState('idle');
  const [demoDragOver, setDemoDragOver] = useState(false);

  // Scroll-reveal animation
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) entry.target.classList.add('visible');
        });
      },
      { threshold: 0.1 }
    );
    document.querySelectorAll('.fade-up').forEach(el => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  // Demo fake progress
  useEffect(() => {
    if (demoPhase !== 'analyzing') return;
    const interval = setInterval(() => {
      setDemoProgress(prev => {
        if (prev >= 95) return prev;
        return Math.min(95, prev + Math.max(0.5, (95 - prev) / 15));
      });
    }, 100);
    const timeout = setTimeout(() => {
      clearInterval(interval);
      setDemoProgress(100);
      setDemoPhase('done');
    }, 2500);
    return () => { clearInterval(interval); clearTimeout(timeout); };
  }, [demoPhase]);

  const handleDemoFile = (file) => {
    setDemoFile(file);
    setDemoProgress(0);
    setDemoPhase('analyzing');
  };

  const resetDemo = () => {
    setDemoPhase('idle');
    setDemoFile(null);
    setDemoProgress(0);
  };

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  // Showcase waveform bars (deterministic pattern)
  const showcaseBars = Array.from({ length: 48 }, (_, i) => {
    const h = 30 + Math.sin(i * 0.4) * 25 + Math.cos(i * 0.7) * 15;
    return <span key={i} style={{ height: `${Math.max(8, h)}%` }} />;
  });

  return (
    <div className="landing">

      {/* ===== HERO ===== */}
      <section className="landing-section hero">
        <div className="hero-content">
          <h1 className="hero-headline fade-up">Understand every song.</h1>
          <p className="hero-subhead fade-up">
            Drop in a track. Get its BPM, key, energy, and harmonic profile in seconds.
          </p>
          <div className="hero-buttons fade-up">
            <button className="hero-btn-primary" onClick={onTryFree}>Try it free</button>
            <button className="hero-btn-secondary" onClick={() => scrollTo('how')}>
              See how it works <ChevronDown size={14} />
            </button>
          </div>
          <p className="hero-muted fade-up">Free forever. No credit card.</p>
        </div>
        <div className="hero-visual fade-up">
          <div className="hero-waveform">
            <svg viewBox="0 0 600 200" fill="none">
              <defs>
                <linearGradient id="wg1" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#ff3b30" stopOpacity="0" />
                  <stop offset="50%" stopColor="#ff3b30" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#ff3b30" stopOpacity="0" />
                </linearGradient>
                <linearGradient id="wg2" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#ff3b30" stopOpacity="0" />
                  <stop offset="50%" stopColor="#ff3b30" stopOpacity="0.18" />
                  <stop offset="100%" stopColor="#ff3b30" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path className="wave-1"
                d="M0,100 Q75,30 150,100 Q225,170 300,100 Q375,30 450,100 Q525,170 600,100"
                stroke="url(#wg1)" strokeWidth="2" />
              <path className="wave-2"
                d="M0,100 Q75,55 150,100 Q225,145 300,100 Q375,55 450,100 Q525,145 600,100"
                stroke="url(#wg2)" strokeWidth="1.5" />
            </svg>
          </div>
        </div>
      </section>

      {/* ===== DEMO ===== */}
      <section className="landing-section demo-section" id="demo">
        <h2 className="section-headline fade-up">Try it now.</h2>
        <p className="section-subhead fade-up">Drop an audio file below. No signup required.</p>

        {demoPhase === 'idle' && (
          <div
            className={`demo-drop-zone fade-up visible ${demoDragOver ? 'drag-over' : ''}`}
            onClick={() => document.getElementById('demoFileInput').click()}
            onDragOver={(e) => { e.preventDefault(); setDemoDragOver(true); }}
            onDragLeave={() => setDemoDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDemoDragOver(false); if (e.dataTransfer.files[0]) handleDemoFile(e.dataTransfer.files[0]); }}
          >
            <Upload size={32} className="demo-drop-zone-icon" />
            <p>Drop an MP3 or WAV</p>
            <span className="hint">or click to browse</span>
            <input
              id="demoFileInput"
              type="file"
              accept="audio/*"
              hidden
              onChange={(e) => e.target.files[0] && handleDemoFile(e.target.files[0])}
            />
          </div>
        )}

        {demoPhase === 'analyzing' && (
          <div className="demo-file-info">
            <p className="demo-filename">{demoFile?.name}</p>
            <div className="demo-progress">
              <div className="demo-progress-bar" style={{ width: `${demoProgress}%` }} />
            </div>
            <p className="demo-progress-text">Analyzing... {Math.round(demoProgress)}%</p>
          </div>
        )}

        {demoPhase === 'done' && (
          <>
            <div className="demo-result">
              <h3>{demoFile?.name}</h3>
              <div className="demo-metrics">
                <div className="demo-metric">
                  <span className="demo-metric-label">BPM</span>
                  <span className="demo-metric-value">{DEMO_ANALYSIS.bpm}</span>
                </div>
                <div className="demo-metric">
                  <span className="demo-metric-label">Key</span>
                  <span className="demo-metric-value">{DEMO_ANALYSIS.key} {DEMO_ANALYSIS.scale}</span>
                </div>
                <div className="demo-metric">
                  <span className="demo-metric-label">Energy</span>
                  <span className="demo-metric-value">{(DEMO_ANALYSIS.energy * 100).toFixed(0)}%</span>
                </div>
                <div className="demo-metric">
                  <span className="demo-metric-label">Danceability</span>
                  <span className="demo-metric-value">{(DEMO_ANALYSIS.danceability * 100).toFixed(0)}%</span>
                </div>
              </div>
              <div className="demo-footer">
                <p>Demo analysis. Sign up to analyze your actual tracks.</p>
                <button className="demo-signup-btn" onClick={() => onOpenAuth('register')}>Sign up free</button>
              </div>
            </div>
            <button className="demo-retry" onClick={resetDemo}>Try another track</button>
          </>
        )}
      </section>

      {/* ===== FEATURES ===== */}
      <section className="landing-section" id="features">
        <div className="features-grid">
          <div className="feature-card fade-up">
            <Activity size={24} color="#ff3b30" />
            <h3>Precision analysis</h3>
            <p>Industry-standard DSP techniques extract BPM, key, and harmonic features with confidence scores.</p>
          </div>
          <div className="feature-card fade-up">
            <Library size={24} color="#ff3b30" />
            <h3>Your library, organized</h3>
            <p>Upload once, search forever. Filter by BPM, key, genre, or energy.</p>
          </div>
          <div className="feature-card fade-up">
            <Compass size={24} color="#ff3b30" />
            <h3>Built for the curious</h3>
            <p>Whether you're a DJ, producer, or obsessive listener, Harmonia speaks your language.</p>
          </div>
        </div>
      </section>

      {/* ===== HOW IT WORKS ===== */}
      <section className="landing-section" id="how">
        <div className="how-steps">
          <div className="how-step fade-up">
            <span className="how-number">01</span>
            <h3>Upload</h3>
            <p>Drag in MP3 or WAV files. Batch upload supported.</p>
          </div>
          <div className="how-step fade-up">
            <span className="how-number">02</span>
            <h3>Analyze</h3>
            <p>Our pipeline extracts every feature you need in seconds.</p>
          </div>
          <div className="how-step fade-up">
            <span className="how-number">03</span>
            <h3>Explore</h3>
            <p>Browse, search, and discover connections across your library.</p>
          </div>
        </div>
      </section>

      {/* ===== SHOWCASE ===== */}
      <section className="landing-section showcase-section">
        <h2 className="section-headline fade-up">See every song, clearly.</h2>
        <div className="showcase-mockup fade-up">
          <div className="showcase-header">
            <div className="showcase-icon">
              <Music size={24} />
            </div>
            <div>
              <div className="showcase-title">Midnight City</div>
              <div className="showcase-artist">M83</div>
            </div>
          </div>
          <div className="showcase-metrics">
            <div className="showcase-metric">
              <span className="showcase-label">BPM</span>
              <span className="showcase-value">105</span>
            </div>
            <div className="showcase-metric">
              <span className="showcase-label">Key</span>
              <span className="showcase-value">A minor</span>
            </div>
            <div className="showcase-metric">
              <span className="showcase-label">Energy</span>
              <span className="showcase-value">72%</span>
            </div>
            <div className="showcase-metric">
              <span className="showcase-label">Danceability</span>
              <span className="showcase-value">68%</span>
            </div>
          </div>
          <div className="showcase-waveform">
            {showcaseBars}
          </div>
        </div>
      </section>

      {/* ===== FINAL CTA ===== */}
      <section className="landing-section cta-section">
        <div className="cta-content fade-up">
          <h2 className="cta-headline">Ready to hear your library differently?</h2>
          <button className="cta-btn" onClick={onTryFree}>Get started — it's free</button>
          <button className="cta-link" onClick={() => onOpenAuth('login')}>Or log in &#8594;</button>
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer className="landing-footer">
        <div className="footer-inner">
          <div className="footer-col">
            <h4>Product</h4>
            <a href="#features" onClick={(e) => { e.preventDefault(); scrollTo('features'); }}>Features</a>
            <a href="#how" onClick={(e) => { e.preventDefault(); scrollTo('how'); }}>How it works</a>
            <a href="#demo" onClick={(e) => { e.preventDefault(); scrollTo('demo'); }}>Demo</a>
          </div>
          <div className="footer-col">
            <h4>Resources</h4>
            <a href="https://github.com/Harmonia-isep/Harmonia-web" target="_blank" rel="noopener noreferrer">GitHub</a>
          </div>
          <div className="footer-col">
            <h4>Legal</h4>
            <a href="#" onClick={(e) => e.preventDefault()}>Privacy</a>
            <a href="#" onClick={(e) => e.preventDefault()}>Terms</a>
          </div>
          <div className="footer-col footer-brand">
            <span className="footer-logo">Harmonia</span>
            <span className="footer-copy">&copy; 2026 Harmonia</span>
            <span className="footer-tagline">Understand every song.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
