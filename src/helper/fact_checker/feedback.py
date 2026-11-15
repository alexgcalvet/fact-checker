"""Shared feedback: each mark goes to the owner's collector a moment after the person gives it, unless the person
turned sharing off, and the owner pulls them.

A sent mark holds the flag, the person's verdict and reason, the provider and model that made the flag, the helper
version and a random install id. Nothing else about the machine or the person goes out.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

BATCH = 50  # marks per request: the longest fields stay under the collector's 256 KB
QUOTE = 1000  # the collector refuses a longer quote
TIMEOUT = 15
# Cloudflare answers 403 (error 1010) to the default Python-urllib agent, so the helper names itself.
AGENT = {"User-Agent": "fact-checker-helper"}


def helper_version() -> str:
    try:
        return version("fact-checker")
    except PackageNotFoundError:  # run from the source tree, as in the tests
        return "dev"


def install_id(home: Path) -> str:
    """A random id, made once per helper home, so the owner can group the marks of one tester."""
    path = home / "install-id"
    if not path.exists():
        path.write_text(str(uuid.uuid4()))
    return path.read_text().strip()


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def _reader(home: Path, video: dict, flag: dict) -> tuple[str | None, str | None]:
    """The provider and model that made the flag: from the flag file's `readers`, else the model of the video's latest
    usage line of that step and no provider."""
    role, step = ("verdict", "fact_check") if flag["type"] == "inaccuracy" else ("parts", "analyze_chunk")
    if "readers" in video:
        return video["readers"][role]["provider"], video["readers"][role]["model"]
    models = [u["model"] for u in _lines(home / "usage.log")
              if u.get("video_id") == video["video_id"] and u.get("step") == step and u.get("model")]
    return None, models[-1] if models else None


def _sent_path(home: Path) -> Path:
    return home / "feedback-sent.json"


def unsent(home: Path) -> list[dict]:
    """The latest mark of each flag that was not sent with this verdict and reason, joined with its flag."""
    latest = {(m["video_id"], m["flag_id"]): m for m in _lines(home / "marks.jsonl")}
    sent = json.loads(_sent_path(home).read_text()) if _sent_path(home).exists() else {}
    videos, marks = {}, []
    for (video_id, flag_id), m in latest.items():
        if m.get("shared") is False or sent.get(f"{video_id}/{flag_id}") == [m["verdict"], m["reason"]]:
            continue
        if video_id not in videos:
            path = home / "videos" / f"{video_id}.json"
            videos[video_id] = json.loads(path.read_text()) if path.exists() else {"flags": []}
        flag = next((f for f in videos[video_id]["flags"] if f["id"] == flag_id), None)
        if not flag:  # the flag file was deleted: the mark has no second
            continue
        provider, model = _reader(home, videos[video_id], flag)
        marks.append({"video_id": video_id, "flag_id": flag_id, "t": flag["t"], "type": flag["type"],
                      "label": flag["label"], "quote": flag["quote"][:QUOTE], "confidence": flag["confidence"],
                      "verdict": m["verdict"], "reason": m["reason"], "provider": provider, "model": model})
    return marks


def set_share(home: Path, on: bool) -> None:
    """Writes `share_marks` into `<home>/config.toml`: in place of its line, or first, so it stays above every table."""
    path = home / "config.toml"
    text = path.read_text() if path.exists() else ""
    line = f"share_marks = {'true' if on else 'false'}"
    text, found = re.subn(r"(?m)^share_marks\s*=.*$", line, text)
    path.write_text(text if found else f"{line}\n{text}")


def send(home: Path, url: str | None, save: bool = True) -> dict:
    """Sends the unsent marks to the collector at `url` in batches and records each sent batch. Without `url`, or when
    a request fails, writes the marks not sent to `<home>/feedback-<date>.json` instead, unless `save` is false; they
    stay unsent."""
    marks = unsent(home)
    body = {"install_id": install_id(home), "helper_version": helper_version()}
    sent = json.loads(_sent_path(home).read_text()) if _sent_path(home).exists() else {}
    done = 0
    try:
        if not url:
            raise OSError("no feedback_url")
        for i in range(0, len(marks), BATCH):
            batch = marks[i:i + BATCH]
            req = urllib.request.Request(f"{url.rstrip('/')}/marks", method="POST",
                                         data=json.dumps(body | {"marks": batch}, ensure_ascii=False).encode(),
                                         headers={"Content-Type": "application/json", **AGENT})
            urllib.request.urlopen(req, timeout=TIMEOUT).close()
            sent |= {f"{m['video_id']}/{m['flag_id']}": [m["verdict"], m["reason"]] for m in batch}
            _sent_path(home).write_text(json.dumps(sent, ensure_ascii=False))
            done += len(batch)
    except (OSError, ValueError):  # no answer, an HTTP error, or a malformed URL
        if not save:
            return {"unsent": len(marks) - done}
        path = home / f"feedback-{date.today().isoformat()}.json"
        path.write_text(json.dumps(body | {"marks": marks[done:]}, ensure_ascii=False, indent=1))
        return {"saved": str(path), "unsent": len(marks) - done}
    return {"sent": done, "unsent": 0}


def pull(home: Path, url: str | None, token: str | None) -> int:
    """Downloads the rows received since the last pull into `<home>/feedback/<UTC time>.jsonl`; prints how many. 1 when
    the collector refuses or does not answer."""
    if not url:
        print(f"Set feedback_url in {home / 'config.toml'} to the collector's address.")
        return 1
    folder = home / "feedback"
    since = (folder / "since").read_text().strip() if (folder / "since").exists() else ""
    req = urllib.request.Request(f"{url.rstrip('/')}/marks?since={urllib.parse.quote(since)}",
                                 headers=AGENT | ({"Authorization": f"Bearer {token}"} if token else {}))
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            rows = json.load(res)["rows"]
    except urllib.error.HTTPError as e:
        print(f"The collector refused the read (HTTP {e.code}). "
              f"Set FEEDBACK_ADMIN_TOKEN in {home / '.env'} to the collector's ADMIN_TOKEN.")
        return 1
    except OSError as e:
        print(f"The collector at {url} does not answer: {e}")
        return 1
    if rows:
        folder.mkdir(exist_ok=True)
        path = folder / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.jsonl"
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
        (folder / "since").write_text(max(r["received_at"] for r in rows))
        print(f"{len(rows)} new marks: {path}")
    else:
        print("0 new marks")
    return 0
