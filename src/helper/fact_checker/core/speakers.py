import bisect
from dataclasses import replace

from fact_checker.core.flags import Prompt, Segment, Transcript
from fact_checker.core.languages import NAMES, ROLES

MAIN_SHARE = 0.05
OPENING = 600

SCHEMA = {
    "type": "object",
    "properties": {
        "speakers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"voice": {"type": "string"}, "name": {"type": "string"},
                               "role": {"type": "string", "enum": ["host", "guest"]}, "person": {"type": "string"}},
                "required": ["voice", "name", "role", "person"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["speakers"],
    "additionalProperties": False,
}

PROMPT = """Below is the opening of a {spoken} video. Each line starts with a voice label from the audio.
Name each voice: the person's name if the conversation says it, followed by the role in {reader} in brackets, such
as {named} or {role}. Use a role alone when no name is said. Two voices never get
the same name.
Give each voice its role: "host" for whoever leads the conversation and asks the questions, "guest" for everyone else.
In a debate, only a moderator is "host"; every debater is "guest", even one who asks the other questions.
Give each voice its person: the full name of that person, from the conversation, else from the video title; the
voice's name when neither says it.

Video title: {title}
Voices: {voices}
Do not use any tool. Answer only with the JSON.

{opening}
"""


def assign(transcript: Transcript, turns: list[dict]) -> Transcript:
    """Gives each word the voice of its turn, or of the nearest turn. Voices under MAIN_SHARE of the talk are noise."""
    talk: dict[str, float] = {}
    for turn in turns:
        talk[turn["speaker"]] = talk.get(turn["speaker"], 0) + turn["end"] - turn["start"]
    total = sum(talk.values())
    main = sorted((t for t in turns if talk[t["speaker"]] >= MAIN_SHARE * total), key=lambda t: t["start"])
    if not main:
        return transcript
    starts = [t["start"] for t in main]

    def voice(t: float) -> str:
        i = bisect.bisect_right(starts, t) - 1
        near = [main[j] for j in (i, i + 1) if 0 <= j < len(main)]
        return min(near, key=lambda turn: max(turn["start"] - t, t - turn["end"], 0))["speaker"]

    return replace(transcript, segments=[replace(s, speaker=voice(s.t)) for s in transcript.segments])


def labeled(segments: list[Segment], names: dict[str, str]) -> str:
    """The words, with a `[speaker]` line start at each change of voice."""
    lines: list[list[str]] = []
    current = None
    for s in segments:
        if s.speaker and s.speaker != current or not lines:
            current = s.speaker
            lines.append([f"[{names.get(current, current)}]"] if current else [])
        lines[-1].append(s.text.strip())
    return "\n".join(" ".join(line) for line in lines)


def name(transcript: Transcript, llm, reader: str | None = None) -> dict[str, dict]:
    """Voice → {name, role, person}, from the opening of the conversation and the video title, in one model call. The
    name is the person's or a role in `reader`, by default the language of the conversation; the role is `host` or
    `guest`."""
    voices = sorted({s.speaker for s in transcript.segments if s.speaker})
    if not voices:
        return {}
    opening = [s for s in transcript.segments if s.t < OPENING]
    spoken = transcript.language
    reader = reader or spoken
    named, role = ROLES[reader]
    text = PROMPT.format(voices=", ".join(voices), opening=labeled(opening, {}), spoken=NAMES[spoken],
                         reader=NAMES[reader], named=named, role=role, title=transcript.title or "")
    answer = llm.complete(Prompt("", text, language=spoken), SCHEMA)
    given = {v["voice"]: v for v in answer.get("speakers", []) if v["voice"] in voices}
    found = {}
    for v in voices:
        answer = given.get(v, {})
        label = (answer.get("name") or "").strip() or v
        found[v] = {"name": label, "role": "host" if answer.get("role") == "host" else "guest",
                    "person": (answer.get("person") or "").strip() or label}
    return found


def people(named: dict[str, dict], turns: list[dict]) -> dict[str, dict]:
    """Speaker name → {role, person, spoken_s, set_by: "llm"}, the seconds of speech summed over the voice turns."""
    spoken: dict[str, float] = {}
    for turn in turns:
        spoken[turn["speaker"]] = spoken.get(turn["speaker"], 0) + turn["end"] - turn["start"]
    return {n["name"]: {"role": n["role"], "person": n["person"], "spoken_s": round(spoken.get(v, 0)), "set_by": "llm"}
            for v, n in named.items()}


def voice_at(transcript: Transcript, t: float) -> str | None:
    """The name of the voice heard at second `t`: the voice of the last word said by then; None without voices."""
    if not transcript.segments:
        return None
    voice = transcript.segments[max(0, bisect.bisect_right([s.t for s in transcript.segments], t) - 1)].speaker
    return voice and transcript.speakers.get(voice, voice)


def merged(turns: list[dict], names: dict[str, str]) -> list[dict]:
    """The voice turns by person, in order: {start, end, person}, to the tenth of a second. Consecutive turns of one
    voice merge into one, since the diarizer splits a voice at short pauses. A voice with no name is left out."""
    out: list[dict] = []
    for turn in sorted(turns, key=lambda t: t["start"]):
        person = names.get(turn["speaker"])
        if not person:
            continue
        if out and out[-1]["person"] == person:
            out[-1]["end"] = max(out[-1]["end"], round(turn["end"], 1))
        else:
            out.append({"start": round(turn["start"], 1), "end": round(turn["end"], 1), "person": person})
    return out


def speech(turns: list[dict], names: dict[str, str]) -> dict[str, dict]:
    """Person → {spoken_s, turns, longest_s}: the seconds of speech summed over the voice turns, the number of merged
    turns and the longest merged turn, in whole seconds."""
    spoken: dict[str, float] = {}
    for turn in turns:
        if person := names.get(turn["speaker"]):
            spoken[person] = spoken.get(person, 0) + turn["end"] - turn["start"]
    out = {p: {"spoken_s": round(s), "turns": 0, "longest_s": 0} for p, s in spoken.items()}
    for turn in merged(turns, names):
        p = out[turn["person"]]
        p["turns"] += 1
        p["longest_s"] = max(p["longest_s"], round(turn["end"] - turn["start"]))
    return out
