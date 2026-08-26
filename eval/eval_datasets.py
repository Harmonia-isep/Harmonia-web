"""Dataset acquisition and iteration for the Harmonia evaluation harness.

Wraps mirdata for the two reference datasets and yields plain
(audio_path, reference) pairs the runner can consume without knowing anything
about mirdata:

    key   -> GiantSteps+ EDM Key (600 tracks, Zenodo 1095691) via mirdata
             `giantsteps_key`; audio + key annotations both fetched from Zenodo.
    tempo -> GTZAN (Tzanetakis) audio from the public Hugging Face mirror, with
             single-BPM tempo annotations from the TempoBeatDownbeat project,
             both via mirdata `gtzan_genre` (annotations) plus a direct audio
             fetch (mirdata cannot serve GTZAN audio - the original source is
             dead).

Nothing here is vendored. Everything downloads under eval/datasets/, which is
gitignored. The module is named eval_datasets (not datasets) so it does not
shadow the unrelated Hugging Face `datasets` package on sys.path.
"""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
from pathlib import Path

DATA_HOME = Path(__file__).resolve().parent / "datasets"

# Public Hugging Face mirror of GTZAN. The canonical marsyas source
# (opihi.cs.uvic.ca) is long dead; this repo hosts the same genres/ tree as WAV.
GTZAN_AUDIO_URL = (
    "https://huggingface.co/datasets/marsyas/gtzan/resolve/main/data/genres.tar.gz"
)


# --------------------------------------------------------------------------- #
# mirdata handles
# --------------------------------------------------------------------------- #


def _require_mirdata():
    try:
        import mirdata
    except ImportError as exc:  # pragma: no cover - environment guard
        msg = (
            "mirdata is required for dataset access.\n"
            "Install the eval extras:  pip install -r eval/requirements.txt"
        )
        raise SystemExit(msg) from exc
    return mirdata


def key_dataset():
    """mirdata handle for GiantSteps+ EDM Key, rooted under eval/datasets/."""
    mirdata = _require_mirdata()
    return mirdata.initialize(
        "giantsteps_key", data_home=str(DATA_HOME / "giantsteps_key")
    )


def tempo_dataset():
    """mirdata handle for GTZAN (genre index carries the tempo annotations)."""
    mirdata = _require_mirdata()
    return mirdata.initialize("gtzan_genre", data_home=str(DATA_HOME / "gtzan_genre"))


# --------------------------------------------------------------------------- #
# Downloading
# --------------------------------------------------------------------------- #


def _stream_download(url: str, dest: str, chunk: int = 1 << 20) -> None:
    import requests

    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        done = 0
        with open(dest, "wb") as fh:
            for block in resp.iter_content(chunk_size=chunk):
                fh.write(block)
                done += len(block)
                if total:
                    pct = 100 * done / total
                    print(f"\r  {os.path.basename(dest)}: {pct:5.1f}%", end="")
        print()


def download_key() -> dict:
    """Download GiantSteps+ audio + key annotations via mirdata (Zenodo)."""
    ds = key_dataset()
    print("Downloading GiantSteps+ EDM Key (audio + keys) from Zenodo ...")
    try:
        ds.download()
    except Exception as exc:  # pragma: no cover - network/host dependent
        msg = (
            f"mirdata could not download giantsteps_key: {exc}\n"
            "If Zenodo is blocking automated downloads, fetch audio.zip and "
            "keys.zip manually from https://zenodo.org/record/1095691 and place "
            f"them under {DATA_HOME / 'giantsteps_key'} following mirdata's "
            "layout, then rerun run_eval.py to validate."
        )
        raise SystemExit(msg) from exc
    return _coverage(ds, ref_getter=lambda t: t.key)


def download_tempo() -> dict:
    """Download GTZAN tempo/beat annotations (mirdata) + audio (HF mirror)."""
    ds = tempo_dataset()
    print("Downloading GTZAN tempo/beat annotations (TempoBeatDownbeat) ...")
    ds.download()  # annotations only; audio is not among mirdata's remotes
    placed, missing = _download_gtzan_audio(ds)
    print(f"Placed audio for {placed} GTZAN tracks; {len(missing)} source files missing.")
    return _coverage(ds, ref_getter=lambda t: t.tempo)


