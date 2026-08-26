# Acceptance tests: the surviving user-story criteria. The auth stories US01-US06
# were removed with authentication (Phase 3). One parametrized case each; every check
# drives the real application (HTTP endpoints, DSP, or pure logic). Because tracks are
# no longer user-scoped, list/filter checks that share the session database use
# membership assertions rather than exact equality.

import io

import numpy as np
import pytest
import soundfile as sf

from backend.api.analysis import camelot_compatible, to_camelot
from backend.audio.analyzer import analyze_audio
from backend.models.models import Analysis, Playlist, PlaylistTrack, Track


def _wav_bytes(freq=440.0, sr=22050, dur=2.0):
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    y = 0.5 * np.sin(2 * np.pi * freq * t)
    buf = io.BytesIO()
    sf.write(buf, y.astype(np.float32), sr, format="WAV")
    return buf.getvalue()


# --- one function per user story ---------------------------------------------

def us07_upload_track(client, db):
    r = client.post(
        "/api/tracks/upload",
        files={"file": ("song.wav", _wav_bytes(), "audio/wav")},
        data={"title": "My Song"},
    )
    assert r.status_code == 200 and r.json()["title"] == "My Song"


def us08_oversized_upload_rejected(client, db):
    big = b"\0" * (21 * 1024 * 1024)  # 21 MB, over the 20 MB cap
    r = client.post(
        "/api/tracks/upload",
        files={"file": ("big.mp3", big, "audio/mpeg")},
        data={"title": "Too Big"},
    )
    assert r.status_code == 413


def us09_view_library(client, db):
    db.add(Track(title="Lib Song", file_path="uploads/a.mp3"))
    db.commit()
    r = client.get("/api/tracks/")
    assert r.status_code == 200 and any(t["title"] == "Lib Song" for t in r.json())


def us10_search_by_title(client, db):
    db.add(Track(title="Sunset Drive", file_path="uploads/s1.mp3"))
    db.add(Track(title="Rainy Day", file_path="uploads/s2.mp3"))
    db.commit()
    r = client.get("/api/tracks/", params={"search": "sunset"})
    titles = [t["title"] for t in r.json()]
    assert titles == ["Sunset Drive"]


def us11_filter_by_key_and_bpm(client, db):
    t1 = Track(title="Match", file_path="uploads/m1.mp3")
    t2 = Track(title="NoMatch", file_path="uploads/m2.mp3")
    db.add_all([t1, t2])
    db.commit()
    db.refresh(t1)
    db.refresh(t2)
    db.add(Analysis(track_id=t1.id, bpm=120, key="A", scale="minor"))
    db.add(Analysis(track_id=t2.id, bpm=90, key="C", scale="major"))
    db.commit()
    r = client.get("/api/tracks/", params={"key": "A", "bpm_min": 115, "bpm_max": 125})
    titles = [t["title"] for t in r.json()]
    assert "Match" in titles and "NoMatch" not in titles


def us12_track_detail_includes_analysis(client, db):
    track = Track(title="Detail", file_path="uploads/d.mp3")
    db.add(track)
    db.commit()
    db.refresh(track)
    db.add(Analysis(track_id=track.id, bpm=128, key="G", scale="minor"))
    db.commit()
    r = client.get(f"/api/tracks/{track.id}")
    assert r.status_code == 200 and r.json()["analysis"] is not None


def us13_dsp_extracts_all_descriptors(client, db):
    sr, dur, freq = 22050, 2.0, 440.0
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    import os
    import tempfile
    path = os.path.join(tempfile.gettempdir(), "us13.wav")
    sf.write(path, (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32), sr)
    result = analyze_audio(path)
    for field in ("bpm", "key", "scale", "energy", "danceability"):
        assert field in result


def us14_get_analysis_via_api(client, db):
    track = Track(title="Ana", file_path="uploads/an.mp3")
    db.add(track)
    db.commit()
    db.refresh(track)
    db.add(Analysis(track_id=track.id, bpm=124, key="D", scale="major",
                    energy=0.6, danceability=0.7))
    db.commit()
    r = client.get(f"/api/analysis/{track.id}")
    assert r.status_code == 200 and r.json()["bpm"] == 124


