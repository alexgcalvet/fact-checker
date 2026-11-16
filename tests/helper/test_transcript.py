"""The transcript: captions, audio through Whisper, and the voices that name each speaker."""
import json
import os
import platform
import shutil
import sys
import threading
import time
from pathlib import Path

import pytest

from fact_checker import server
from fact_checker.adapters.whisper import Whisper
from fact_checker.adapters.youtube import YouTube
from fact_checker.core import scheduler, summary
from fact_checker.core.flags import Segment, Transcript
from fact_checker.server import run_analysis
from first_part_fakes import (
    FakeModel,
    FakeTranscript,
    flag_file,
    GUEST_QUOTE,
    HOST_QUOTE,
    LATE_QUOTE,
    SlowVoices,
    speaker_of,
    wait_for,
)
from roles_fakes import (
    FakeModel as FakeModel_roles,
    FakeTranscript as FakeTranscript_roles,
    FakeVoices,
    GUEST,
    HOST,
    NOISE,
    TITLE,
)


# S5 A2 · A card names the voice that said its words
#
# Story: In an invented interview the host says "la oposición no tiene autoridad para hablar". The model
# calls it an ad hominem by the guest. The card says the host said it, because the audio puts those words
# in the host's voice.
# Edge case: when the quoted words cross from one voice to the other, no card is made.
#
# Setup: invented word-by-word captions of a host (0-10 s) and a guest (10-20 s); fake voice turns that
# put the first ten seconds in voice SPEAKER_00 and the rest in SPEAKER_01; a fake Claude that names the
# voices "Presentadora" and "Invitado", and in the part call returns two ad hominem flags, both pinned on
# the guest: one on the host's words, one on words that cross from the host to the guest; a temporary
# helper home.

HOST_s5a2 = "Mucha gente dice que la oposición no tiene autoridad para hablar de vivienda"
GUEST_s5a2 = "Nosotros hemos construido más viviendas que ningún otro gobierno"


def words(start, text):
    return [Segment(t=start + i * 0.5, text=w) for i, w in enumerate(text.split())]


class FakeTranscript_s5a2:
    def fetch(self, video_id):
        return Transcript(segments=words(0, HOST_s5a2) + words(10, GUEST_s5a2), published_at="2026-11-10")


class FakeVoices_s5a2:
    def turns(self, video_id):
        return [{"start": 0.0, "end": 9.8, "speaker": "SPEAKER_00"},
                {"start": 9.9, "end": 20.0, "speaker": "SPEAKER_01"}]


def flag(quote):
    return {"quote": quote, "label": "ad_hominem", "speaker": "Invitado", "reason": "Ataca a la oposición.",
            "confidence": 0.9}


class FakeClaude:
    def complete(self, prompt, schema, tools=()):
        if "speakers" in schema["properties"]:
            return {"speakers": [{"voice": "SPEAKER_00", "name": "Presentadora"},
                                 {"voice": "SPEAKER_01", "name": "Invitado"}]}
        if "verdicts" in schema["properties"]:
            return {"verdicts": []}
        return {"flags": [flag("la oposición no tiene autoridad para hablar"),
                          flag("hablar de vivienda Nosotros hemos construido")], "claims": []}


def test_speaker_from_voice(tmp_path):
    run_analysis("voices", 0, transcript=FakeTranscript_s5a2(), llm=FakeClaude(), home=tmp_path, voices=FakeVoices_s5a2())
    data = json.loads((tmp_path / "videos" / "voices.json").read_text())
    flags = data["flags"]

    # Case 1 · the model pins the host's words on the guest → the card names the host, from the voice
    host = [f for f in flags if f["quote"] == "la oposición no tiene autoridad para hablar"]
    assert len(host) == 1, flags
    assert host[0]["speaker"] == "Presentadora"

    # Case 2 · the quoted words cross from the host's voice to the guest's → no card
    assert not [f for f in flags if "Nosotros" in f["quote"]], flags
    assert len(flags) == 1
    print("PASS S5 A2 · A card names the voice that said its words")


