# pulls embedded album art out of an audio file, if it has any
import os
import uuid

from mutagen import File as MutagenFile

ARTWORK_DIR = "uploads/artwork"


def extract_artwork(file_path: str):
    """
    Looks inside an audio file for embedded album art.
    If found, saves it as an image and returns the path.
    If the file has no artwork, returns None.
    """
    # make sure the artwork folder exists
    os.makedirs(ARTWORK_DIR, exist_ok=True)

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
        art_path = os.path.join(ARTWORK_DIR, art_filename)
        with open(art_path, "wb") as f:
            f.write(artwork_data)

        return art_path

    except Exception as e:
        print(f"Could not extract artwork: {e}")
        return None
