"""The judge: one more reading of the whole conversation that rules on every flag found part by part."""
import math

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
- Fair reading. If the claim is true on a reasonable reading of the speaker's words, or the reason leaves out a
  fact that speaks for the speaker (a detention without charges, a later ruling), the verdict is "nitpick".
- Estimates. A round figure for a crowd or a total that sources count differently is a "nitpick" when it is
  within, or near, the range that the sources give, even if one official count is lower.
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
  what the speaker meant: intent does not count. "serious": the error changes the conclusion of a central claim, or
  it is large (a figure off by half or more, an event that did not happen). "moderate": it weakens a claim that
  matters to the argument. "minor": a side remark, or a weak argument that changes little. Most kept flags are not
  serious: keep "serious" for the few that a viewer must not miss.
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


def conversation(transcript: Transcript, start: float, end: float) -> str:
    """The words from `start` to `end`, a line per speaker turn and per minute: "[5:00] Ana Ruiz: …"."""
    lines, current, since = [], object(), -STAMP
    for s in transcript.segments:
        if not start <= s.t < end:
            continue
        name = transcript.speakers.get(s.speaker, s.speaker) if s.speaker else None
        if name != current or s.t - since >= STAMP:
            current, since = name, s.t
            lines.append([f"[{minute(s.t)}]" + (f" {name}:" if name else "")])
        lines[-1].append(s.text.strip())
    return "\n".join(" ".join(line) for line in lines)


def _flag(f: dict) -> str:
    out = [f'- id={f["id"]} [{minute(f["t"])}] {f["type"]}/{f["label"]}, said by {f["speaker"]}, '
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


def judge(flags: list[dict], transcript: Transcript, llm, reader: str | None = None) -> dict[str, dict]:
    """Flag id → `{verdict, reason, severity?, speaker?}` for every non-context flag, one model call per two-hour window. The
    reasons are in `reader`, by default the language of the conversation."""
    spoken = transcript.language
    reader = reader or spoken
    names = set(transcript.speakers.values())
    out = {}
    for n in range(calls(transcript)):
        start, end = n * WINDOW, (n + 1) * WINDOW
        own = {f["id"]: f for f in flags if f["type"] != "context" and start <= f["t"] < end}
        if not own:
            continue
        text = PROMPT.format(rules=RULES, flags="\n".join(_flag(f) for f in own.values()),
                             start=minute(start), end=minute(min(end, transcript.segments[-1].t)),
                             conversation=conversation(transcript, start, end), spoken=NAMES[spoken],
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
            if r.get("speaker") in names and r["speaker"] != f["speaker"]:
                ruling["speaker"] = r["speaker"]
            out[f["id"]] = ruling
    return out