# S12 A1 · A video with no Spanish captions is analysed from its audio
#
# Story: The helper analyses an invented video whose captions exist only in English. It transcribes the
# audio instead and the flag file gets a fallacy flag at the second where the transcript puts the words,
# with the publish date of the video.
# Edge case: when the video has Spanish captions, the audio is not transcribed.
#
# Setup: a fake yt-dlp on the PATH that prints the publish date 20240315 and writes Spanish captions only
# for the video "captioned" (the invented dialogue of tests/fakes/youtube/); the YouTube adapter with the
# Whisper adapter as its fallback; the Whisper transcript of the video "uncaptioned" already cached in the
# helper home from the synthetic fake tests/fakes/whisper/transcribe.json, where "autoridad" has a low
# probability; an audio source that records each request; a fake Claude that flags "La oposición no tiene
# autoridad para hablar." as an ad hominem; a temporary helper home.

FAKES = Path(__file__).parents[1] / "fakes"

FAKE_YTDLP = f"""#!/usr/bin/env python3
import shutil, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1].replace("%(id)s", "")
video = args[-1].split("v=")[-1]
if video == "captioned":
    shutil.copy("{FAKES / 'youtube' / 'invented-dialogue.json3'}", out + "captioned.es.json3")
print("20240315")
"""


class Audio:
    def __init__(self):
        self.requests = []

    def audio(self, video_id):
        self.requests.append(video_id)
        raise RuntimeError("no audio in this test")


class FakeClaude_s12a1:
    def complete(self, prompt, schema, tools=()):
        if "verdicts" in schema["properties"]:
            return {"verdicts": []}
        return {"flags": [{"quote": "La oposición no tiene autoridad para hablar.", "label": "ad_hominem",
                           "speaker": "ministro", "reason": "Ataca a la oposición.", "confidence": 0.9}],
                "claims": []}


def helper(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "yt-dlp").write_text(FAKE_YTDLP)
    (bin_dir / "yt-dlp").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    speech = tmp_path / "home" / "speech"
    speech.mkdir(parents=True)
    shutil.copy(FAKES / "whisper" / "transcribe.json", speech / "uncaptioned.words.json")
    audio = Audio()
    youtube = YouTube(tmp_path / "home" / "captions", speech=Whisper(speech, audio))
    return youtube, audio, tmp_path / "home"


def test_audio_when_no_captions(tmp_path, monkeypatch):
    youtube, audio, home = helper(tmp_path, monkeypatch)

    # Case 1 · no Spanish captions → the fallacy quotes the Whisper words, at the second of the first word
    run_analysis("uncaptioned", 0, transcript=youtube, llm=FakeClaude_s12a1(), home=home)
    data = json.loads((home / "videos" / "uncaptioned.json").read_text())
    assert data["status"] == "done", data
    assert [(f["label"], f["quote"]) for f in data["flags"]] == [
        ("ad_hominem", "La oposición no tiene autoridad para hablar.")], data["flags"]
    assert abs(data["flags"][0]["t"] - 12.4) < 0.01

    # Case 2 · the captions step still gives the date → the publish date of the video
    assert data["published_at"] == "2024-03-15"

    # Case 3 · Spanish captions exist → the audio is not requested and the captions are analysed
    run_analysis("captioned", 0, transcript=youtube, llm=FakeClaude_s12a1(), home=home)
    data = json.loads((home / "videos" / "captioned.json").read_text())
    assert data["status"] == "done", data
    assert audio.requests == []
    assert not (home / "speech" / "captioned.words.json").exists()
    assert abs(data["flags"][0]["t"] - 42.0) < 0.01
    print("PASS S12 A1 · A video with no Spanish captions is analysed from its audio")