def us15_harmonic_recommendations(client, db):
    src = Track(title="Src15", file_path="uploads/rs.mp3")
    good = Track(title="Good15", file_path="uploads/rg.mp3")
    db.add_all([src, good])
    db.commit()
    db.refresh(src)
    db.refresh(good)
    db.add(Analysis(track_id=src.id, bpm=120, key="A", scale="minor"))
    db.add(Analysis(track_id=good.id, bpm=121, key="A", scale="minor"))
    db.commit()
    r = client.get(f"/api/analysis/{src.id}/recommendations")
    titles = [rec["title"] for rec in r.json()["recommendations"]]
    assert "Good15" in titles


def us16_camelot_mapping(client, db):
    assert to_camelot("A", "minor") == "8A"
    assert to_camelot("C", "major") == "8B"
    assert camelot_compatible("12A", "1A") is True   # wheel wrap


def us17_create_and_share_playlist(client, db):
    track = Track(title="PL Track", file_path="uploads/pl.mp3")
    db.add(track)
    db.commit()
    db.refresh(track)
    created = client.post("/api/playlists/create", params={"name": "My Set"}).json()
    client.post(f"/api/playlists/{created['id']}/add/{track.id}")
    shared = client.get(f"/api/playlists/shared/{created['share_token']}")
    assert shared.status_code == 200
    assert shared.json()["name"] == "My Set"
    assert any(t["title"] == "PL Track" for t in shared.json()["tracks"])


def us18_export_library_csv(client, db):
    db.add(Track(title="Export Me", file_path="uploads/e.mp3"))
    db.commit()
    r = client.get("/api/tracks/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "Title" in r.text and "Export Me" in r.text


def us19_delete_track(client, db):
    track = Track(title="Delete Me", file_path="uploads/del.mp3")
    db.add(track)
    db.commit()
    db.refresh(track)
    tid = track.id

    # give the track an analysis and a playlist entry, so deletion must clean both
    db.add(Analysis(track_id=tid, bpm=120, key="A", scale="minor",
                    energy=0.5, danceability=0.4))
    playlist = Playlist(name="Del PL", share_token="deltok19")
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    db.add(PlaylistTrack(playlist_id=playlist.id, track_id=tid, position=0))
    db.commit()

    assert client.delete(f"/api/tracks/{tid}").status_code == 200
    assert client.get(f"/api/tracks/{tid}").status_code == 404

    # dependent rows must be gone, not orphaned
    db.expire_all()
    assert db.query(Analysis).filter(Analysis.track_id == tid).first() is None
    assert db.query(PlaylistTrack).filter(PlaylistTrack.track_id == tid).first() is None


STORIES = [
    ("US07", "User can upload an audio track", us07_upload_track),
    ("US08", "Oversized uploads are rejected", us08_oversized_upload_rejected),
    ("US09", "User can view the library", us09_view_library),
    ("US10", "User can search the library by title", us10_search_by_title),
    ("US11", "User can filter by key and BPM range", us11_filter_by_key_and_bpm),
    ("US12", "Track detail shows its analysis", us12_track_detail_includes_analysis),
    ("US13", "DSP extracts BPM, key, scale, energy, danceability", us13_dsp_extracts_all_descriptors),
    ("US14", "Analysis is retrievable via the API", us14_get_analysis_via_api),
    ("US15", "User gets harmonic mixing recommendations", us15_harmonic_recommendations),
    ("US16", "Keys map correctly to the Camelot wheel", us16_camelot_mapping),
    ("US17", "User can create and share a playlist", us17_create_and_share_playlist),
    ("US18", "User can export the library as CSV", us18_export_library_csv),
    ("US19", "User can delete a track", us19_delete_track),
]


@pytest.mark.parametrize(
    "story_id,description,check",
    STORIES,
    ids=[s[0] for s in STORIES],
)
def test_acceptance_criteria(story_id, description, check, client, db):
    check(client, db)
