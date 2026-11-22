import json
import os
import re
import threading
from dataclasses import asdict
from pathlib import Path

from fact_checker.core.flags import Candidate, Claim, Flag


def default_home() -> Path:
    return Path(os.environ.get("FACT_CHECKER_HOME", Path.home() / ".fact-checker"))


# One lock per helper home: an analysis and the server each hold a Store of the same home, and both rewrite its files.
_locks: dict[Path, threading.RLock] = {}


class Store:
    """Flag files, candidates log, claims log and usage log under the helper home."""

    def __init__(self, home: Path):
        self.home = Path(home)
        (self.home / "videos").mkdir(parents=True, exist_ok=True)
        self.lock = _locks.setdefault(self.home.resolve(), threading.RLock())

    def _path(self, video_id: str) -> Path:
        return self.home / "videos" / f"{video_id}.json"

    def load(self, video_id: str) -> dict | None:
        path = self._path(video_id)
        return json.loads(path.read_text()) if path.exists() else None

    def save(self, data: dict) -> None:
        with self.lock:
            path = self._path(data["video_id"])
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
            tmp.replace(path)

    def add_flags(self, video_id: str, flags: list[Flag]) -> None:
        """Adds the flags of one part; a name keeps one context flag, at its earliest mention."""
        data = self.load(video_id)
        merged, named = [], set()
        for f in sorted(data["flags"] + [asdict(f) | {"id": f.id} for f in flags], key=lambda f: f["t"]):
            if f["type"] == "context":
                name = re.sub(r"[^\w\s]", "", f["quote"].lower())
                if name in named:
                    continue
                named.add(name)
            merged.append(f)
        data["flags"] = merged
        self.save(data)

    def add_candidates(self, video_id: str, candidates: list[Candidate]) -> None:
        self._append("candidates.log", [asdict(c) | {"video_id": video_id} for c in candidates])

    def add_claims(self, video_id: str, claims: list[Claim], outcomes: list[str]) -> None:
        """One line per claim, with no quote: the claims log holds no transcript. A `repeated` claim also has the
        second of the claim it repeats in `repeats`."""
        self._append("claims.jsonl", [{"video_id": video_id, "t": c.t, "speaker": c.speaker, "outcome": o}
                                      | ({"repeats": c.repeats} if o == "repeated" else {})
                                      for c, o in zip(claims, outcomes)])

    def add_mark(self, video_id: str, flag: dict, verdict: str, reason: str, shared: bool = True) -> None:
        """A mark given with sharing off carries `"shared": false` and never leaves the laptop."""
        self._append("marks.jsonl", [{
            "video_id": video_id, "flag_id": flag["id"], "quote": flag["quote"], "type": flag["type"],
            "label": flag["label"], "confidence": flag["confidence"], "verdict": verdict, "reason": reason,
        } | ({} if shared else {"shared": False})])

    def marks(self, video_id: str) -> dict[str, str]:
        """The latest verdict per flag id of one video."""
        path = self.home / "marks.jsonl"
        with self.lock:
            rows = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
        return {r["flag_id"]: r["verdict"] for r in rows if r["video_id"] == video_id}

    def log_usage(self, entry: dict) -> None:
        self._append("usage.log", [entry])

    def _append(self, name: str, rows: list[dict]) -> None:
        if not rows:
            return
        with self.lock, open(self.home / name, "a") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
