# Integration tests: real FastAPI app driven through the TestClient against an
# in-memory SQLite database (see conftest.py). These exercise the HTTP layer,
# routing, request/response shapes and the ORM together.

from backend.models.models import Analysis, Track


def test_root_health(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "Harmonia API is running"}


def test_register_returns_id_and_username(client):
    r = client.post("/api/users/register",
                    json={"username": "alice", "password": "pw"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "alice"
    assert "id" in body


def test_login_success_response_shape(client):
    # The mobile client depends on this exact shape — keep message/user_id/username.
    client.post("/api/users/register", json={"username": "bob", "password": "pw"})
    r = client.post("/api/users/login", json={"username": "bob", "password": "pw"})
    assert r.status_code == 200
    body = r.json()
    assert body["message"] == "Login successful"
    assert body["username"] == "bob"
    assert "user_id" in body


def test_login_wrong_password_is_rejected(client):
    client.post("/api/users/register", json={"username": "carol", "password": "pw"})
    r = client.post("/api/users/login",
                    json={"username": "carol", "password": "WRONG"})
    assert r.status_code == 401


def test_list_tracks_for_user(client, db):
    reg = client.post("/api/users/register",
                      json={"username": "dave", "password": "pw"}).json()
    db.add(Track(title="Song A", artist="Artist",
                 file_path="uploads/x.mp3", user_id=reg["id"]))
    db.commit()

    r = client.get(f"/api/tracks/user/{reg['id']}")
    assert r.status_code == 200
    titles = [t["title"] for t in r.json()]
    assert "Song A" in titles


def test_get_one_analysis(client, db):
    reg = client.post("/api/users/register",
                      json={"username": "erin", "password": "pw"}).json()
    track = Track(title="Analyzed", file_path="uploads/y.mp3", user_id=reg["id"])
    db.add(track)
    db.commit()
    db.refresh(track)
    db.add(Analysis(track_id=track.id, bpm=120, key="A", scale="minor",
                    energy=0.5, danceability=0.4))
    db.commit()

    r = client.get(f"/api/analysis/{track.id}")
    assert r.status_code == 200
    body = r.json()
    assert body["bpm"] == 120
    assert body["key"] == "A"
    assert body["scale"] == "minor"


def test_recommendations_only_returns_compatible_tracks(client, db):
    reg = client.post("/api/users/register",
                      json={"username": "frank", "password": "pw"}).json()
    uid = reg["id"]

    source = Track(title="Src", file_path="uploads/s.mp3", user_id=uid)
    db.add(source)
    db.commit()
    db.refresh(source)
    db.add(Analysis(track_id=source.id, bpm=120, key="A", scale="minor",
                    energy=0.5, danceability=0.4))

    # Same key (8A) and within +/-5 BPM -> should be recommended.
    good = Track(title="Good", file_path="uploads/g.mp3", user_id=uid)
    db.add(good)
    db.commit()
    db.refresh(good)
    db.add(Analysis(track_id=good.id, bpm=122, key="A", scale="minor",
                    energy=0.5, danceability=0.4))

    # Same key but BPM too far away -> should be filtered out.
    bad = Track(title="Bad", file_path="uploads/b.mp3", user_id=uid)
    db.add(bad)
    db.commit()
    db.refresh(bad)
    db.add(Analysis(track_id=bad.id, bpm=150, key="A", scale="minor",
                    energy=0.5, danceability=0.4))
    db.commit()

    r = client.get(f"/api/analysis/{source.id}/recommendations")
    assert r.status_code == 200
    body = r.json()
    assert body["camelot"] == "8A"
    titles = [rec["title"] for rec in body["recommendations"]]
    assert "Good" in titles
    assert "Bad" not in titles
