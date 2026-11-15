import argparse
import errno
import html
import json
import os
import platform
import re
import shutil
import tempfile
import threading
import time
import tomllib
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

from fact_checker import analyses, feedback
from fact_checker.adapters.diarization import Diarizer
from fact_checker.adapters.factcheck_google import GoogleFactCheck
from fact_checker.adapters.llm_anthropic_api import AnthropicAPI
from fact_checker.adapters.llm_chat_api import ChatAPI
from fact_checker.adapters.llm_claude_cli import ClaudeCLI
from fact_checker.adapters.llm_codex_cli import CodexCLI
from fact_checker.adapters.llm_openai_api import OpenAIAPI
from fact_checker.adapters.screenshot import screenshot
from fact_checker.adapters.search_tavily import Tavily
from fact_checker.adapters.thumbnail import thumbnail
from fact_checker.adapters.whisper import CLI as MLX_CLI, FASTER_CLI, Whisper
from fact_checker.adapters.youtube import YouTube
from fact_checker.core import judge as rulings, scheduler, speakers, summary
from fact_checker.core.factcheck import check_claims
from fact_checker.core.flags import Session
from fact_checker.core.languages import NAMES
from fact_checker.core.pipeline import ChunkResult, analyze_chunk, screen as screen_part
from fact_checker.store import Store, default_home

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{6,20}")
THRESHOLDS = Path(__file__).parent / "thresholds.json"
DEFAULT_BAR = 0.8  # a type missing from the thresholds; a null bar means never
# How a part gets what was said before it: "window" or "conversation". A `chat` parts provider always reads a window:
# a chat API resends the whole conversation and most have no prompt cache, so each part would cost more than the last.
CONTEXT_MODE = "conversation"
VOICES_WAIT = 1.0  # seconds the first part waits for voices that are ready at once, such as a separation done before
SESSION_TOKENS = 150_000  # a conversation over this context starts a new one, which gets the positions list
# The default model of each role: `parts` reads each part, `verdict` turns the search evidence into verdicts, `judge`
# rules on the whole video, `search` searches the web, `screen` decides which parts get the full reading. `config.toml`
# in the helper home can set each one. Codex has none: with no model it uses the account's own default, since each
# ChatGPT plan allows other models. A `chat` screen with no model of its own uses the parts model.
ROLES = ("parts", "verdict", "judge", "search", "screen")
MODELS = {
    "claude": {"parts": "opus", "verdict": "opus", "judge": "opus", "search": "haiku", "screen": "haiku"},
    "codex": dict.fromkeys(ROLES),
    "anthropic": {"parts": "claude-opus-5-5", "verdict": "claude-opus-5-5", "judge": "claude-opus-5-5",
                  "search": "claude-haiku-5-5", "screen": "claude-haiku-5-5"},
    "openai": {"parts": "gpt-6-astra", "verdict": "gpt-6-astra", "judge": "gpt-6-astra", "search": "gpt-6-luna",
               "screen": "gpt-6-luna"},
    "chat": dict.fromkeys(ROLES),
}
# The API providers' default base URL and key variable.
API = {"anthropic": ("https://api.anthropic.com", "ANTHROPIC_API_KEY"),
       "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
       "chat": ("http://localhost:11434/v1", "CHAT_API_KEY")}
WEB_SEARCH = ("claude", "codex", "anthropic", "openai")  # the providers whose models search the web themselves
SUMMARY_TEMPLATE = Path(__file__).parent / "summary.html"
SHARE_TEXTS = {"es": {"title": "Fichas", "copy": "Texto alternativo, listo para copiar:", "series": "Serie",
                      "apply": "Aplicar", "hint": "por ejemplo 1/3 · Candidatos a la Xunta"},
               "en": {"title": "Cards", "copy": "Alt text, ready to copy:", "series": "Series", "apply": "Apply",
                      "hint": "for example 1/3 · Candidates for mayor"}}
