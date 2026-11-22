"""Shared analyses: a person who analyses a whole video uploads its flags to the author's collector, and once the
author approves them, anyone who opens that video later in the same language downloads them instead of paying the
analysis again.

Only the flag file travels, stripped to SHARED, with each guest's summary, each person's speaking time and the voice
turns by person (S5), and the prompts file of the helper version: never the transcript, the person's marks or anything
else of the machine.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from fact_checker import prompts
from fact_checker.core import speakers, summary
from fact_checker.feedback import AGENT, install_id
from fact_checker.store import Store

# The fields of a flag file that a shared analysis keeps.
SHARED = ("video_id", "lang", "spoken", "status", "published_at", "title", "channel", "duration", "speakers",
          "people", "claims", "questions", "readers", "cost_usd", "analysed_until", "flags")
UPLOAD_TIMEOUT = 15
DOWNLOAD_TIMEOUT = 5  # the person waits for it when the video opens


def _address(url: str, video_id: str, lang: str, action: str = "") -> str:
    return f"{url.rstrip('/')}/analyses/{video_id}{action and '/' + action}?lang={lang}"


def _owner(home) -> dict:
    """The admin token header of the author's own helper; none on anyone else's."""
    from fact_checker.server import secret  # the server imports this module
    token = secret(home, "FEEDBACK_ADMIN_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


SPEECH = ("spoken_s", "turns", "longest_s")


def strip(data: dict, version: str | None = None, turns: list[dict] | None = None) -> dict:
    """The shared fields, with the tally of each guest's card as `summary` and the version of the prompts that made
    the analysis (this helper's) as its helper version. With the video's voice turns, each person carries their
    speaking time, turns and longest turn, and `turns` the voice turns by person; without them, neither."""
    shared = {k: data[k] for k in SHARED if k in data}
    # An analysis from before roles has no `people`: its named voices stand in, with no role.
    people = shared.get("people") or ({name: {} for name in shared.get("speakers", {}).values() if name} if turns else {})
    if people:
        said = speakers.speech(turns or [], shared.get("speakers", {}))
        shared["people"] = {name: {k: v for k, v in p.items() if k not in SPEECH} | (said.get(name, {}) if turns else {})
                            for name, p in people.items()}
    if turns:
        shared["turns"] = speakers.merged(turns, shared.get("speakers", {}))
    return shared | {"summary": {name: summary.tally(shared, name) for name in summary.guests(shared)},
                     "helper_version": version or prompts.export()["version"]}


def _turns(home, video_id: str) -> list[dict] | None:
    """The local voice turns of a video, or None when its voices were never told apart on this machine."""
    file = home / "voices" / f"{video_id}.turns.json"
    return json.loads(file.read_text()) if file.exists() else None


def upload(home, url: str, data: dict) -> None:
    """Sends the stripped flag file with the install id; raises OSError when the collector does not take it. The
    author's upload carries the admin token and is served at once; anyone else's waits for the author's review. The
    prompts file of this helper version travels with it, so the collector can serve the rules behind each flag."""
    file = prompts.export()
    body = {"install_id": install_id(home), "analysis": strip(data, file["version"], _turns(home, data["video_id"])),
            "prompts": file}
    req = urllib.request.Request(_address(url, data["video_id"], data["lang"]), method="PUT",
                                 data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json", **AGENT, **_owner(home)})
    urllib.request.urlopen(req, timeout=UPLOAD_TIMEOUT).close()


def share_again(home, url: str | None, video_id: str, lang: str) -> int:
    """Uploads the local analysis of a video again, as the helper does after a whole analysis: with the owner's token
    it replaces the served one. 1 when there is no whole local analysis in `lang` or the collector refuses it."""
    data = Store(home).load(video_id)
    if not url:
        print(f"Set feedback_url in {home / 'config.toml'} to the collector's address.")
        return 1
    if not data or data.get("status") != "done" or (data.get("lang") or "es") != lang:
        print(f"No whole local analysis of {video_id} in {lang}.")
        return 1
    try:
        upload(home, url, data)
    except urllib.error.HTTPError as e:
        print(f"The collector refused the analysis of {video_id} (HTTP {e.code}): {e.read().decode(errors='replace')}")
        return 1
    except OSError as e:
        print(f"The collector at {url} does not answer: {e}")
        return 1
    print(f"Shared {video_id} ({lang}) again, with its summary and prompts.")
    return 0


def download(url: str, video_id: str, lang: str) -> dict | None:
    """The shared analysis of the video in `lang`, or None when there is none or the collector does not answer. The
    request carries no install id."""
    try:
        with urllib.request.urlopen(urllib.request.Request(_address(url, video_id, lang), headers=AGENT),
                                    timeout=DOWNLOAD_TIMEOUT) as res:
            return json.load(res)
    except (OSError, ValueError):
        return None


def _line(r: dict) -> str:
    return f"{r['video_id']}  {r['lang']}  {r['model']}  {r['flags']} flags  {r['install_id']}  {r['received_at']}"


def review(home, url: str | None, action: str, video_id: str | None = None, lang: str | None = None,
           install: str = "") -> int:
    """The author's review of the pending uploads: `list` prints one line each; `approve` serves one upload of a video
    and language to everyone (the only one, or the one whose install id starts with `install`), `reject` deletes its
    pending uploads. 1 when the collector refuses or does not answer, or when the upload to approve is not one."""
    if not url:
        print(f"Set feedback_url in {home / 'config.toml'} to the collector's address.")
        return 1

    def send(req: urllib.request.Request) -> list[dict] | None:
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return json.load(res).get("rows", [])
        except urllib.error.HTTPError as e:
            print(f"No pending analysis of {video_id} in {lang}." if e.code == 404 else
                  f"The upload of {video_id} in {lang} changed; list it again." if e.code == 409 else
                  f"The collector refused the review (HTTP {e.code}). "
                  f"Set FEEDBACK_ADMIN_TOKEN in {home / '.env'} to the collector's ADMIN_TOKEN.")
        except OSError as e:
            print(f"The collector at {url} does not answer: {e}")
        return None

    headers = AGENT | _owner(home)
    rows = [] if action == "reject" else send(urllib.request.Request(f"{url.rstrip('/')}/analyses", headers=headers))
    if rows is None:
        return 1
    if action == "list":
        for r in rows:
            print(_line(r))
        print(f"{len(rows)} pending analyses")
        return 0
    which = ""
    if action == "approve":
        found = [r for r in rows if (r["video_id"], r["lang"]) == (video_id, lang) and r["install_id"].startswith(install)]
        if len(found) != 1:
            print(f"No pending analysis of {video_id} in {lang}." if not found else
                  "\n".join([f"{len(found)} uploads of {video_id} in {lang}; name one with --install:",
                             *map(_line, found)]))
            return 1
        which = "&" + urllib.parse.urlencode({"install": found[0]["install_id"], "at": found[0]["received_at"]})
    if send(urllib.request.Request(_address(url, video_id, lang, action) + which, method="POST", headers=headers)) is None:
        return 1
    print(f"Approved {video_id} ({lang}): everyone who opens it now gets these flags." if action == "approve" else
          f"Rejected {video_id} ({lang}): its pending uploads are deleted.")
    return 0
