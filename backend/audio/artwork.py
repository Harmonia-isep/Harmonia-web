# pulls embedded album art out of an audio file, if it has any
import os
import uuid

from mutagen import File as MutagenFile

from backend.storage import resolve_artwork_dir


def extract_artwork(file_path: str, artwork_dir=None):
    """
    Looks inside an audio file for embedded album art.
    If found, saves it as an image and returns the path.
    If the file has no artwork, returns None.

    artwork_dir defaults to the configured upload directory's artwork/ subfolder,
    so the CLI scanner and the upload endpoint agree on where art lands.
    """
    artwork_dir = resolve_artwork_dir() if artwork_dir is None else artwork_dir
    # make sure the artwork folder exists
    os.makedirs(artwork_dir, exist_ok=True)

    try:
        audio = MutagenFile(file_path)
        if audio is None:
            return None

        artwork_data = None

        # MP3 files store art in APIC frames
        if audio.tags:
            for tag in audio.tags.values():
                # APIC is the ID3 frame that holds a picture
                if tag.__class__.__name__ == "APIC":
                    artwork_data = tag.data
                    break

        # some formats (like M4A) store it differently
        if artwork_data is None and hasattr(audio, "get"):
            covers = audio.get("covr")
            if covers:
                artwork_data = bytes(covers[0])

        if artwork_data is None:
            return None

        # save the image we found
        art_filename = f"{uuid.uuid4()}.jpg"
        art_path = os.path.join(artwork_dir, art_filename)
        with open(art_path, "wb") as f:
            f.write(artwork_data)

        return art_path

    except Exception as e:
        print(f"Could not extract artwork: {e}")
        return None
