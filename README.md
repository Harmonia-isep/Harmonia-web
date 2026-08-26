# Harmonia

> Music Analysis & Library Management Platform  
> LEI-PROJ 2025/2026 · Instituto Superior de Engenharia do Porto

---

## Team

| Name | Role |
|------|------|
| Adam Abdelkefi | Backend, DSP Pipeline, Web Frontend |
| Inas Mezouri | Mobile App (Android) |

---

## About

Harmonia is a web-based platform that allows users to upload audio tracks and automatically extract musical properties such as BPM, key, scale, energy and danceability using digital signal processing (DSP). Users can manage their personal music library through a clean web interface, while a REST API exposes all functionality for the companion mobile app.

---

## Architecture

Three-tier architecture: React frontend communicates with a FastAPI backend over HTTP/REST. The backend handles business logic, DSP processing, and communicates with a PostgreSQL database for persistence and a local file system for audio storage. The mobile app (Ines) consumes the same REST API.

- **Client Tier** — React.js web app + Mobile app (Ines)
- **Server Tier** — FastAPI (Python 3.12), SQLAlchemy ORM, librosa DSP
- **Data Tier** — PostgreSQL 16 + File System (audio uploads)

---

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 16+
- Node.js 18+
- ffmpeg

### Setup

    git clone https://github.com/Harmonia-isep/Harmonia-web.git
    cd Harmonia-web
    pip install -e .
    alembic upgrade head

The database defaults to a local SQLite file (`harmonia.db`); set `DATABASE_URL` to a
Postgres URL to use Postgres instead.

### Running

**Single process (built frontend).** Build the React app once; one server then serves
both the UI and the API on a single origin:

    (cd frontend && npm install && npm run build)
    python3 -m uvicorn --factory backend.main:create_app --host 127.0.0.1 --port 8000

Then open http://127.0.0.1:8000.

**Development (separate frontend).** Run the API and the Create React App dev server
separately. CORS is enabled for the dev-server origin (`localhost:3000`) as a dev-only
convenience:

    python3 -m uvicorn --factory backend.main:create_app --reload --host 127.0.0.1 --port 8000
    # in another terminal:
    cd frontend && npm install && npm start

Both commands bind `127.0.0.1` (loopback), so the server is not exposed on your network.
If the frontend build is absent, the backend logs a warning and serves the API only.

### No accounts (local-first)

Harmonia is a local-first, single-user tool, so it has no authentication: no login, no
user accounts, no per-user data. On `127.0.0.1` an auth layer would be security theatre,
and removing it deletes the `User` model, ownership filtering, and a whole class of state.
This is a deliberate design decision, not a missing feature. To expose the server on a
LAN, put it behind your own reverse proxy and access control.

## DSP Analysis Pipeline

Each uploaded track is processed through the following pipeline:

1. **Audio Loading** — librosa loads the audio file with native sample rate
2. **BPM Detection** — beat tracking algorithm estimates tempo
3. **Key Detection** — chroma CQT features identify musical key
4. **Scale Detection** — correlation with major/minor profiles
5. **Energy** — RMS energy computed across the signal
6. **Danceability** — onset strength consistency metric

---

## Project Structure

    Harmonia-web/
    ├── backend/
    │   ├── api/
    │   │   ├── users.py        # User registration & auth
    │   │   ├── tracks.py       # Track upload & management
    │   │   └── analysis.py     # DSP analysis endpoints
    │   ├── audio/
    │   │   └── analyzer.py     # librosa DSP pipeline
    │   ├── models/
    │   │   ├── models.py       # SQLAlchemy DB models
    │   │   └── database.py     # DB connection & session
    │   └── main.py             # FastAPI app entry point
    ├── frontend/
    │   └── src/
    │       ├── components/
    │       │   ├── Auth.js     # Login & register
    │       │   ├── Library.js  # Music library view
    │       │   └── Upload.js   # Track upload
    │       ├── api.js          # API client
    │       └── App.js          # Main app & routing
    ├── .env                    # Environment variables
    ├── requirements.txt        # Python dependencies
    └── README.md

---

## Mobile App

The companion mobile app is developed by Ines Mezouri and lives in a separate repository:
[Harmonia-mobile](https://github.com/Harmonia-isep/Harmonia-mobile)

It consumes the same REST API documented above.

## License

MIT License — see LICENSE for details.    