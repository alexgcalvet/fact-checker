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
                "properties": {"voice": {"type": "string"}, "name": {"type": "string"}},
                "required": ["voice", "name"],
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


def name(transcript: Transcript, llm, reader: str | None = None) -> dict[str, str]:
    """Voice → name or role, from the opening of the conversation, in one model call; the roles in `reader`, by
    default the language of the conversation."""
    voices = sorted({s.speaker for s in transcript.segments if s.speaker})
    if not voices:
        return {}
    opening = [s for s in transcript.segments if s.t < OPENING]
    spoken = transcript.language
    reader = reader or spoken
    named, role = ROLES[reader]
    text = PROMPT.format(voices=", ".join(voices), opening=labeled(opening, {}), spoken=NAMES[spoken],
                         reader=NAMES[reader], named=named, role=role)
    answer = llm.complete(Prompt("", text, language=spoken), SCHEMA)
    names = {v["voice"]: v["name"].strip() for v in answer.get("speakers", []) if v["voice"] in voices}
    return {v: names.get(v) or v for v in voices}


def voice_at(transcript: Transcript, t: float) -> str | None:
    """The name of the voice heard at second `t`: the voice of the last word said by then; None without voices."""
    if not transcript.segments:
        return None
    voice = transcript.segments[max(0, bisect.bisect_right([s.t for s in transcript.segments], t) - 1)].speaker
    return voice and transcript.speakers.get(voice, voice)
