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

### Backend Setup

Clone the repo:

    git clone https://github.com/Harmonia-isep/Harmonia-web.git
    cd Harmonia-web

Install Python dependencies:

    pip3 install fastapi uvicorn sqlalchemy psycopg2-binary python-multipart librosa numpy scipy python-dotenv --break-system-packages

Create the database:

    sudo -u postgres psql -c "CREATE USER harmonia_user WITH PASSWORD 'harmonia123';"
    sudo -u postgres psql -c "CREATE DATABASE harmonia_db OWNER harmonia_user;"

Create .env file:

    echo "DATABASE_URL=postgresql://harmonia_user:harmonia123@localhost/harmonia_db" > .env

Start the server:

    python3 -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

### Frontend Setup

    cd frontend
    npm install
    npm 
    

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