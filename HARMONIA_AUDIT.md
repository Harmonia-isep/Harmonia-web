# Harmonia — Codebase Audit

Read-only audit. Generated 2026-08-25.

## 1. Repo and history

- **Branch:** `develop`
- **Latest commit:** `1c865f3c140b0d37e794c40a5ddea8634da54d98` — *fix(tracks): remove analysis and playlist entries on track deletion*
- **Working tree:** NOT clean. 5 entries:
  - `M frontend/.env`
  - `M frontend/package-lock.json`
  - `?? coverage.json`
  - `?? docs/`
  - `?? frontend/.env.render`
- **Tags / releases:** absent (0 tags).

### Committed secrets (locations only)
| Type | File | Commit |
|------|------|--------|
| Postgres URL w/ inline password (`postgresql://…:…@localhost/harmonia_db`, a *dev/localhost* credential) | `README.md` | `702d8bb` *docs: full README with setup* |
| Backend API endpoint URL (`*.onrender.com`) — not a secret, but a hardcoded env value | `frontend/.env` | `deee67a` *use REACT_APP_API_URL for backend URL* |

- No production Neon URL, `SECRET_KEY`, `API_KEY`, or `Bearer` token found anywhere in history. The production `DATABASE_URL`/`SECRET_KEY` live only in the untracked root `.env`.

### .env tracking
- **`.env` tracked?** `frontend/.env` IS tracked (contains `REACT_APP_API_URL`). Root `.env` is NOT tracked. Note: `.gitignore` lists `.env` (lines 138, 209) but `frontend/.env` was committed before being ignored, so git keeps tracking it.
- **`.env.example`?** absent (none at root, backend, or frontend). An untracked `frontend/.env.render` exists on disk only.

## 2. Persistence layer

### Models (`backend/models/models.py`)
- **User** (`users`): `id` Integer PK, `username` String unique not-null, `password_hash` String not-null, `created_at` DateTime.
- **Track** (`tracks`): `id` Integer PK, `title` String not-null, `artist` String, `album` String, `file_path` String not-null, `artwork_path` String, `duration` Float, `uploaded_at` DateTime, `user_id` Integer FK→users.id.
- **Analysis** (`analyses`): `id` Integer PK, `track_id` Integer FK→tracks.id, `bpm` Float, `key` String, `scale` String, `energy` Float, `danceability` Float, `analyzed_at` DateTime.
- **Playlist** (`playlists`): `id` Integer PK, `name` String not-null, `user_id` Integer FK→users.id, `share_token` String unique, `created_at` DateTime.
- **PlaylistTrack** (`playlist_tracks`): `id` Integer PK, `playlist_id` Integer FK→playlists.id, `track_id` Integer FK→tracks.id, `position` Integer default 0.

Note: `Text` is imported (models.py:1) but never used.

- **`sqlalchemy.dialects.postgresql` imports (ARRAY/JSONB/UUID/…):** absent — no occurrences. All columns use generic types.
- **Raw SQL strings:** absent — everything goes through the ORM. Only `Base.metadata.create_all(bind=engine)` (main.py:8).
- **Migrations:** Alembic absent. Schema is created via `Base.metadata.create_all(bind=engine)` (main.py:8). No migration versioning of any kind.
- **DATABASE_URL resolution:** env var via `python-dotenv`, `backend/models/database.py:6-10`:
  ```python
  load_dotenv()
  DATABASE_URL = os.getenv("DATABASE_URL")
  engine = create_engine(DATABASE_URL)
  ```
  No default/fallback — if unset, `create_engine(None)` fails at import. (Tests set `DATABASE_URL=sqlite://` in `conftest.py` before import.)

### ForeignKey definitions & ondelete
All FKs are plain `ForeignKey(...)` with **no `ondelete`** setting (default NO ACTION):
- `Track.user_id` → `users.id` (models.py:26)
- `Analysis.track_id` → `tracks.id` (models.py:33)
- `Playlist.user_id` → `users.id` (models.py:48)
- `PlaylistTrack.playlist_id` → `playlists.id` (models.py:60)
- `PlaylistTrack.track_id` → `tracks.id` (models.py:61)