SHARE_PAGE = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{title}</title></head>
<body style="margin:24px;background:#121417;color:#f1f3f5;font:16px -apple-system,Arial,sans-serif">
<form style="margin-bottom:24px"><label>{series_label} <input name="series" value="{series}" placeholder="{hint}"
 style="width:320px"></label> <button>{apply}</button></form>
{cards}
</body></html>"""
SHARE_CARD = """<section style="margin-bottom:32px"><img src="{src}" alt="{alt}" style="display:block;width:540px;max-width:100%">
<p>{copy}</p><textarea rows="8" style="width:540px;max-width:100%" readonly>{alt}</textarea></section>"""


def summary_page(data: dict, name: str, series: str | None = None) -> str:
    """The HTML page of the card of `name`, from the flag file with marks."""
    return summary.page(summary.card(data, name, series), SUMMARY_TEMPLATE.read_text(),
                        thumbnail(data["video_id"], default_home()))


def speech_cli() -> Path | None:
    """The speech-to-text script of this machine: mlx-whisper on Apple silicon, faster-whisper on the CPU of any other
    Mac or Linux machine. None without uv, which runs both."""
    if not shutil.which("uv") or platform.system() not in ("Darwin", "Linux"):
        return None
    return MLX_CLI if (platform.system(), platform.machine()) == ("Darwin", "arm64") else FASTER_CLI


def read_env(home: Path) -> dict:
    """The `KEY=value` lines of `<home>/.env`: the optional keys of a helper that starts at login, with no shell."""
    path = home / ".env"
    lines = path.read_text().splitlines() if path.exists() else []
    return {k.strip(): v.strip().strip("\"'") for k, _, v in (x.partition("=") for x in lines)
            if k.strip() and not k.strip().startswith("#")}


def config(home: Path) -> dict:
    """The settings in `<home>/config.toml`; none without the file."""
    path = home / "config.toml"
    return tomllib.loads(path.read_text()) if path.exists() else {}


def consent(home: Path) -> bool | None:
    """The person's answer to sharing their marks and analyses: `share_marks` in the settings; None until asked."""
    answer = config(home).get("share_marks")
    return answer if isinstance(answer, bool) else None


def sharing(home: Path) -> bool:
    """Whether new marks and whole analyses go to the author's collector: only after the person said yes."""
    return consent(home) is True


def provider(home: Path) -> str:
    """The provider that every reading goes through: FACT_CHECK_PROVIDER, else `provider` in the settings, else
    `claude`."""
    return os.environ.get("FACT_CHECK_PROVIDER") or config(home).get("provider", "claude")


def models(home: Path) -> dict:
    """The model of each role: the settings' `[models]`, else the provider's default."""
    return MODELS[provider(home)] | config(home).get("models", {})


def secret(home: Path, variable: str) -> str | None:
    """The value of a key variable, from the environment or `<home>/.env`."""
    return os.environ.get(variable) or read_env(home).get(variable)


def role(home: Path, name: str) -> dict:
    """The `provider`, `model`, `base_url` and `key_env` of a role of ROLES. Its `[roles.<name>]` table overrides the
    `[<provider>]` table, which overrides the provider's defaults; a role without a table uses `provider` and
    `[models]`. FACT_CHECK_PROVIDER ignores the role tables."""
    settings = config(home)
    table = {} if os.environ.get("FACT_CHECK_PROVIDER") else settings.get("roles", {}).get(name, {})
    used = table.get("provider", provider(home))
    section = settings.get(used, {})
    base_url, key_env = API.get(used, (None, None))
    defaults = models(home) if used == provider(home) else MODELS[used]
    return {"provider": used,
            "model": table.get("model") or defaults[name] or (defaults["parts"] if name == "screen" and used == "chat"
                                                               else None),
            "base_url": table.get("base_url") or section.get("base_url") or base_url,
            "key_env": table.get("key_env") or section.get("key_env") or key_env}


def provider_llm(home: Path, name: str, **options):
    """The LLM of the provider for a role of ROLES."""
    settings = role(home, name)
    if settings["provider"] in API:
        options |= {"key": secret(home, settings["key_env"]), "key_env": settings["key_env"],
                    "base_url": settings["base_url"]}
    else:
        options |= {"workdir": home}
    adapter = {"claude": ClaudeCLI, "codex": CodexCLI, "anthropic": AnthropicAPI, "openai": OpenAIAPI,
               "chat": ChatAPI}[settings["provider"]]
    return adapter(model=settings["model"], **options)


