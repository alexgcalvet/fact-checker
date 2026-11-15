import base64
from pathlib import Path
from urllib.request import urlopen


def thumbnail(video_id: str, home: Path) -> str | None:
    """The YouTube thumbnail of the video as a data URI, kept under the helper home; None when there is none."""
    path = home / "thumbnails" / f"{video_id}.jpg"
    if not path.exists():
        for name in ("maxresdefault", "hqdefault"):
            try:
                with urlopen(f"https://i.ytimg.com/vi/{video_id}/{name}.jpg", timeout=5) as reply:
                    raw = reply.read()
            except OSError:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            break
        else:
            return None
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()