Cascade deletion is done **manually in app code** (see `delete_track`, `delete_playlist`), not by the DB.

## 3. DSP pipeline

### File tree of the DSP/analysis module
```
backend/audio/
├── __init__.py        (empty)
├── analyzer.py        (analyze_audio — BPM/key/scale/energy/danceability)
└── artwork.py         (embedded album-art extraction)
backend/api/analysis.py  (spectrum FFT endpoint + Camelot engine)
```

### Key/scale detection (`backend/audio/analyzer.py`, inside `analyze_audio`)
```python
        # Key detection. We use chroma_stft (FFT-based) instead of chroma_cqt:
        # the CQT is far more memory-hungry, and the STFT version gives
        # essentially the same key result at a fraction of the RAM.
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        chroma_mean = chroma.mean(axis=1)
        key_index = int(np.argmax(chroma_mean))
        key = KEYS[key_index]

        # Major vs minor - correlate the chroma against major/minor templates
        major_profile = np.array([1,0,1,0,1,1,0,1,0,1,0,1], dtype=float)
        minor_profile = np.array([1,0,1,1,0,1,0,1,1,0,1,0], dtype=float)
        major_corr = np.corrcoef(chroma_mean, np.roll(major_profile, key_index))[0,1]
        minor_corr = np.corrcoef(chroma_mean, np.roll(minor_profile, key_index))[0,1]
        scale = "major" if major_corr > minor_corr else "minor"
```

### BPM/beat detection (`backend/audio/analyzer.py`)
```python
        # Compute the onset envelope ONCE - both BPM and danceability use it.
        # Reusing it avoids running the expensive beat tracker twice.
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset_env, sr=sr)
        bpm = round(float(tempo[0]))
```

### Energy and danceability (`backend/audio/analyzer.py`)
```python
        # Energy - blend loudness (RMS) with brightness (spectral centroid)
        rms_mean = float(np.mean(librosa.feature.rms(y=y)))
        loudness = min(1.0, rms_mean / 0.3)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        brightness = min(1.0, float(np.mean(centroid)) / 4000.0)
        energy = float(round(0.6 * loudness + 0.4 * brightness, 4))

        # Danceability - blend beat steadiness with pulse strength (punch),
        # reusing the onset envelope and beats we already computed above.
        if len(beat_frames) > 2:
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)
            intervals = np.diff(beat_times)

            cv = np.std(intervals) / (np.mean(intervals) + 1e-6)
            steadiness = max(0.0, min(1.0, 1.0 - cv))

            beat_strength = np.mean(onset_env[beat_frames])
            overall = np.mean(onset_env) + 1e-6
            punch = beat_strength / overall
            punch = max(0.0, min(1.0, (punch - 3.0) / 6.0))

            danceability = float(round(0.8 * punch + 0.2 * steadiness, 4))
        else:
            danceability = 0.0
```

### Hardcoded DSP constants
| Constant | Value | file:line |
|----------|-------|-----------|
| load sr | 22050 | analyzer.py:12 |
| load duration | 45 s | analyzer.py:12 |
| loudness normaliser | RMS / 0.3 | analyzer.py:37 |
| brightness normaliser | centroid / 4000.0 | analyzer.py:39 |
| energy weights | 0.6·loudness + 0.4·brightness | analyzer.py:40 |
| punch rescale | (punch − 3.0) / 6.0 | analyzer.py:54 |
| danceability weights | 0.8·punch + 0.2·steadiness | analyzer.py:56 |
| spectrum load sr | 22050 | analysis.py:70 |
| spectrum load duration | 30 s | analysis.py:70 |
| spectrum num_bands | 64 | analysis.py:78 |
| spectrum max_freq | 16000 Hz | analysis.py:79 |
| spectrum log band edges | logspace(20, 16000, 65) | analysis.py:87 |
| dB floor epsilon | 1e-6 | analysis.py:102 |
| upload size cap | 20 MB | tracks.py:36 |
- **n_fft, hop_length, n_chroma:** absent as explicit constants — `chroma_stft`, `rms`, `spectral_centroid`, `onset_strength` all rely on librosa defaults (n_fft=2048, hop_length=512, n_chroma=12).