def search_api(home: Path) -> tuple[str, Tavily | None]:
    """The key variable of the search service that a search model with no web search reads, and the service; None
    without its key."""
    settings = config(home).get("tavily", {})
    variable = settings.get("key_env", "TAVILY_API_KEY")
    key = secret(home, variable)
    return variable, key and Tavily(key, **({"base_url": settings["base_url"]} if "base_url" in settings else {}))


def bars_file(home: Path) -> Path:
    """The confidence bars of the provider: it was tuned on its own flags. Claude's are THRESHOLDS."""
    name = provider(home)
    return THRESHOLDS if name == "claude" else THRESHOLDS.with_name(f"thresholds.{name}.json")


def _search(factcheck, query: str, language: str) -> list:
    """Published fact-checks help but are not required: a network error gives none instead of stopping the video."""
    try:
        return factcheck.search(query, language)
    except OSError:
        return []


class Logged:
    """An LLM whose every reading adds a usage line to `lines`: its step, duration, tokens and cost, and the id of the
    conversation it continues, if any."""

    def __init__(self, llm, line, lines: list):
        self.llm, self.line, self.lines = llm, line, lines

    def complete(self, prompt, schema, tools=()):
        t0 = time.monotonic()
        answer = self.llm.complete(prompt, schema, tools=tools) if tools else self.llm.complete(prompt, schema)
        session = getattr(prompt, "session", None)
        self.lines.append(self.line(t0) | getattr(answer, "usage", {}) | ({"session": session.id} if session else {}))
        return answer


