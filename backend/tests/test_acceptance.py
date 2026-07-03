# Acceptance tests: the 19 user-story acceptance criteria, one parametrized
# case each. Every check drives the real application (HTTP endpoints, DSP, or
# pure logic) and asserts the behaviour the story promises. The parametrize id
# (US01..US19) is what shows up as pass/fail per story.

import io
import numpy as np
import soundfile as sf

from backend.models.models import Track, Analysis
from backend.api.analysis import to_camelot, camelot_compatible
from backend.audio.analyzer import analyze_audio


def _wav_bytes(freq=440.0, sr=22050, dur=2.0):
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    y = 0.5 * np.sin(2 * np.pi * freq * t)
    buf = io.BytesIO()
    sf.write(buf, y.astype(np.float32), sr, format="WAV")
    return buf.getvalue()


def _register(client, name):
    return client.post("/api/users/register",
                       json={"username": name, "password": "pw"}).json()


# --- one function per user story ---------------------------------------------

def us01_guest_mode(client, db):
    r = client.post("/api/users/guest")
    assert r.status_code == 200
    assert "user_id" in r.json() and r.json()["username"].startswith("guest_")


def us02_register_account(client, db):
    r = client.post("/api/users/register",
                    json={"username": "acc_us02", "password": "pw"})
    assert r.status_code == 200 and "id" in r.json()


def us03_duplicate_username_rejected(client, db):
    client.post("/api/users/register", json={"username": "dup_us03", "password": "pw"})
    r = client.post("/api/users/register", json={"username": "dup_us03", "password": "pw"})
    assert r.status_code == 400


def us04_login_valid(client, db):
    client.post("/api/users/register", json={"username": "log_us04", "password": "pw"})
    r = client.post("/api/users/login", json={"username": "log_us04", "password": "pw"})
    assert r.status_code == 200 and r.json()["message"] == "Login successful"


def us05_login_invalid_rejected(client, db):
    client.post("/api/users/register", json={"username": "log_us05", "password": "pw"})
    r = client.post("/api/users/login", json={"username": "log_us05", "password": "bad"})
    assert r.status_code == 401


def us06_passwords_stored_hashed(client, db):
    import hashlib
    from backend.models.models import User
    client.post("/api/users/register", json={"username": "hash_us06", "password": "pw"})
    user = db.query(User).filter(User.username == "hash_us06").first()
    assert user.password_hash != "pw"
    assert user.password_hash == hashlib.sha256(b"pw").hexdigest()


def us07_upload_track(client, db):
    reg = _register(client, "up_us07")
    r = client.post(
        "/api/tracks/upload",
        files={"file": ("song.wav", _wav_bytes(), "audio/wav")},
        data={"title": "My Song", "user_id": str(reg["id"])},
    )
    assert r.status_code == 200 and r.json()["title"] == "My Song"


def us08_oversized_upload_rejected(client, db):
    reg = _register(client, "up_us08")
    big = b"\0" * (21 * 1024 * 1024)  # 21 MB, over the 20 MB cap
    r = client.post(
        "/api/tracks/upload",
        files={"file": ("big.mp3", big, "audio/mpeg")},
        data={"title": "Too Big", "user_id": str(reg["id"])},
    )
    assert r.status_code == 413


def us09_view_library(client, db):
    reg = _register(client, "lib_us09")
    db.add(Track(title="Lib Song", file_path="uploads/a.mp3", user_id=reg["id"]))
    db.commit()
    r = client.get(f"/api/tracks/user/{reg['id']}")
    assert r.status_code == 200 and any(t["title"] == "Lib Song" for t in r.json())


def us10_search_by_title(client, db):
    reg = _register(client, "srch_us10")
    db.add(Track(title="Sunset Drive", file_path="uploads/s1.mp3", user_id=reg["id"]))
    db.add(Track(title="Rainy Day", file_path="uploads/s2.mp3", user_id=reg["id"]))
    db.commit()
    r = client.get(f"/api/tracks/user/{reg['id']}", params={"search": "sunset"})
    titles = [t["title"] for t in r.json()]
    assert titles == ["Sunset Drive"]


def us11_filter_by_key_and_bpm(client, db):
    reg = _register(client, "filt_us11")
    t1 = Track(title="Match", file_path="uploads/m1.mp3", user_id=reg["id"])
    t2 = Track(title="NoMatch", file_path="uploads/m2.mp3", user_id=reg["id"])
    db.add_all([t1, t2])
    db.commit()
    db.refresh(t1)
    db.refresh(t2)
    db.add(Analysis(track_id=t1.id, bpm=120, key="A", scale="minor"))
    db.add(Analysis(track_id=t2.id, bpm=90, key="C", scale="major"))
    db.commit()
    r = client.get(f"/api/tracks/user/{reg['id']}",
                   params={"key": "A", "bpm_min": 115, "bpm_max": 125})
    titles = [t["title"] for t in r.json()]
    assert titles == ["Match"]