### Beat array persistence
- **Discarded.** `beat_frames` is used only in-function for danceability (steadiness/punch). Only the scalar `bpm` is persisted to `Analysis.bpm`. The beat array is never stored.

### Installed DSP versions (WSL runtime + requirements.txt — they match)
- librosa **0.11.0**, numpy **2.4.4**, scipy **1.17.1**, soundfile **0.13.1**.

## 4. Audio file handling

### Upload → storage → analysis → deletion trace
Endpoint handler (`backend/api/tracks.py:13-58`):
```python
@router.post("/upload")
async def upload_track(
    file: UploadFile = File(...),
    title: str = Form(...),
    artist: str = Form(None),
    album: str = Form(None),
    user_id: int = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    ...
    max_size = 20 * 1024 * 1024  # 20 MB
    if os.path.getsize(file_path) > max_size:
        os.remove(file_path)
        raise HTTPException(status_code=413, ...)

    artwork_path = extract_artwork(file_path)

    track = Track(title=title, artist=artist, album=album,
                  file_path=file_path, artwork_path=artwork_path, user_id=user_id)
    db.add(track); db.commit(); db.refresh(track)
    return {"id": track.id, "title": track.title, "file_path": track.file_path}
```
- **Temp storage:** none. File is written directly to `UPLOAD_DIR = "uploads"` under a UUID filename (tracks.py:11, 27-31). Size is checked *after* the full write; oversized files are deleted post-write.
- **Analysis** is a *separate* request (`POST /api/analysis/analyze/{track_id}`), not part of upload.
- **Deletion** happens only via `DELETE /api/tracks/{track_id}` (`os.remove(track.file_path)`, tracks.py:110-111). Analysis never deletes the source file.

### Long-term persistence / path & hash columns
- Audio **is persisted long-term** on the server's `uploads/` directory (survives until explicit track deletion).
- `Track.file_path` (String, not-null) stores the path. `Track.artwork_path` stores extracted art. **No hash column** on Track (no dedup/content-addressing). No checksum anywhere.

### Analysis: synchronous or offloaded?
Offloaded via FastAPI `BackgroundTasks` (`backend/api/analysis.py:10-37`):
```python
@router.post("/analyze/{track_id}")
async def analyze_track(track_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    track = db.query(Track).filter(Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    if not os.path.exists(track.file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    background_tasks.add_task(run_analysis, track_id, track.file_path, db)
    return {"message": "Analysis started", "track_id": track_id}

def run_analysis(track_id: int, file_path: str, db: Session):
    from backend.models.database import SessionLocal
    db = SessionLocal()   # NOTE: the passed-in `db` arg is shadowed/ignored
    try:
        result = analyze_audio(file_path)
        existing = db.query(Analysis).filter(Analysis.track_id == track_id).first()
        if existing:
            existing.bpm = result["bpm"]; existing.key = result["key"]
            existing.scale = result["scale"]; existing.energy = result["energy"]
            existing.danceability = result["danceability"]
        else:
            analysis = Analysis(track_id=track_id, **result)
            db.add(analysis)
        db.commit()
    finally:
        db.close()
```
`BackgroundTasks` runs *in-process after the response is sent* (same event loop / threadpool) — not a separate worker/queue.

### Job/task/status table or registry
- **Absent.** No job table, no in-memory registry, no status field. The client discovers completion by polling `GET /api/analysis/{track_id}` until it flips from 404 → 200 (see commit *extend analysis polling for slow free-tier hosting*).

## 5. Camelot engine