def run_analysis(video_id: str, from_t: float, *, transcript, llm, home: Path, factcheck=None, voices=None,
                 thresholds: dict | None = None, judge=None, searcher=None, verdict=None, context_mode: str = "window",
                 viewer: scheduler.Viewer | None = None, web=None, no_check: str | None = None,
                 readers: dict | None = None, lang: str | None = None, screen=None) -> bool:
    """Analyses one video from the playback second and keeps its flag file up to date.

    A part gets what was said before it as a short window (`context_mode` "window": the minutes before it and the
    positions list) or as one conversation that reads the parts in order ("conversation"). With a `viewer`, the
    analysis follows the playback second it hears; without one, it reads the whole video.

    With `voices`, the voices of the whole video are separated and named in the background while the parts are read
    with the speakers told apart from the text; the parts read after that use the voices, every flag takes the name of
    the voice heard at its second, and the file says done only once they are known. With `searcher`, a
    cheaper LLM gathers the evidence of each fact-check and `verdict` (else `llm`, on the same budget) judges it.
    Once every part is done, `judge` (an LLM, off by default) rules on the flags before the file says done. The flag file's `cost_usd` sums the cost of
    every reading. With `web`, a search service, the `searcher` reads its results instead of searching. With
    `no_check`, a reason, no claim is fact-checked and the usage log says why. `readers`, the provider and model of
    each role, goes into the flag file. `lang`, the viewer's language, is the language of every reason and of the
    flag file's `lang`; by default the video's own, which the file keeps in `spoken`. With `screen`, a cheap LLM on a
    budget of its own first decides whether each part gets the full reading; any doubt reads it. A skipped part adds
    its words to what the later parts see, and no position.

    `first_flags_s` in the flag file is the time from the call to the first part written.

    Returns True when the analysis is done and read every caption second: a whole analysis, which may be shared.
    """
    asked = time.monotonic()
    path = bars_file(home)
    bars = thresholds if thresholds is not None else json.loads(path.read_text()) if path.exists() else {}
    store = Store(home)
    # A role the person set survives a later naming of the voices.
    kept = {n: p for n, p in ((store.load(video_id) or {}).get("people") or {}).items() if p.get("set_by") == "person"}
    data = {"video_id": video_id, "published_at": None, "status": "running", "stop_reason": None,
            "analysed_until": from_t, "speakers": {}, "flags": []} | ({"readers": readers} if readers else {}) \
        | ({"lang": lang} if lang else {})
    store.save(data)
    began = time.monotonic()
    cost = [0.0]

    def log(lines):
        for entry in lines:
            store.log_usage(entry)
            cost[0] += entry.get("cost_usd") or 0

    def usage(step, chunk=None):
        def line(t0):
            return {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "video_id": video_id,
                "step": step, "chunk_start": chunk and chunk.start, "duration_s": round(time.monotonic() - t0, 2),
                "lead_s": chunk and round((chunk.start - from_t) - (time.monotonic() - began), 1),
            }
        return line

    if no_check:
        store.log_usage(usage("fact_check")(time.monotonic()) | {"stop_reason": no_check})
        factcheck = None
    try:
        tr = transcript.fetch(video_id)
        spoken, reader = tr.language, lang or tr.language
        budgeted = scheduler.BudgetedLLM(llm, scheduler.budget(tr) + (rulings.calls(tr) if judge else 0))
        searching = searcher and scheduler.BudgetedLLM(searcher, scheduler.budget(tr))
        screening = screen and scheduler.BudgetedLLM(screen, scheduler.budget(tr))
        verdicts = budgeted.through(verdict) if verdict else budgeted
    except Exception as e:
        store.save(data | {"status": "stopped", "stop_reason": f"error: {e}"})
        return False
    store.save(data | {"lang": reader, "spoken": spoken, "published_at": tr.published_at, "speakers": tr.speakers,
                       "title": tr.title, "channel": tr.channel, "duration": tr.duration, "cost_usd": round(cost[0], 6)})

    saving = threading.Lock()  # the parts and the voices both rewrite the flag file
    heard = threading.Event()

    def name_voices(flags) -> None:
        """Each flag takes the name of the voice heard at its second, once the voices are known."""
        for flag in flags:
            if isinstance(flag, dict):
                flag["speaker"] = speakers.voice_at(tr, flag["t"]) or flag["speaker"]
            else:
                flag.speaker = speakers.voice_at(tr, flag.t) or flag.speaker

    def hear_voices():
        """Separates and names the voices, with the role, person and seconds of speech of each; a failure keeps the
        names from the text."""
        nonlocal tr
        lines, t0 = [], time.monotonic()
        try:
            turns = voices.turns(video_id)
            voiced = speakers.assign(tr, turns)
            named = speakers.name(voiced, Logged(budgeted, usage("speakers"), lines), reader)
            voiced = replace(voiced, speakers={v: n["name"] for v, n in named.items()})
            people = speakers.people(named, turns)
            people |= {n: people[n] | {"role": p["role"], "set_by": "person"} for n, p in kept.items() if n in people}
        except Exception as e:
            lines.append(usage("speakers")(t0) | {"stop_reason": f"error: {e}"})
            voiced = None
        try:
            with saving:
                log(lines)
                if voiced and voiced.speakers:
                    tr = voiced
                    shown = store.load(video_id)
                    name_voices(shown["flags"])
                    store.save(shown | {"speakers": tr.speakers, "people": people, "cost_usd": round(cost[0], 6)})
        finally:
            heard.set()

    if voices:
        threading.Thread(target=hear_voices, daemon=True).start()
        heard.wait(VOICES_WAIT)

    positions = []  # what the speakers stated in the parts done so far
    checked = []  # the claims sent to a fact-check so far, which a later claim may repeat
    lock = threading.Lock()
    # In a conversation the parts are read one after another, in the order they are planned.
    session, planned, read, turn = [Session()], [], [0], threading.Condition()
    unread = []  # in a conversation, the words of the skipped parts since the last part read

    def in_order(chunks):
        for chunk in chunks:
            planned.append(chunk.start)
            yield chunk

    def read_part(chunk, llm, earlier, read_it):
        before = [p for p in positions if p.t < chunk.start]
        said = [s for s in tr.segments if s.t < chunk.start]
        if context_mode == "window":
            return analyze_chunk(chunk, scheduler.context_before(tr, chunk), llm, tr.speakers, before, earlier, said=said,
                                 spoken=spoken, reader=reader) if read_it else ChunkResult()
        with turn:
            turn.wait_for(lambda: planned[read[0]] == chunk.start)
        try:
            if not read_it:
                unread.extend(chunk.segments)
                return ChunkResult()
            if session[0].tokens > SESSION_TOKENS:
                session[0] = Session()
            result = analyze_chunk(chunk, list(unread), llm, tr.speakers, before, earlier, session[0], said, spoken,
                                   reader)
            unread.clear()
            return result
        finally:
            with turn:
                read[0] += 1
                turn.notify_all()

    def worth(chunk, lines) -> bool:
        """The screen's answer, logged with the usage line of its reading; only an explicit `read: false` skips."""
        line = usage("screen", chunk)
        t0 = time.monotonic()
        try:
            answer = screen_part(chunk, Logged(screening, line, lines), tr.speakers, spoken, reader)
        except (RuntimeError, OSError) as e:
            lines.append(line(t0) | {"read": True, "stop_reason": f"error: {e}"})
            return True
        lines[-1] |= {"read": answer.get("read") is not False, "reason": answer.get("reason")}
        return lines[-1]["read"]

    def work(chunk):
        if tr.speakers:  # the voices came after the part was planned
            chunk = replace(chunk, segments=[s for s in tr.segments if chunk.start <= s.t < chunk.end])
        lines = []
        read_it = not screening or worth(chunk, lines)
        with lock:
            earlier = list(checked)
        result = read_part(chunk, Logged(budgeted, usage("analyze_chunk", chunk), lines), earlier, read_it)
        positions.extend(result.positions)
        outcomes = ["skipped" if not c.central else "repeated" if c.repeats is not None else "unchecked"
                    for c in result.claims]
        claims = [c for c, o in zip(result.claims, outcomes) if o == "unchecked"]
        with lock:
            checked.extend(claims)
        try:
            if factcheck and claims:
                published = {c.quote: [p for q in c.queries for p in _search(factcheck, q, spoken)] for c in claims}
                flags, done = check_claims(claims, tr.published_at, published,
                                           Logged(verdicts, usage("fact_check", chunk), lines),
                                           searching and Logged(searching, usage("search", chunk), lines), web,
                                           spoken, reader)
                result.flags += flags
                found = iter(done)
                outcomes = [next(found) if o == "unchecked" else o for o in outcomes]
        finally:
            store.add_claims(video_id, result.claims, outcomes)
        return result, lines, [(c.t, c.speaker) for c, o in zip(result.claims, outcomes) if o in ("flagged", "ok")]

    stop = threading.Event()
    chunks = in_order(scheduler.follow(tr, viewer, stop) if viewer else scheduler.plan(tr, from_t))
    finished = []

    def analysed_until():
        """The end of the parts done without a gap from the playback second: a later part done early does not mean
        the earlier one is. A stretch with no caption is no gap."""
        t = viewer.t if viewer else from_t
        while (said := next((s.t for s in tr.segments if s.t >= t), None)) is not None \
                and (done := next((b for a, b in finished if a <= said < b), None)) is not None:
            t = done
        return t

    tally = {"claims": [], "questions": []}  # (second, speaker) of each checked claim and each question asked

    def counts() -> dict:
        """The checked claims and the questions put to each speaker, by the voice heard at each second once the
        voices are known: the card's "de 26" and "de 11"."""
        return {key: dict(Counter(speakers.voice_at(tr, t) or who for t, who in rows))
                for key, rows in tally.items()}

    def on_done(chunk, outcome):
        result, steps, checked = outcome
        for flag in result.flags:
            bar = bars.get(flag.type, DEFAULT_BAR)
            flag.on_player = bar is not None and flag.confidence >= bar
        with saving:
            if tr.speakers:
                name_voices(result.flags)
            store.add_flags(video_id, result.flags)
            store.add_candidates(video_id, result.candidates)
            finished.append((chunk.start, chunk.end))
            log(steps)
            data = store.load(video_id) | {"analysed_until": analysed_until(), "cost_usd": round(cost[0], 6)}
            tally["claims"] += checked
            tally["questions"] += result.questions
            data |= counts()
            data.setdefault("first_flags_s", round(time.monotonic() - asked, 2))
            store.save(data)

    status, reason = scheduler.run(chunks, work, on_done, stop)
    if voices:
        heard.wait()
    data = store.load(video_id)
    if status == "done" and judge:
        lines = []
        data["flags"] = judged(data["flags"], tr, Logged(scheduler.BudgetedLLM(judge, budgeted.left), usage("judge"), lines),
                               reader)
        log(lines)
    store.save(data | counts() | {"status": status, "stop_reason": reason, "cost_usd": round(cost[0], 6)})
    return status == "done" and all(any(a <= s.t < b for a, b in finished) for s in tr.segments)