def _download_gtzan_audio(ds) -> tuple[int, list[str]]:
    """Fetch the GTZAN audio tarball and copy each file to mirdata's path.

    mirdata's Track.audio_path is the single source of truth for where each file
    belongs, so we never hardcode the on-disk layout - we just satisfy it.
    """
    tmp = tempfile.mkdtemp(prefix="gtzan_audio_")
    try:
        tar_path = os.path.join(tmp, "genres.tar.gz")
        print("Downloading GTZAN audio from the Hugging Face mirror ...")
        _stream_download(GTZAN_AUDIO_URL, tar_path)
        with tarfile.open(tar_path) as tf:
            _safe_extract(tf, tmp)

        placed, missing = 0, []
        for tid in ds.track_ids:
            genre = tid.split(".")[0]
            src = _find_audio(os.path.join(tmp, "genres", genre), tid)
            dst = ds.track(tid).audio_path
            if src is None:
                missing.append(tid)
                continue
            if not os.path.exists(dst):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
            placed += 1
        return placed, missing
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _find_audio(genre_dir: str, tid: str) -> str | None:
    """Locate a track's audio file under genre_dir, tolerant of extension."""
    if not os.path.isdir(genre_dir):
        return None
    exact = os.path.join(genre_dir, f"{tid}.wav")
    if os.path.exists(exact):
        return exact
    for name in os.listdir(genre_dir):
        if name.startswith(tid + "."):
            return os.path.join(genre_dir, name)
    return None


def _safe_extract(tf: tarfile.TarFile, path: str) -> None:
    """Extract a tar guarding against path traversal (CVE-2007-4559)."""
    base = os.path.realpath(path)
    for member in tf.getmembers():
        target = os.path.realpath(os.path.join(path, member.name))
        if not (target == base or target.startswith(base + os.sep)):
            msg = f"unsafe path in archive: {member.name}"
            raise RuntimeError(msg)
    tf.extractall(path)


# --------------------------------------------------------------------------- #
# Iteration -> (audio_path, reference) pairs
# --------------------------------------------------------------------------- #


def _coverage(ds, ref_getter) -> dict:
    """Count how many tracks have both a usable reference and audio on disk."""
    total = len(ds.track_ids)
    with_ref = with_audio = usable = 0
    for tid in ds.track_ids:
        t = ds.track(tid)
        has_ref = _ref_ok(ref_getter, t)
        has_audio = bool(t.audio_path) and os.path.exists(t.audio_path)
        with_ref += has_ref
        with_audio += has_audio
        usable += has_ref and has_audio
    return {
        "total": total,
        "with_reference": with_ref,
        "with_audio": with_audio,
        "usable": usable,
    }


def _ref_ok(ref_getter, track) -> bool:
    try:
        ref = ref_getter(track)
    except Exception:
        return False
    if ref is None:
        return False
    if isinstance(ref, str):
        return bool(ref.strip())
    return True


def key_pairs(limit: int | None = None) -> list[tuple[str, str]]:
    """(audio_path, key_string) for GiantSteps+ tracks with audio present."""
    ds = key_dataset()
    return _pairs(ds, ref_getter=lambda t: t.key, limit=limit)


def tempo_pairs(limit: int | None = None) -> list[tuple[str, float]]:
    """(audio_path, tempo_bpm) for GTZAN tracks with audio present."""
    ds = tempo_dataset()
    return _pairs(ds, ref_getter=lambda t: t.tempo, limit=limit)


def _pairs(ds, ref_getter, limit):
    out = []
    for tid in ds.track_ids:
        t = ds.track(tid)
        if not (t.audio_path and os.path.exists(t.audio_path)):
            continue
        if not _ref_ok(ref_getter, t):
            continue
        out.append((t.audio_path, ref_getter(t)))
        if limit is not None and len(out) >= limit:
            break
    return out