# S21 A2 · A video without captions uses the speech engine of the machine
#
# Story: The helper analyses an invented video with no Spanish captions. On an Apple silicon Mac it transcribes the audio
# with mlx-whisper; on an Intel Mac or on Linux, with faster-whisper; the flags come from the transcribed words in both
# cases.
# Edge case: WHEN the machine has no speech engine (no uv) THEN the analysis stops with the reason "no Spanish captions,
# and no speech engine on this machine: run fact-checker doctor".
#
# Setup: the helper runs as it does for the person (Helper._run), in a temporary helper home per machine, with PATH
# holding only a folder of fake commands: `yt-dlp` (prints the publish date and writes no captions), `uv` (writes the
# synthetic words of tests/fakes/whisper/transcribe.json to its last argument and logs the script it runs) and `claude`
# (flags "La oposición no tiene autoridad para hablar." as an ad hominem, answers every other reading with nothing).
# The operating system and the processor are set by replacing platform.system and platform.machine. No Hugging Face
# token and no Fact Check Tools API key.

WORDS = Path(__file__).parents[1] / "fakes" / "whisper" / "transcribe.json"
QUOTE = "La oposición no tiene autoridad para hablar."

FAKE_YTDLP_s21a2 = """\
print("20240315")
"""
FAKE_UV = f"""\
import json, os, shutil, sys
with open(os.environ["FAKE_UV_LOG"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
shutil.copy({str(WORDS)!r}, sys.argv[-1])
"""
FAKE_CLAUDE = f"""\
import json, sys
args = sys.argv[1:]
schema = json.loads(args[args.index("--json-schema") + 1])["properties"]
answer = {{k: [] for k in schema}}
if "flags" in schema:
    answer["flags"] = [{{"quote": {QUOTE!r}, "label": "ad_hominem", "speaker": "ministro",
                        "reason": "Ataca a la oposición.", "confidence": 0.9}}]
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "api_error_status": None,
                  "total_cost_usd": 0.0, "usage": {{"input_tokens": 1, "cache_creation_input_tokens": 0,
                  "cache_read_input_tokens": 0, "output_tokens": 1}}, "result": json.dumps(answer), "structured_output": answer}}))
"""


def fake_bin(tmp_path, with_uv: bool) -> Path:
    bin_dir = tmp_path / ("bin-uv" if with_uv else "bin")
    bin_dir.mkdir()
    for name, code in {"yt-dlp": FAKE_YTDLP_s21a2, "claude": FAKE_CLAUDE, **({"uv": FAKE_UV} if with_uv else {})}.items():
        (bin_dir / name).write_text(f"#!{sys.executable}\n{code}")
        (bin_dir / name).chmod(0o755)
    return bin_dir