def judged(flags: list[dict], transcript, llm, reader: str | None = None) -> list[dict]:
    """The flags with the judge's verdict in `judge`, its reasons in `reader`; a failed judge leaves them as found."""
    try:
        verdicts = rulings.judge(flags, transcript, llm, reader)
    except Exception:
        return flags
    return [f | {"judge": verdicts[f["id"]]} if f["id"] in verdicts else f for f in flags]


class Helper:
    def __init__(self, home: Path):
        self.home = home
        self.store = Store(home)
        self.running: set[str] = set()
        self.viewers: dict[str, scheduler.Viewer] = {}
        self.lock = threading.Lock()
        self.sender = threading.Lock()

    def share(self) -> None:
        """Sends the unsent marks to `feedback_url` in a background thread, one sender at a time, so a mark is
        answered at once and two quick marks never go twice. A failure writes no file: the marks wait for the next
        send."""
        def run():
            with self.sender:
                settings = config(self.home)
                if sharing(self.home) and settings.get("feedback_url"):
                    feedback.send(self.home, settings["feedback_url"], save=False)
        threading.Thread(target=run, daemon=True).start()

    def start(self, video_id: str, from_t: float, lang: str | None = None) -> dict:
        with self.lock:
            data = self.store.load(video_id)
            again = data and data["status"] == "stopped" and str(data["stop_reason"]).startswith("error")
            if video_id in self.running or (data and data["status"] != "running" and not again):
                return data or {"video_id": video_id, "status": "running"}
            if again:  # the next poll must not read the old stop and give up
                self.store.save(data | {"status": "running", "stop_reason": None})
            self.running.add(video_id)
            self.viewers[video_id] = scheduler.Viewer(from_t)
        threading.Thread(target=self._run, args=(video_id, from_t),
                         kwargs={"viewer": self.viewers[video_id], "lang": lang}, daemon=True).start()
        return {"video_id": video_id, "status": "running"}

    def heard(self, video_id: str, t: float) -> None:
        """The extension's poll says the person is at second `t` of the video."""
        viewer = self.viewers.get(video_id)
        if viewer:
            viewer.hear(t)

    def _run(self, video_id: str, from_t: float, context_mode: str | None = None,
             viewer: scheduler.Viewer | None = None, lang: str | None = None) -> None:
        try:
            key = os.environ.get("FACT_CHECK_API_KEY")
            audio = YouTube(self.home / "audio")
            voices = Diarizer(self.home / "voices", audio) if os.environ.get("HF_TOKEN") else None
            cli = speech_cli()
            speech = Whisper(self.home / "speech", audio, cli) if cli else None
            web = no_check = None
            if role(self.home, "search")["provider"] not in WEB_SEARCH:
                variable, web = search_api(self.home)
                no_check = None if web else f"{variable} is not set"
            if context_mode is None:
                context_mode = "window" if role(self.home, "parts")["provider"] == "chat" else CONTEXT_MODE
            screen = provider_llm(self.home, "screen") if config(self.home).get("screen", True) is not False else None
            whole = run_analysis(video_id, from_t, transcript=YouTube(self.home / "captions", speech),
                         llm=provider_llm(self.home, "parts"), verdict=provider_llm(self.home, "verdict"),
                         home=self.home, judge=provider_llm(self.home, "judge", timeout=rulings.TIMEOUT),
                         searcher=provider_llm(self.home, "search"),
                         factcheck=GoogleFactCheck(key) if key else None, voices=voices,
                         context_mode=context_mode, viewer=viewer, web=web, no_check=no_check,
                         readers={r: {k: role(self.home, r)[k] for k in ("provider", "model")} for r in ROLES},
                         lang=lang, screen=screen)
            url = config(self.home).get("feedback_url")
            if whole and url and sharing(self.home):
                try:
                    analyses.upload(self.home, url, self.store.load(video_id))
                except (OSError, ValueError):  # refused (a better analysis is kept) or no answer: the flags stay local
                    pass
        finally:
            with self.lock:
                self.running.discard(video_id)
                self.viewers.pop(video_id, None)