### Recommendation generator (`backend/api/analysis.py:196-239`)
```python
@router.get("/{track_id}/recommendations")
def get_recommendations(track_id: int, db: Session = Depends(get_db)):
    source = db.query(Analysis).filter(Analysis.track_id == track_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="No analysis for this track")

    source_track = db.query(Track).filter(Track.id == track_id).first()
    source_code = to_camelot(source.key, source.scale)

    # look at every other analyzed track belonging to the same user
    others = db.query(Analysis).filter(Analysis.track_id != track_id).all()

    recommendations = []
    for other in others:
        other_track = db.query(Track).filter(Track.id == other.track_id).first()
        # only recommend tracks owned by the same user
        if not other_track or other_track.user_id != source_track.user_id:
            continue

        bpm_close = abs((other.bpm or 0) - (source.bpm or 0)) <= 5
        other_code = to_camelot(other.key, other.scale)
        key_ok = camelot_compatible(source_code, other_code)

        if bpm_close and key_ok:
            recommendations.append({
                "track_id": other_track.id, "title": other_track.title,
                "artist": other_track.artist, "bpm": other.bpm,
                "key": other.key, "scale": other.scale, "camelot": other_code,
            })

    return {"track_id": track_id, "camelot": source_code, "recommendations": recommendations}
```

### N+1
- `analysis.py:207` loads **all** `Analysis` rows across **all users** (`Analysis.track_id != track_id`), then the loop at `analysis.py:210` issues a per-iteration `db.query(Track)...` at **`analysis.py:211`** — one Track query per candidate analysis. User-ownership is filtered in Python *after* the query, so cross-user rows are fetched then discarded.

### Camelot adjacency: runtime or DB?
- **Runtime.** `to_camelot` uses two module-level Python dicts (`CAMELOT_MINOR`, `CAMELOT_MAJOR`, analysis.py:121-150); `camelot_compatible` (analysis.py:163-192) computes the three adjacency rules arithmetically each call. Nothing about the wheel is stored in the DB.

## 6. Auth coupling

### User model (`backend/models/models.py:8-14`)
```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    tracks = relationship("Track", back_populates="owner")
```

### Password hashing (`backend/api/users.py:19-20`)
```python
def hash_password(password: str):
    return hashlib.sha256(password.encode()).hexdigest()
```
Unsalted SHA-256. `login` compares `user.password_hash != hash_password(...)` (users.py:48). Guest users are created with `password_hash=""` (users.py:25). **No JWT/session/token** is issued — `login` just returns `user_id` in the JSON body.

### Models with a user_id FK
- `Track.user_id` (models.py:26)
- `Playlist.user_id` (models.py:48)
(`Analysis` and `PlaylistTrack` have no user_id — they inherit ownership through Track/Playlist.)

### Endpoints that read a current user / user_id
There is **no `get_current_user` / auth dependency anywhere** — "current user" is always a client-supplied `user_id` param. Occurrences:
- `users.py`: `/guest` (creates user), `/register`, `/login`, `/{user_id}` (get_user)
- `tracks.py:13` `POST /upload` (user_id Form), `tracks.py:22` looks up User
- `tracks.py:60` `GET /user/{user_id}`, `tracks.py:120` `GET /user/{user_id}/export`
- `playlists.py:11` `POST /create` (user_id), `playlists.py:23` `GET /user/{user_id}`
- `analysis.py:213` `get_recommendations` reads `source_track.user_id` / `other_track.user_id` to scope recommendations

### Test blast-radius if User were removed
Total: **5 test files, 35 `def test_` functions (53 collected pytest items** after `test_acceptance` parametrizes into 19).

Auth coupling is pervasive — every file touches it at least by import:
| File | test fns | Breakage if auth/User deleted |
|------|----------|-------------------------------|
| `test_unit.py` | 18 | Module-level `from backend.api.users import hash_password` → **all 18 error on import** (though only the 3 `TestPasswordHashing` tests are conceptually auth-related; the 15 Camelot/DSP tests break only via the shared import line). |
| `test_integration.py` | 7 | 6 break (register/login shape + all that seed via `/register`); only `test_root_health` survives. |
| `test_analysis_paths.py` | 7 | Module-level `from ...models import User` + `_make_user_and_track` → **all 7 error**. |
| `test_acceptance.py` | 1 (19 params) | The one parametrized fn; 17 of 19 stories need a user (all but US13 DSP, US16 Camelot). |
| `test_e2e.py` | 2 | Both drive the guest/auth UI → both break. |

