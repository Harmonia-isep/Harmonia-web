import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import analysis, playlists, tracks, users
from backend.models.database import engine
from backend.models.models import Base

Base.metadata.create_all(bind=engine)

os.makedirs("uploads", exist_ok=True)

app = FastAPI(title="Harmonia API", version="1.0.0")

_default_cors = "http://localhost:3000,http://127.0.0.1:3000"
cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", _default_cors).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(tracks.router, prefix="/api/tracks", tags=["tracks"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(playlists.router, prefix="/api/playlists", tags=["playlists"])

@app.get("/")
def root():
    return {"message": "Harmonia API is running"}
