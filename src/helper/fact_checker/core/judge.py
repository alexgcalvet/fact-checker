"""The judge: one more reading of the whole conversation that rules on every flag found part by part."""
import math
import re

from fact_checker.core.flags import Prompt, Transcript
from fact_checker.core.languages import NAMES, NITPICK
from fact_checker.core.summary import minute

WINDOW = 7200  # one reading per started two video-hours
TIMEOUT = 900  # seconds: one reading of up to two hours of conversation
STAMP = 60  # a minute stamp at each change of speaker and at least once a minute
SEVERITIES = ("minor", "moderate", "serious")

SCHEMA = {
    "type": "object",
    "properties": {
        "rulings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["keep", "nitpick"]},
                    "reason": {"type": "string"},
                    "speaker": {"type": ["string", "null"]},
                    "severity": {"type": ["string", "null"], "enum": ["minor", "moderate", "serious", None]},
                },
                "required": ["id", "verdict", "reason", "speaker", "severity"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["rulings"],
    "additionalProperties": False,
}

# The person's principles and the lessons of their marks on the 112-minute interview. Never add a case from a
# video that the judge is measured on.
RULES = """\
- Never drop a flag: each one quotes words said in the conversation, and most are right. Rule "keep" or
  "nitpick" only.
- You rule on the reading, never on the facts. The fact check already weighed the sources; you do not search and
  you do not check again. Rule "nitpick" only for a reason of reading: who said it, what exactly was claimed, or a
  small error by the rules below. Never rule "nitpick" because a source, an official figure or a government says the
  speaker is right: governments and parties also give false or framed figures. If you doubt the facts, keep the flag.
- A nitpick needs a reason that the flag's own sources or the conversation give. "It cannot be checked", "it is a
  valuation" or "the size backs it" are not reasons: if the flag cites a record or a measure against the speaker, keep
  it. A figure more than about 1.4 times from the closest credible measure is never a nitpick.
- A figure from the speaker's own government, party or an administration they lead or led never makes the speaker
  right by itself.
- Materiality. If the substance of a figure holds and the error is small (about 10-15 %, or a near date),
  the verdict is "nitpick", never "keep".
- Direction. An error that does not strengthen the speaker's own argument is never misleading or false.
  It is at most a "nitpick".
- Scope. Read the whole sentence and the sentences around it before you decide what is claimed. If the
  speaker states the right figure himself, or only describes a rule or a position as it is, the verdict is
  "nitpick".
- Who speaks. Check in the transcript who says each flagged line. If the line belongs to another speaker,
  give that speaker's name exactly as the transcript writes it in "speaker"; else null. A reproach or a
  question from the host is the host's line, not the guest's.
- Roles. A rhetorical question that a speaker asks himself and then answers is not an evasion. A host who
  says "you do it too" is challenging the guest, not making a tu quoque. Rule such a flag "nitpick".
- Fair reading. If the claim is true on a reasonable reading of the speaker's words, as said in the conversation,
  or the reason leaves out a fact that speaks for the speaker (a detention without charges, a later ruling), the
  verdict is "nitpick". A reading is about the words, not about which source to believe.
- Estimates. A round figure for a crowd or a total that sources count differently is a "nitpick" when it is
  within, or near, the range that independent sources give. A range made only of the speaker's own side's figures
  does not count.
- Fallacies. A debatable but reasonable causal link, or an argument that mostly holds, is a "nitpick".
- Contradictions. Two statements of the same speaker that cannot both be true as said are a contradiction.
  Keep it unless the speaker himself, in the conversation, says how they fit: an exception, a change of mind,
  another period or another measure. Do not excuse it on a reading that you supply for him. His explanation
  counts only if it makes both statements true as he said them. Renaming the thing, narrowing what he first
  said, or calling the new case different without saying how it differs on the point at stake does not
  reconcile them: keep the flag. If his explanation does reconcile them, the verdict is "nitpick".
- Keep a flag that survives all of the above. When in doubt, keep it.
- Severity. Rate each kept flag "minor", "moderate" or "serious"; a nitpick gets null. Rate by how much the error
  changes the point, how central the claim is to what the speaker argues, and how big the error is. Never rate by
  what the speaker meant: intent does not count.
  A figure is rated by how far it is from the closest credible measure, as a ratio of the larger to the smaller:
  up to about 1.4 times (69 % said for 56 %) is "minor"; from about 1.4 up to 2 times (15,000 said for at most
  8,000) is "moderate"; more than 2 times (one in three said for 8-10 %), or a figure that reverses the
  conclusion, is "serious". A figure said in passing is one level lower.
  "serious" is also: an event that did not happen; a ruling, a law or a record stated as the opposite of what it
  says; a self-contradiction on the central topic of the answer; an insinuation that accuses a named person of a
  crime with no evidence given.
  A statement about the speaker's own conduct that a record (an agenda, the press of the time, a court) contradicts,
  on the topic of the answer, is at least "moderate"; "serious" when the record shows the opposite of what he says.
  "moderate" is also: a fallacy that carries an argument of the answer.
  "minor" is also: a side remark, or a weak argument that changes little.
  Rate each flag on its own against these anchors; there is no quota for any level.
"""

PROMPT = """You review the flags that an automatic analyst found in a {spoken} conversation. It read the
conversation part by part, so it can miss who speaks to whom, the rest of a sentence, or how much a small
error matters. You read the whole conversation and rule on each flag: "keep" or "nitpick" (a minor correction),
with one short reason in {reader}, and the severity of each kept flag. For a nitpick, the reason states the correction, such as
"{example}".

Rules:
{rules}
Do not use any tool. Use only the sources that the flags already hold. Answer only with the JSON: one ruling
per flag id below.

FLAGS:
{flags}

CONVERSATION ({start} to {end}), each line with its minute and its speaker:
{conversation}
"""


def calls(transcript: Transcript) -> int:
    duration = transcript.segments[-1].t if transcript.segments else 0
    return max(1, math.ceil(duration / WINDOW))


def blind(names: set[str]) -> dict[str, str]:
    """Each speaker name → a label with its role and no name, "Invitado 1", so the judge rules on what was said, not on
    who said it."""
    labels = {}
    for i, name in enumerate(sorted(names), 1):
        role = re.search(r"\(([^)]+)\)\s*$", name)
        labels[name] = f"{role[1].strip().capitalize()} {i}" if role else f"Speaker {i}"
    return labels


def conversation(transcript: Transcript, start: float, end: float, labels: dict[str, str] | None = None) -> str:
    """The words from `start` to `end`, a line per speaker turn and per minute: "[5:00] Ana Ruiz: …"; with `labels`,
    each name is replaced by its label."""
    labels = labels or {}
    lines, current, since = [], object(), -STAMP
    for s in transcript.segments:
        if not start <= s.t < end:
            continue
        name = transcript.speakers.get(s.speaker, s.speaker) if s.speaker else None
        name = labels.get(name, name)
        if name != current or s.t - since >= STAMP:
            current, since = name, s.t
            lines.append([f"[{minute(s.t)}]" + (f" {name}:" if name else "")])
        lines[-1].append(s.text.strip())
    return "\n".join(" ".join(line) for line in lines)


def _flag(f: dict, labels: dict[str, str]) -> str:
    out = [f'- id={f["id"]} [{minute(f["t"])}] {f["type"]}/{f["label"]}, said by {labels.get(f["speaker"], f["speaker"])}, '
           f'confidence {f["confidence"]:.2f}: «{f["quote"]}»', f"  reason: {f['reason']}"]
    if f.get("related"):
        out.append(f"  related: «{f['related']['quote']}»")
    for m in f.get("measures") or []:
        out.append(f"  measure: {m['name']} = {m['value']} ({m['source']}, {'supports' if m['supports'] else 'against'})")
    if f.get("note"):
        out.append(f"  note: {f['note']}")
    for s in f.get("sources") or []:
        out.append(f"  source: {s['publisher']}, {s['date']}")
    return "\n".join(out)


def judge(flags: list[dict], transcript: Transcript, llm, reader: str | None = None, readings: int = 1) -> dict[str, dict]:
    """Flag id → `{verdict, reason, severity?, speaker?}` for every non-context flag, one model call per two-hour window
    and reading. With several readings the strictest ruling of each flag wins: a keep over a nitpick, then the higher
    severity. The reasons are in `reader`, by default the language of the conversation."""
    rank = lambda r: (r["verdict"] == "keep", SEVERITIES.index(r["severity"]) if r.get("severity") in SEVERITIES else -1)
    out = {}
    for _ in range(readings):
        for id, ruling in _reading(flags, transcript, llm, reader).items():
            if id not in out or rank(ruling) > rank(out[id]):
                out[id] = ruling
    return out


def _reading(flags: list[dict], transcript: Transcript, llm, reader: str | None) -> dict[str, dict]:
    spoken = transcript.language
    reader = reader or spoken
    names = set(transcript.speakers.values())
    labels = blind(names | {f["speaker"] for f in flags})
    named = {label: name for name, label in labels.items()}
    out = {}
    for n in range(calls(transcript)):
        start, end = n * WINDOW, (n + 1) * WINDOW
        own = {f["id"]: f for f in flags if f["type"] != "context" and start <= f["t"] < end}
        if not own:
            continue
        text = PROMPT.format(rules=RULES, flags="\n".join(_flag(f, labels) for f in own.values()),
                             start=minute(start), end=minute(min(end, transcript.segments[-1].t)),
                             conversation=conversation(transcript, start, end, labels), spoken=NAMES[spoken],
                             reader=NAMES[reader], example=NITPICK[reader])
        prompt = Prompt("", text, language=spoken)
        for r in llm.complete(prompt, SCHEMA).get("rulings", []):
            f = own.get(r["id"])
            if not f:
                continue
            # A provider that does not enforce the schema can still answer "drop": the judge drops no flag.
            ruling = {"verdict": "nitpick" if r["verdict"] == "nitpick" else "keep", "reason": r["reason"]}
            if ruling["verdict"] == "keep" and r.get("severity") in SEVERITIES:
                ruling["severity"] = r["severity"]
            speaker = named.get(r.get("speaker"), r.get("speaker"))
            if speaker in names and speaker != f["speaker"]:
                ruling["speaker"] = speaker
            out[f["id"]] = ruling
    return out