def handler(helper: Helper):
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, code: int, body: dict | None) -> None:
            raw = json.dumps(body or {}, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _video(self):
            url = urlparse(self.path)
            m = re.fullmatch(r"/videos/([^/]+)", url.path)
            if not m or not VIDEO_ID.fullmatch(m[1]):
                self._reply(404, {"error": "not found"})
                return None, None
            return m[1], parse_qs(url.query)

        def _send(self, raw: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _flag_file(self, video_id: str) -> dict | None:
            data = helper.store.load(video_id)
            if data:
                marks = helper.store.marks(video_id)
                data["flags"] = [f | {"mark": marks[f["id"]]} if f["id"] in marks else f for f in data["flags"]]
            return data

        def _summary(self, video_id: str, kind: str, query: dict) -> None:
            """The page of one card per guest, or the PNG or alt text of the card of `person` (the first guest by
            default); `series` adds the series line."""
            data = self._flag_file(video_id)
            if not data:
                return self._reply(404, {"error": "not analysed"})
            guests = summary.guests(data)
            series = query.get("series", [""])[0].strip()[:80]
            if not kind:
                words = SHARE_TEXTS[data.get("lang") or "es"]
                cards = "".join(SHARE_CARD.format(
                    src=html.escape("summary.png?" + urlencode({"person": g} | ({"series": series} if series else {}))),
                    alt=html.escape(summary.alt_text(summary.card(data, g, series))), copy=words["copy"])
                    for g in guests)
                page = SHARE_PAGE.format(lang=data.get("lang") or "es", cards=cards, series=html.escape(series),
                                         series_label=words["series"], title=words["title"], hint=words["hint"],
                                         apply=words["apply"])
                return self._send(page.encode(), "text/html; charset=utf-8")
            name = query.get("person", guests[:1])[0] if guests else None
            if name not in guests:
                return self._reply(404, {"error": "unknown person"})
            if kind == ".png":
                return self._send(screenshot(summary_page(data, name, series)), "image/png")
            self._send(summary.alt_text(summary.card(data, name, series)).encode(), "text/plain; charset=utf-8")

        def _health(self) -> None:
            """Says that this is fact-checker, and whether it can write its home: a sandboxed start cannot."""
            try:
                with tempfile.TemporaryFile(dir=helper.home):
                    writable = True
            except OSError:
                writable = False
            self._reply(200, {"app": "fact-checker", "version": feedback.helper_version(), "pid": os.getpid(),
                              "home": str(helper.home), "writable": writable})

        def do_GET(self):
            if urlparse(self.path).path == "/health":
                return self._health()
            if urlparse(self.path).path == "/share":
                return self._reply(200, {"share": consent(helper.home)})
            if urlparse(self.path).path == "/provider":  # the analyse button says what a reading spends
                return self._reply(200, {"provider": role(helper.home, "parts")["provider"]})
            m = re.fullmatch(r"/videos/([A-Za-z0-9_-]{6,20})/summary(\.png|\.txt)?", urlparse(self.path).path)
            if m:
                return self._summary(m[1], m[2], parse_qs(urlparse(self.path).query))
            video_id, query = self._video()
            if video_id:
                if "at" in query:
                    try:
                        helper.heard(video_id, max(0.0, float(query["at"][0])))
                    except ValueError:
                        return self._reply(400, {"error": "bad at"})
                data = self._flag_file(video_id) or self._shared(video_id, query.get("lang", [None])[0])
                if not data:
                    return self._reply(404, {"error": "not analysed"})
                self._reply(200, data)

        def _shared(self, video_id: str, lang: str | None) -> dict | None:
            """The shared analysis of a video with no local flag file, in the viewer's language, kept with `source`
            "shared"; None without `lang` or `feedback_url`, or when the collector has none."""
            url = config(helper.home).get("feedback_url")
            if lang not in NAMES or not url:
                return None
            shared = analyses.download(url, video_id, lang)
            if not shared:
                return None
            helper.store.save(shared | {"source": "shared"})
            return self._flag_file(video_id)

        def _mark(self, video_id: str) -> None:
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            except (ValueError, json.JSONDecodeError):
                return self._reply(400, {"error": "bad json"})
            if body.get("verdict") not in ("correct", "unfair"):
                return self._reply(400, {"error": "bad verdict"})
            data = helper.store.load(video_id)
            flag = next((f for f in (data or {}).get("flags", []) if f["id"] == body.get("flag_id")), None)
            if not flag:
                return self._reply(404, {"error": "unknown flag"})
            shared = sharing(helper.home)
            helper.store.add_mark(video_id, flag, body["verdict"], str(body.get("reason", ""))[:500], shared)
            if shared:
                helper.share()
            self._reply(200, {"ok": True})

        def _people(self, video_id: str) -> None:
            """The person sets the role of one speaker; a later naming of the voices keeps it."""
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            except (ValueError, json.JSONDecodeError):
                return self._reply(400, {"error": "bad json"})
            data = helper.store.load(video_id)
            if not data:
                return self._reply(404, {"error": "not analysed"})
            name = body.get("name")
            if name not in data.get("speakers", {}).values():
                return self._reply(400, {"error": "unknown speaker"})
            if body.get("role") not in ("host", "guest"):
                return self._reply(400, {"error": "bad role"})
            people = data.get("people") or {}
            people[name] = people.get(name, {"person": name}) | {"role": body["role"], "set_by": "person"}
            helper.store.save(data | {"people": people})
            self._reply(200, {"people": people})

        def _share(self) -> None:
            try:
                on = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))["share"]
            except (ValueError, KeyError, TypeError):
                return self._reply(400, {"error": "bad json"})
            if not isinstance(on, bool):
                return self._reply(400, {"error": "bad share"})
            feedback.set_share(helper.home, on)
            self._reply(200, {"share": on})

        def do_POST(self):
            if urlparse(self.path).path == "/share":
                return self._share()
            m = re.fullmatch(r"/videos/([A-Za-z0-9_-]{6,20})/(marks|people)", urlparse(self.path).path)
            if m:
                return self._mark(m[1]) if m[2] == "marks" else self._people(m[1])
            video_id, query = self._video()
            if video_id:
                try:
                    from_t = max(0.0, float(query.get("from", ["0"])[0]))
                except ValueError:
                    return self._reply(400, {"error": "bad from"})
                lang = query.get("lang", [None])[0]
                if lang is not None and lang not in NAMES:
                    return self._reply(400, {"error": "bad lang"})
                self._reply(202, helper.start(video_id, from_t, lang))

        def log_message(self, *args):
            pass

    return Handler


def ports() -> range:
    """The five ports the helper tries in order: 8765–8769, or five from FACT_CHECKER_PORT."""
    first = int(os.environ.get("FACT_CHECKER_PORT", 8765))
    return range(first, first + 5)


def serve(port: int | None = None) -> None:
    """Serves on `port`, or on the first free port of `ports()`; with all five taken, says so and ends with exit 0,
    so the login agent does not start it again."""
    for key, value in read_env(default_home()).items():
        os.environ.setdefault(key, value)
    helper = Helper(default_home())
    tries = [port] if port else ports()
    for candidate in tries:
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", candidate), handler(helper))
            break
        except OSError as e:
            if e.errno != errno.EADDRINUSE or port:
                raise
    else:
        print(f"fact-checker helper: ports {tries[0]}–{tries[-1]} are all taken by other programs; stopping", flush=True)
        raise SystemExit(0)
    print(f"fact-checker helper on http://127.0.0.1:{candidate}", flush=True)
    helper.share()  # the marks that waited for a collector that did not answer
    httpd.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(prog="fact-checker serve")
    parser.add_argument("--port", type=int)
    serve(parser.parse_args().port)


if __name__ == "__main__":
    main()