Net: **all 5 test files** are coupled; effectively **~34 of 35 test functions** (≈51 of 53 items) would fail — only `test_root_health` is fully auth-independent.

### Current test count & coverage (`pytest --cov=backend`)
```
53 passed in 22.63s      |      TOTAL  493 stmts  80 miss  84%
```

## 7. Frontend and packaging

- **Frontend build tool:** Create React App (**`react-scripts` 5.0.1**), NOT Vite. React 19.2, react-router-dom 7, axios, lucide-react.
- Scripts block (`frontend/package.json`):
  ```json
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test",
    "eject": "react-scripts eject"
  }
  ```
- **Backend serving static files?** No. `backend/main.py` mounts no `StaticFiles` and serves no build. Frontend is a **fully separate** SPA (talks to the API via `REACT_APP_API_URL`). The only place the build is served is inside `test_e2e.py`, via a throwaway `http.server`.
- **CORS:** `backend/main.py:14-20` — wide open:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
  (`allow_origins=["*"]` + `allow_credentials=True` is a contradictory/insecure combo browsers reject for credentialed requests.)
- **Dependency management:** `requirements.txt` only (49 pinned lines). No `pyproject.toml`, no Poetry/Pipenv/uv. Backend has **no lockfile**. Frontend has `package-lock.json` (present, currently modified).
- **Python version:** 3.12.3 (WSL runtime used for the test run).
- **CI:** `.github/workflows` absent — no GitHub Actions / CI of any kind.

---

## SURPRISES
Things a plan written from memory would likely get wrong:

1. **The auth stack is fake-heavy.** `requirements.txt` pins `bcrypt`, `passlib`, `python-jose`, `ecdsa`, `rsa` — a full JWT/password-hashing stack — but **none are imported**. Real auth is unsalted `hashlib.sha256` and login returns a bare `user_id`. There is **no token/session and no `get_current_user`** — deleting auth is mechanically easy (no middleware to unwind), but you must remove those unused deps too.
2. **`SECRET_KEY` and `UPLOAD_FOLDER` in `.env` are dead.** No code references `SECRET_KEY`; `UPLOAD_DIR` is hardcoded to `"uploads"` in tracks.py, ignoring `UPLOAD_FOLDER`.
3. **`docker-compose.yml` is an empty (0-byte) file** despite existing and being tracked.
4. **No migrations at all** — schema is `create_all` at import. Changing a model requires manually altering the live Neon DB (or dropping it). No Alembic to lean on.
5. **`frontend/.env` is tracked and currently modified**, even though `.gitignore` lists `.env`. It carries the production `onrender.com` API URL. Root `.env` (the real secrets) is correctly untracked.
6. **FK deletes are app-managed, not DB-managed.** No `ondelete` anywhere; `delete_track`/`delete_playlist` hand-delete children. On SQLite (tests) FKs aren't even enforced, so a missed manual cleanup would pass tests but orphan rows on Postgres.
7. **`run_analysis(track_id, file_path, db)` ignores its `db` argument** — it reopens `SessionLocal()` internally. The passed session is dead weight (and would be closed by the time the BackgroundTask runs).
8. **Analysis has no job/status tracking.** "Async" is FastAPI `BackgroundTasks` (in-process, post-response); the client polls the analysis GET until 404→200. On a single free-tier worker this competes with request handling.
9. **Recommendations scan every user's analyses**, then filter ownership in Python — both an N+1 (per-candidate Track query, analysis.py:211) and a cross-tenant over-fetch.
10. **CORS is `allow_origins=["*"]` with `allow_credentials=True`** — self-contradictory and a finding in its own right.
11. **A localhost Postgres password is committed in `README.md`** history (`702d8bb`). Low sensitivity (dev creds) but present.
12. **`Text` is imported in models.py but unused;** no model uses it — a hint the schema was trimmed down from something larger.
13. **53 pytest items but only 35 `def test_` functions** — `test_acceptance.py` is a single parametrized function expanding to 19 user-story cases (US01–US19). Coverage (84%) is real and the suite genuinely runs the DSP on synthesized audio (nothing mocked), so it's slower (~23s) than a unit-only suite.