def analyse(tmp_path, monkeypatch, system, machine, with_uv=True) -> tuple[dict, list]:
    home = tmp_path / f"{system}-{machine}-{with_uv}"
    home.mkdir()
    log = home / "uv.jsonl"
    monkeypatch.setenv("PATH", str(fake_bin(home, with_uv)))
    monkeypatch.setenv("FAKE_UV_LOG", str(log))
    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.setattr(platform, "machine", lambda: machine)
    server.Helper(home)._run("sincaption", 0)
    data = json.loads((home / "videos" / "sincaption.json").read_text())
    return data, [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []


@pytest.fixture
def no_keys(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("FACT_CHECK_API_KEY", raising=False)


@pytest.mark.parametrize("system, machine, script", [
    ("Darwin", "arm64", "whisper_cli.py"),
    ("Darwin", "x86_64", "faster_whisper_cli.py"),
    ("Linux", "x86_64", "faster_whisper_cli.py"),
    ("Linux", "aarch64", "faster_whisper_cli.py"),
])
@pytest.mark.usefixtures("no_keys")
def test_engine_of_the_machine(tmp_path, monkeypatch, system, machine, script):
    # Case 1 · no Spanish captions on this machine → its engine transcribes the audio, the flag quotes its words
    data, runs = analyse(tmp_path, monkeypatch, system, machine)
    assert data["status"] == "done", f"FAIL S21 A2 · {system} {machine}: {data['status']} ({data['stop_reason']})"
    scripts = [Path(a).name for r in runs for a in r if a.endswith(".py")]
    assert scripts == [script], f"FAIL S21 A2 · {system} {machine} ran {scripts}, not {script}"
    flags = [f for f in data["flags"] if f["label"] == "ad_hominem"]
    assert flags and flags[0]["quote"] == QUOTE, f"FAIL S21 A2 · {system} {machine}: flags {data['flags']}"


@pytest.mark.usefixtures("no_keys")
def test_no_engine(tmp_path, monkeypatch):
    # Case 2 · no Spanish captions and no uv → stopped, with the reason that names the doctor
    data, runs = analyse(tmp_path, monkeypatch, "Linux", "x86_64", with_uv=False)
    assert data["status"] == "stopped", f"FAIL S21 A2 · status {data['status']} with no engine"
    assert "no Spanish captions, and no speech engine on this machine: run fact-checker doctor" in data["stop_reason"], \
        f"FAIL S21 A2 · stop reason {data['stop_reason']!r}"
    print("PASS S21 A2 · A video without captions uses the speech engine of the machine")


# S31 A1 · The first part is read before the voices are known
#
# Story: The helper analyses an invented 12-minute interview from second 0, with a speaker separation that takes 5
# seconds and part readings that take 0.2 seconds. The flag of the first 30 seconds is in the flag file before the
# speaker separation ends. When the person reaches minute 7, the part at minute 11 is read with the voice names
# ("[Invitado]") in its text.
#
# Setup: invented word-by-word captions with no voices (one word every 0.5 s): the host's ad hominem at 0:00, the
# guest's at 0:12, a line at 3:20 and the guest's last ad hominem at 11:00. A fake speaker separation that takes 5 s and
# puts 0-10 s in the host's voice and the rest in the guest's. A fake model whose part readings take 0.2 s and that
# names the voices "Presentadora" and "Invitado". The analysis runs as the helper runs it for the extension: in a thread,
# following a viewer at second 0, so no part starts more than 10 minutes ahead of the playback second. A temporary
# helper home.

def test_first_part_first(tmp_path):
    voices, model, viewer = SlowVoices(5), FakeModel(), scheduler.Viewer(0)
    began = time.monotonic()
    run = threading.Thread(target=run_analysis, args=("primero1", 0), daemon=True,
                           kwargs={"transcript": FakeTranscript(), "llm": model, "home": tmp_path, "voices": voices,
                                   "viewer": viewer})
    run.start()

    # Case 1 · the speaker separation takes 5 s → the flag of the first 30 seconds is in the flag file before it ends
    shown = wait_for(lambda: speaker_of(flag_file(tmp_path, "primero1"), HOST_QUOTE), timeout=4.5)
    assert shown and not voices.done.is_set(), \
        f"FAIL S31 A1 · no first-part flag before the voices ({time.monotonic() - began:.1f} s)"
    assert time.monotonic() - began < 5

    # Case 2 · the voices end; the person reaches minute 7 → the part at minute 11 is read with the voice names
    assert wait_for(lambda: (flag_file(tmp_path, "primero1") or {}).get("speakers"), timeout=10), \
        "FAIL S31 A1 · the voices never reached the flag file"
    viewer.hear(420)
    run.join(timeout=20)
    assert not run.is_alive(), "FAIL S31 A1 · the analysis did not end"
    late = [p for p in model.parts if LATE_QUOTE in p]
    assert late and "[Invitado]" in late[0], f"FAIL S31 A1 · the part at minute 11 has no voice names: {late}"
    data = flag_file(tmp_path, "primero1")
    assert data["status"] == "done", data
    assert speaker_of(data, LATE_QUOTE) == "Invitado", data["flags"]

    # Case 3 · the first part was read once, without voice names
    first = [p for p in model.parts if HOST_QUOTE in p]
    assert len(first) == 1 and "[" not in first[0], f"FAIL S31 A1 · first part readings: {first}"
    print("PASS S31 A1 · The first part is read before the voices are known")


# S31 A2 · A flag shown before the voices are known gets the voice's name
#
# Story: In the same interview, the reading of the first part pins the host's ad hominem at second 1 on "Invitado". Once
# the voices are known, the flag file names "Presentadora" for that flag, with the same id; a flag whose name already
# matches its voice keeps it.
# Edge case: WHEN there is no Hugging Face token (no speaker separation) THEN the flags keep the names from the text and
# no speakers reading runs.
#
# Setup: the invented interview of S31 A1 (captions with no voices; the host's ad hominem at 0:00, the guest's at 0:12,
# the guest's last at 11:00), read whole with no viewer. A fake speaker separation that takes 4 s and puts 0-10 s in the
# host's voice and the rest in the guest's. A fake model whose part readings take 0.2 s, that pins the host's words on
# "Invitado" and names the voices "Presentadora" and "Invitado". A second run has no speaker separation. A temporary
# helper home per run.

def test_names_corrected(tmp_path):
    voices, model = SlowVoices(4), FakeModel()
    run = threading.Thread(target=run_analysis, args=("nombres1", 0), daemon=True,
                           kwargs={"transcript": FakeTranscript(), "llm": model, "home": tmp_path / "voices",
                                   "voices": voices})
    run.start()

    # Case 1 · before the voices are known → the host's flag is shown with the name from the text, "Invitado"
    shown = wait_for(lambda: speaker_of(flag_file(tmp_path / "voices", "nombres1"), HOST_QUOTE), timeout=3.5)
    assert shown == "Invitado" and not voices.done.is_set(), f"FAIL S31 A2 · shown before the voices as {shown}"
    before = next(f for f in flag_file(tmp_path / "voices", "nombres1")["flags"] if f["quote"] == HOST_QUOTE)

    # Case 2 · the voices are known → the same flag (same id) names "Presentadora"; the guest's flag keeps "Invitado"
    run.join(timeout=15)
    data = flag_file(tmp_path / "voices", "nombres1")
    after = next(f for f in data["flags"] if f["quote"] == HOST_QUOTE)
    assert after["speaker"] == "Presentadora", f"FAIL S31 A2 · the shown flag still names {after['speaker']}"
    assert after["id"] == before["id"] and after["t"] == before["t"] and after["reason"] == before["reason"], after
    assert speaker_of(data, GUEST_QUOTE) == "Invitado", data["flags"]
    assert data["status"] == "done" and data["speakers"] == {"SPEAKER_00": "Presentadora", "SPEAKER_01": "Invitado"}

    # Case 3 · no speaker separation → the flags keep the names from the text; no speakers reading
    model = FakeModel()
    run_analysis("nombres1", 0, transcript=FakeTranscript(), llm=model, home=tmp_path / "text")
    data = flag_file(tmp_path / "text", "nombres1")
    assert speaker_of(data, HOST_QUOTE) == "Invitado" and model.speakers_readings == 0, \
        f"FAIL S31 A2 · without voices: {data['flags']}"
    print("PASS S31 A2 · A flag shown before the voices are known gets the voice's name")


# S33 A1 · Each voice gets a role, a person and its seconds of speech
#
# Story: The person analyses an invented interview where the host opens with "Buenos días, hoy está con nosotros Ana
# Ruiz". The flag file lists the host as `host` and Ana Ruiz as `guest` with the person "Ana Ruiz", and the seconds each
# one speaks, for example 1260 and 2460.
# Edge case: WHEN the voices cannot be separated THEN the file has no people, and the export gives a card for every speaker
# (S35).
#
# Setup: the invented interview of roles_fakes, with the title "Entrevista inventada a Ana Ruiz"; voice turns that give the
# host 1260 s, Ana Ruiz 2460 s and a third voice 30 s; a fake model that names the host "Presentador" (role host, person
# "Presentador") and the guest "Ana Ruiz (invitada)" (role guest, person "Ana Ruiz"); a temporary helper home. The edge
# case runs the same interview with no voice separation, then adds one flag marked correct for each of two speakers.

NAMED = {HOST: ("Presentador", "host", "Presentador"), GUEST: ("Ana Ruiz (invitada)", "guest", "Ana Ruiz"),
         NOISE: ("Técnico", "guest", "Técnico")}


def flag_s33a1(id, t, speaker):
    return {"id": id, "t": t, "speaker": speaker, "quote": f"frase inventada {id}", "type": "fallacy",
            "label": "ad_hominem", "reason": "Motivo inventado.", "confidence": 0.9, "related": None, "sources": [],
            "note": None, "on_player": True, "mark": "correct"}


def test_people_in_flag_file(tmp_path):
    model = FakeModel_roles(NAMED)
    run_analysis("entrevista", 0, transcript=FakeTranscript_roles(), llm=model, home=tmp_path, voices=FakeVoices())
    data = json.loads((tmp_path / "videos" / "entrevista.json").read_text())
    people = data.get("people")
    assert people, f"FAIL S33 A1 · the flag file has no people: {sorted(data)}"

    # Case 1 · the host's voice → role host, the person is the label, 1260 s of speech, set by the reading
    assert people.get("Presentador") == {"role": "host", "person": "Presentador", "spoken_s": 1260,
                                         "set_by": "llm"}, f"FAIL S33 A1 · host entry {people.get('Presentador')}"

    # Case 2 · the guest's voice → role guest, person "Ana Ruiz", 2460 s of speech
    assert people.get("Ana Ruiz (invitada)") == {"role": "guest", "person": "Ana Ruiz", "spoken_s": 2460,
                                                 "set_by": "llm"}, f"FAIL S33 A1 · guest entry {people}"

    # Case 3 · a voice under 5 % of the talk → no entry
    assert set(people) == {"Presentador", "Ana Ruiz (invitada)"}, f"FAIL S33 A1 · entries {sorted(people)}"

    # Case 4 · the speaker reading → asks a role (host or guest) and a person, and sees the video title
    assert len(model.readings) == 1, f"FAIL S33 A1 · {len(model.readings)} speakers readings"
    item = model.readings[0]["schema"]["properties"]["speakers"]["items"]
    assert item["properties"]["role"]["enum"] == ["host", "guest"], f"FAIL S33 A1 · role schema {item['properties']}"
    assert {"role", "person"} <= set(item["required"]), f"FAIL S33 A1 · required {item['required']}"
    assert TITLE in model.readings[0]["prompt"], "FAIL S33 A1 · the speakers reading does not see the video title"

    # Case 5 · no voice separation → no people in the file, and a card for every speaker
    run_analysis("sinvoces", 0, transcript=FakeTranscript_roles(), llm=FakeModel_roles(NAMED), home=tmp_path)
    plain = json.loads((tmp_path / "videos" / "sinvoces.json").read_text())
    assert "people" not in plain, f"FAIL S33 A1 · a file with no voices has people: {plain['people']}"
    shown = summary.guests(plain | {"flags": [flag_s33a1("a-10.0", 10.0, "Presentador"), flag_s33a1("b-20.0", 20.0, "Ana Ruiz")]})
    assert shown == ["Presentador", "Ana Ruiz"], f"FAIL S33 A1 · the export gives cards for {shown}"
    print("PASS S33 A1 · Each voice gets a role, a person and its seconds of speech")


# YouTube may refuse one caption track (HTTP 429 on an automatic translation) while yt-dlp already wrote another:
# the video is read from the track it has, not failed.

TRACK = {"events": [{"tStartMs": 0, "dDurationMs": 2000, "segs": [{"utf8": "hola a todos"}]}]}


def fake_ytdlp(tmp_path, monkeypatch, write: bool):
    script = tmp_path / "bin" / "yt-dlp"
    script.parent.mkdir()
    out = tmp_path / "captions" / "vid123"
    body = f"echo '{json.dumps(TRACK)}' > {out}/vid123.es-orig.json3\n" if write else ""
    script.write_text(f"#!/bin/sh\nmkdir -p {out}\n{body}printf '20261114\\t891\\tCanal\\tTitulo\\n'\n"
                      "echo 'ERROR: Unable to download video subtitles for en: HTTP Error 429' >&2\nexit 1\n")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{script.parent}{os.pathsep}{os.environ['PATH']}")


def test_a_refused_track_does_not_fail_the_video(tmp_path, monkeypatch):
    fake_ytdlp(tmp_path, monkeypatch, write=True)
    transcript = YouTube(tmp_path / "captions").fetch("vid123")
    assert transcript.language == "es" and transcript.title == "Titulo"


def test_no_track_at_all_still_fails(tmp_path, monkeypatch):
    fake_ytdlp(tmp_path, monkeypatch, write=False)
    with pytest.raises(Exception):
        YouTube(tmp_path / "captions").fetch("vid123")
