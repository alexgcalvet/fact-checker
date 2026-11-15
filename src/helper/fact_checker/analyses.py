"""Shared analyses: a person who analyses a whole video uploads its flags to the author's collector, and once the
author approves them, anyone who opens that video later in the same language downloads them instead of paying the
analysis again.

Only the flag file travels, stripped to SHARED: never the transcript, the person's marks or anything of the machine.
"""
import json
import urllib.error
import urllib.request

from fact_checker.feedback import AGENT, helper_version, install_id

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


def strip(data: dict) -> dict:
    return {k: data[k] for k in SHARED if k in data} | {"helper_version": helper_version()}


def upload(home, url: str, data: dict) -> None:
    """Sends the stripped flag file with the install id; raises OSError when the collector does not take it. The
    author's upload carries the admin token and is served at once; anyone else's waits for the author's review."""
    body = {"install_id": install_id(home), "analysis": strip(data)}
    req = urllib.request.Request(_address(url, data["video_id"], data["lang"]), method="PUT",
                                 data=json.dumps(body, ensure_ascii=False).encode(),
                                 headers={"Content-Type": "application/json", **AGENT, **_owner(home)})
    urllib.request.urlopen(req, timeout=UPLOAD_TIMEOUT).close()


def download(url: str, video_id: str, lang: str) -> dict | None:
    """The shared analysis of the video in `lang`, or None when there is none or the collector does not answer. The
    request carries no install id."""
    try:
        with urllib.request.urlopen(urllib.request.Request(_address(url, video_id, lang), headers=AGENT),
                                    timeout=DOWNLOAD_TIMEOUT) as res:
            return json.load(res)
    except (OSError, ValueError):
        return None


def review(home, url: str | None, action: str, video_id: str | None = None, lang: str | None = None) -> int:
    """The author's review of the pending uploads: `list` prints one line each; `approve` serves the upload of a video
    and language to everyone, `reject` deletes its pending uploads. 1 when the collector refuses or does not answer."""
    if not url:
        print(f"Set feedback_url in {home / 'config.toml'} to the collector's address.")
        return 1
    req = (urllib.request.Request(f"{url.rstrip('/')}/analyses", headers=AGENT | _owner(home)) if action == "list"
           else urllib.request.Request(_address(url, video_id, lang, action), method="POST",
                                       headers=AGENT | _owner(home)))
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            rows = json.load(res).get("rows", [])
    except urllib.error.HTTPError as e:
        print(f"No pending analysis of {video_id} in {lang}." if e.code == 404 else
              f"The collector refused the review (HTTP {e.code}). "
              f"Set FEEDBACK_ADMIN_TOKEN in {home / '.env'} to the collector's ADMIN_TOKEN.")
        return 1
    except OSError as e:
        print(f"The collector at {url} does not answer: {e}")
        return 1
    if action == "approve":
        print(f"Approved {video_id} ({lang}): everyone who opens it now gets these flags.")
    elif action == "reject":
        print(f"Rejected {video_id} ({lang}): its pending uploads are deleted.")
    else:
        for r in rows:
            print(f"{r['video_id']}  {r['lang']}  {r['model']}  {r['flags']} flags  {r['install_id']}  {r['received_at']}")
        print(f"{len(rows)} pending analyses")
    return 0