def us12_track_detail_includes_analysis(client, db):
    reg = _register(client, "det_us12")
    track = Track(title="Detail", file_path="uploads/d.mp3", user_id=reg["id"])
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
    import tempfile, os
    path = os.path.join(tempfile.gettempdir(), "us13.wav")
    sf.write(path, (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32), sr)
    result = analyze_audio(path)
    for field in ("bpm", "key", "scale", "energy", "danceability"):
        assert field in result


def us14_get_analysis_via_api(client, db):
    reg = _register(client, "an_us14")
    track = Track(title="Ana", file_path="uploads/an.mp3", user_id=reg["id"])
    db.add(track)
    db.commit()
    db.refresh(track)
    db.add(Analysis(track_id=track.id, bpm=124, key="D", scale="major",
                    energy=0.6, danceability=0.7))
    db.commit()
    r = client.get(f"/api/analysis/{track.id}")
    assert r.status_code == 200 and r.json()["bpm"] == 124


def us15_harmonic_recommendations(client, db):
    reg = _register(client, "rec_us15")
    uid = reg["id"]
    src = Track(title="Src", file_path="uploads/rs.mp3", user_id=uid)
    good = Track(title="Good", file_path="uploads/rg.mp3", user_id=uid)
    db.add_all([src, good])
    db.commit()
    db.refresh(src)
    db.refresh(good)
    db.add(Analysis(track_id=src.id, bpm=120, key="A", scale="minor"))
    db.add(Analysis(track_id=good.id, bpm=121, key="A", scale="minor"))
    db.commit()
    r = client.get(f"/api/analysis/{src.id}/recommendations")
    titles = [rec["title"] for rec in r.json()["recommendations"]]
    assert "Good" in titles


def us16_camelot_mapping(client, db):
    assert to_camelot("A", "minor") == "8A"
    assert to_camelot("C", "major") == "8B"
    assert camelot_compatible("12A", "1A") is True   # wheel wrap


def us17_create_and_share_playlist(client, db):
    reg = _register(client, "pl_us17")
    uid = reg["id"]
    track = Track(title="PL Track", file_path="uploads/pl.mp3", user_id=uid)
    db.add(track)
    db.commit()
    db.refresh(track)
    created = client.post("/api/playlists/create",
                          params={"name": "My Set", "user_id": uid}).json()
    client.post(f"/api/playlists/{created['id']}/add/{track.id}")
    shared = client.get(f"/api/playlists/shared/{created['share_token']}")
    assert shared.status_code == 200
    assert shared.json()["name"] == "My Set"
    assert any(t["title"] == "PL Track" for t in shared.json()["tracks"])


def us18_export_library_csv(client, db):
    reg = _register(client, "csv_us18")
    db.add(Track(title="Export Me", file_path="uploads/e.mp3", user_id=reg["id"]))
    db.commit()
    r = client.get(f"/api/tracks/user/{reg['id']}/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "Title" in r.text and "Export Me" in r.text


def us19_delete_track(client, db):
    reg = _register(client, "del_us19")
    track = Track(title="Delete Me", file_path="uploads/del.mp3", user_id=reg["id"])
    db.add(track)
    db.commit()
    db.refresh(track)
    tid = track.id
    assert client.delete(f"/api/tracks/{tid}").status_code == 200
    assert client.get(f"/api/tracks/{tid}").status_code == 404


STORIES = [
    ("US01", "Guest can use the app without an account", us01_guest_mode),
    ("US02", "Visitor can register an account", us02_register_account),
    ("US03", "Duplicate usernames are rejected", us03_duplicate_username_rejected),
    ("US04", "Registered user can log in", us04_login_valid),
    ("US05", "Wrong credentials are rejected", us05_login_invalid_rejected),
    ("US06", "Passwords are stored hashed, not in plaintext", us06_passwords_stored_hashed),
    ("US07", "User can upload an audio track", us07_upload_track),
    ("US08", "Oversized uploads are rejected", us08_oversized_upload_rejected),
    ("US09", "User can view their library", us09_view_library),
    ("US10", "User can search the library by title", us10_search_by_title),
    ("US11", "User can filter by key and BPM range", us11_filter_by_key_and_bpm),
    ("US12", "Track detail shows its analysis", us12_track_detail_includes_analysis),
    ("US13", "DSP extracts BPM, key, scale, energy, danceability", us13_dsp_extracts_all_descriptors),
    ("US14", "Analysis is retrievable via the API", us14_get_analysis_via_api),
    ("US15", "User gets harmonic mixing recommendations", us15_harmonic_recommendations),
    ("US16", "Keys map correctly to the Camelot wheel", us16_camelot_mapping),
    ("US17", "User can create and share a playlist", us17_create_and_share_playlist),
    ("US18", "User can export their library as CSV", us18_export_library_csv),
    ("US19", "User can delete a track", us19_delete_track),
]


import pytest


@pytest.mark.parametrize(
    "story_id,description,check",
    STORIES,
    ids=[s[0] for s in STORIES],
)
def test_acceptance_criteria(story_id, description, check, client, db):
    check(client, db)
