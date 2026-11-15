import re
from dataclasses import dataclass, field

from fact_checker.core.flags import FALLACY_LABELS, Candidate, Chunk, Claim, Flag, Prompt, Segment, Session
from fact_checker.core.languages import CONTEXT, NAMES
from fact_checker.core.speakers import labeled
from fact_checker.core.summary import minute

MAX_POSITIONS = 60  # lines of the positions list in a part prompt

SCHEMA = {
    "type": "object",
    "properties": {
        "flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "label": {"type": "string"},
                    "closest": {"enum": [*FALLACY_LABELS, None]},
                    "speaker": {"type": "string"},
                    "reason": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["quote", "label", "closest", "speaker", "reason", "confidence"],
                "additionalProperties": False,
            },
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "speaker": {"type": "string"},
                    "queries": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                    "question": {"type": ["string", "null"]},
                    "kind": {"type": "string", "enum": ["fact", "own_words", "promise"]},
                    "central": {"type": "boolean"},
                    "repeats": {"type": ["integer", "null"]},
                },
                "required": ["quote", "speaker", "queries", "question", "kind", "central", "repeats"],
                "additionalProperties": False,
            },
        },
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer_end": {"type": "string"},
                    "speaker": {"type": "string"},
                    "status": {"type": "string", "enum": ["answered", "partial", "dodged"]},
                    "reason": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["question", "answer_end", "speaker", "status", "reason", "confidence"],
                "additionalProperties": False,
            },
        },
        "contradictions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "earlier": {"type": "string"},
                    "speaker": {"type": "string"},
                    "earlier_speaker": {"type": "string"},
                    "reason": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["quote", "earlier", "speaker", "earlier_speaker", "reason", "confidence"],
                "additionalProperties": False,
            },
        },
        "positions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "speaker": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["quote", "speaker", "summary"],
                "additionalProperties": False,
            },
        },
        "context": {
            "type": "array",
            "maxItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "kind": {"type": "string", "enum": ["person", "case", "event"]},
                    "speaker": {"type": "string"},
                    "sentence": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["name", "kind", "speaker", "sentence", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["flags", "claims", "questions", "contradictions", "positions", "context"],
    "additionalProperties": False,
}

RULES = """You review a part of a {spoken} conversation for fallacies. Precision matters more than recall:
flag only clear cases that two reasonable people would agree on. Most parts have no fallacy.

Labels:
- ad_hominem: attacks the person instead of the argument.
- tu_quoque: answers a criticism by pointing at the critic's own past ("y tú más", "what about you", also called
  whataboutism).
- false_dilemma: presents two options when more exist.
- straw_man: distorts an argument that was actually said earlier in this conversation, then attacks it.
- false_cause: claims a cause only because one thing came before another.
- hasty_generalization: concludes about a whole group from one or a few cases.
- vague_authority: supports a claim with an unnamed or irrelevant authority ("todos los expertos dicen", "all the
  experts say").
- insinuation: suggests a grave accusation without evidence, put as a question or a hint ("¿es verdad que…?
  ¿sí o no?", "yo solo pregunto", "is it true that…? yes or no?", "I'm just asking"), so that the listener
  assumes it.
- double_standard: judges the same conduct differently by who does it: demands of a rival what the speaker
  excuses in their own side. It also shows in an answer: asked whether they would ask of their own side what
  they ask of a rival in a like case, the speaker will not say so, or excuses their side with a reason they
  would not accept from the rival.
- cherry_picking: supports a claim with the one figure, period or measure that suits it and leaves out the
  ones that do not. It also covers a switch of yardstick: the speaker measures their own record one way (a
  rank, a share, a rate) and a rival's another way (an absolute figure), so that both comparisons favour
  them. Each figure can be true: flag the switch, quoting the words of the second measure.
- appeal_to_fear: argues by stirring fear of a threat ("una invasión", "nos lo van a quitar todo", "an
  invasion", "they will take everything from us") instead of giving reasons or data.
If a clear fallacy fits none of these, use a short snake_case name of your own, and set `closest` to the
label above that it is a form of (whataboutism is tu_quoque; calling an opponent fascist is ad_hominem),
or null if it is a form of none. A dodged question is not a fallacy. An answer can be both a partial
answer and a fallacy (a double standard): list it under questions and under flags.

When a line starts with a [speaker], the audio says who speaks; trust it over your own guess.
A flag or a claim belongs to what its speaker asserts in their own voice. These are not the speaker's
claims or fallacies:
- words the speaker quotes, reports or attributes to someone else: a hoax, a rumour, what others say;
- a question the speaker asks and then answers themself;
- a criticism that the host puts to the guest (not tu_quoque: tu_quoque needs a speaker answering a
  criticism of their own conduct).

For each flag:
- quote: the exact words from the PART, copied word for word (no words from the CONTEXT).
- speaker: who says it, as far as you can tell (a name or a role such as host or guest).
- reason: one short sentence in {reader}.
- confidence: 0 to 1.

Also list the checkable claims of the PART: concrete figures, dates, rankings or facts that public data
can confirm or refute (not opinions, new promises or predictions). Also list a statement that a plan,
programme or building already exists or was done. Also list a statement of the speaker about what they
said before ("nunca dije que…") and a statement about a promise of the speaker or their side: whether it
was kept, or figures of what was delivered toward it. When an answer to a question gives a figure, also list
the words of the answer that say what the figure counts as a claim of their own (such as "entregadas o en
proceso", "delivered or in process"), because they may count something other than what was asked. Also list a figure that the speaker
gives for the effect of a measure (a saving, a margin, a price, a cost), because how the measure works can
confirm or refute it. For each claim:
- quote: the exact words from the PART, copied word for word.
- speaker: who says it.
- queries: up to 3 short {spoken} search queries to find a published fact-check of it.
- question: the question that another speaker asked just before the claim, copied from the PART or the
  CONTEXT, or null.
- kind: own_words for a statement about what the speaker said before, promise for a statement about a
  promise of the speaker or their side or its progress, else fact.
- central: true when the claim carries the speaker's argument: they build their point on it, or it answers
  the question asked. False for a figure said in passing, as an aside or as background.
- repeats: the number of the CHECKED line that states the same figure or fact, said again in other words,
  else null.

Also list each question that one speaker (usually the interviewer) asks another, in the PART or the
CONTEXT, whose answer ends inside the PART: the next question or a new topic starts in the PART. Skip an
answer that still runs at the end of the PART, a rhetorical question and a question the speaker answers
themself. For each question:
- question: the exact words of the question, copied word for word from the PART or the CONTEXT.
- answer_end: the last words of the answer (about 5 to 10), copied word for word from the PART.
- speaker: who answers.
- status: answered (gives what was asked), partial (gives only part of it) or dodged (talks about
  something else). An answer that gives a figure of something other than what was asked is dodged: asked
  for homes delivered, homes "entregadas o en proceso" ("delivered or in process") do not answer it.
- reason: one short sentence in {reader}: what was asked and what the answer gave instead.
- confidence: 0 to 1.

Also list each statement in the PART that says the opposite of what the same speaker said earlier, in
the PART, the CONTEXT or a line of POSITIONS: both cannot be true at once. Compare each position of the PART
with the earlier statements of the same speaker on the same topic. A later statement counts when it denies,
reverses or empties an earlier commitment, or gives another figure for the same target, also inside the same
answer. Skip a change of mind that the speaker admits or
explains, two different speakers who disagree, and words the speaker quotes or attributes to someone else.
For each contradiction:
- quote: the exact words of the later statement, copied word for word from the PART.
- earlier: the exact words of the earlier statement, copied word for word from the PART, the CONTEXT or
  the «quoted» words of a POSITIONS line.
- speaker: who says the later statement.
- earlier_speaker: who says the earlier statement.
- reason: one short sentence in {reader}: what was said before and what is said now.
- confidence: 0 to 1.

Also list at most 2 people, cases or events named in the PART that a viewer may not know, the least known: a minister, a court
case, a scandal, a law, a strike. Skip the speakers themselves and names everyone knows (the country, the
king, the main parties). For each one:
- name: the name exactly as said, copied word for word from the PART.
- kind: person, case or event.
- speaker: who names it.
- sentence: one short, neutral sentence in {reader} on who or what it is, from your own knowledge, with
  no judgement (such as "{context}").
- confidence: 0 to 1, how sure you are of the sentence.

Also list the positions that a speaker states in the PART in their own voice: a stance, a commitment, a
yes or no on a measure, or a figure they give as their own, that they could contradict later. List at most
4, the clearest. For each one:
- quote: the exact words, copied word for word from the PART (5 to 15 words).
- speaker: who states it.
- summary: one short, neutral sentence, in {spoken} like the conversation, such as "no quitará el Ministerio de Igualdad" or "will
  not close the Department of Education".

Do not use any tool. Answer only with the JSON.
"""

DATA = """CHECKED (claims already checked earlier in the video, numbered):
{checked}

POSITIONS (what each speaker stated earlier in the whole video, oldest first):
{positions}

CONTEXT (earlier, for understanding only):
{context}

PART:
{part}
"""

SCREEN_SCHEMA = {
    "type": "object",
    "properties": {"read": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["read", "reason"],
    "additionalProperties": False,
}

# The cheap screen before the full reading of a part: a part it skips can never be flagged, so it leans to reading.
SCREEN = """You screen a part of a {spoken} conversation before a careful reading. The careful reading looks for
fallacies, checkable figures, dodged questions, contradictions and names that a viewer may not know. Say only whether
the PART may hold any of them.

Answer read: true when the PART holds any of these:
- a figure, a date, a ranking or a fact that public data can confirm or refute;
- a claim that carries an argument: a reason, a cause, a blame, a comparison, an accusation, a warning;
- a stance, a commitment, a yes or no on a measure, or words about what someone said or promised before;
- an answer to a question, which may dodge it;
- a person, a case, a law or an event that a viewer may not know.
Answer read: false only when the whole PART is small talk with none of these: a greeting, thanks, a goodbye, the
introduction of the programme, a joke, logistics, an advert or music.
If you are unsure, answer read: true. A part that you skip is never read.
- reason: a few words in {reader}.

Do not use any tool. Answer only with the JSON.
"""

# A part read as the next message of one conversation: the earlier parts are its messages above.
NEXT = """The earlier parts of this conversation are in the messages above; they count as CONTEXT.

{lists}PART:
{part}
"""


@dataclass(frozen=True)
class Position:
    """What a speaker stated at second `t`: a one-line summary and the caption words that say it."""
    t: float
    speaker: str
    summary: str
    quote: str
    segments: list[Segment]


@dataclass
class ChunkResult:
    flags: list[Flag] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    positions: list[Position] = field(default_factory=list)
    questions: list[tuple[float, str]] = field(default_factory=list)  # (answer end, speaker) of each question asked


def ledger(positions: list[Position]) -> str:
    """One line per position, oldest first; over MAX_POSITIONS lines, the oldest line of a speaker takes in their
    next one, without its quotes."""
    lines = [[p] for p in sorted(positions, key=lambda p: p.t)]
    while len(lines) > MAX_POSITIONS:
        i, j = next((i, j) for i in range(len(lines)) for j in range(i + 1, len(lines))
                    if lines[j][0].speaker == lines[i][0].speaker)
        lines[i] += lines.pop(j)
    out = []
    for line in lines:
        if len(line) == 1:
            out.append(f"{line[0].speaker} ({minute(line[0].t)}): {line[0].summary} «{line[0].quote}»")
        else:
            out.append(f"{line[0].speaker} ({', '.join(minute(p.t) for p in line)}): "
                       + "; ".join(p.summary for p in line))
    return "\n".join(out)


def _norm(word: str) -> str:
    return re.sub(r"[^\w]", "", word.lower())


def _words(segments: list[Segment]) -> list[tuple[str, str, float, str | None]]:
    """(normalized, original, second, voice) for every caption word of the segments."""
    out = []
    for seg in segments:
        for w in seg.text.split():
            if _norm(w):
                out.append((_norm(w), w, seg.t, seg.speaker))
    return out


def _locate(quote: str, words: list[tuple[str, str, float, str | None]]) -> tuple[str, float, set[str], float] | None:
    """The caption words of the quote, their second, their voices and the second of the last word."""
    needle = [n for n in (_norm(w) for w in quote.split()) if n]
    if not needle:
        return None
    hay = [w[0] for w in words]
    for i in range(len(hay) - len(needle) + 1):
        if hay[i : i + len(needle)] == needle:
            span = words[i : i + len(needle)]
            return " ".join(w[1] for w in span), span[0][2], {w[3] for w in span if w[3]}, span[-1][2]
    return None


def _speaker(voices: set[str], names: dict[str, str], guess: str) -> str | None:
    """The name of the one voice that said the words; None when they cross voices."""
    if len(voices) > 1:
        return None
    if not voices:
        return guess
    voice = next(iter(voices))
    return names.get(voice, voice)


def _same_speaker(later: set[str], earlier: set[str], item: dict) -> bool:
    """One voice for both statements; without voices, the model names one speaker for both."""
    if len(later) > 1 or len(earlier) > 1:
        return False
    if later and earlier:
        return later == earlier
    return _norm(item["speaker"]) == _norm(item["earlier_speaker"])


def analyze_chunk(chunk: Chunk, context: list[Segment], llm, names: dict[str, str] | None = None,
                  positions: list[Position] = (), checked: list[Claim] = (), session: Session | None = None,
                  said: list[Segment] | None = None, spoken: str = "es", reader: str | None = None) -> ChunkResult:
    """`positions` are what the speakers stated earlier in the video; the result holds the new ones of the part.
    `checked` are the claims already checked, which a claim of the part may repeat. `spoken` is the language of the
    conversation, `reader` the language of the reasons (by default the spoken one).

    With a `session`, the part is the next message of that conversation: it sends only the part, the checked claims,
    the `context` that no earlier message holds (the words of skipped parts) and, in a new session, the positions. `said` is everything said before the part, where an earlier quote is found
    (by default the context)."""
    names = names or {}
    numbered = "\n".join(f"{i}. [{c.speaker}] «{c.quote}»" for i, c in enumerate(checked, 1))
    part = labeled(chunk.segments, names)
    if session is None:
        data = DATA.format(checked=numbered or "(none)", positions=ledger(positions) or "(none)",
                           context=labeled(context, names) or "(none)", part=part)
    else:
        carried = ledger(positions) if not session.turns else ""
        lists = (f"CHECKED (claims already checked earlier in the video, numbered):\n{numbered}\n\n" if numbered else "") \
            + (f"POSITIONS (what each speaker stated earlier in the whole video, oldest first):\n{carried}\n\n"
               if carried else "") \
            + (f"CONTEXT (earlier, for understanding only):\n{labeled(context, names)}\n\n" if context else "")
        data = NEXT.format(lists=lists, part=part)
    reader = reader or spoken
    rules = RULES.format(spoken=NAMES[spoken], reader=NAMES[reader], context=CONTEXT[reader])
    answer = llm.complete(Prompt(rules, data, session, spoken), SCHEMA)
    words = _words(chunk.segments)
    before = _words(context if said is None else said) + words
    result = ChunkResult()
    for item in answer.get("flags", []):
        found = _locate(item["quote"], words)
        if not found:
            continue
        quote, t, voices, _ = found
        speaker = _speaker(voices, names, item["speaker"])
        if speaker is None:
            continue
        label = item["label"] if item["label"] in FALLACY_LABELS else item.get("closest")
        if item["label"] != label:
            result.candidates.append(Candidate(t=t, label=item["label"], quote=quote, reason=item["reason"]))
        if label:
            result.flags.append(Flag(t=t, speaker=speaker, quote=quote, type="fallacy",
                                     label=label, reason=item["reason"], confidence=item["confidence"]))
    for item in answer.get("claims", []):
        found = _locate(item["quote"], words)
        if not found:
            continue
        speaker = _speaker(found[2], names, item.get("speaker", ""))
        if speaker is not None:
            n = item.get("repeats")
            result.claims.append(Claim(t=found[1], quote=found[0], speaker=speaker,
                                       queries=item.get("queries", [])[:3], question=item.get("question"),
                                       kind=item.get("kind", "fact"), central=item.get("central", True),
                                       repeats=checked[n - 1].t if n and 0 < n <= len(checked) else None))
    for item in answer.get("questions", []):
        end = _locate(item["answer_end"], words)
        if not end:
            continue
        asked = _locate(item["question"], before)
        if not asked:
            continue
        speaker = _speaker(end[2], names, item["speaker"])
        if speaker is not None:
            result.questions.append((end[3], speaker))
        if speaker is not None and item["status"] != "answered":
            result.flags.append(Flag(t=end[3], speaker=speaker, quote=end[0], type="question", label=item["status"],
                                     answer=item["status"], reason=item["reason"], confidence=item["confidence"],
                                     related={"t": asked[1], "quote": asked[0]}))
    for item in answer.get("contradictions", []):
        later = _locate(item["quote"], words)
        earlier = _locate(item["earlier"], before) or next(
            (found for p in positions if (found := _locate(item["earlier"], _words(p.segments)))), None)
        if not later or not earlier or earlier[1] >= later[1] or not _same_speaker(later[2], earlier[2], item):
            continue
        speaker = _speaker(later[2], names, item["speaker"])
        result.flags.append(Flag(t=later[1], speaker=speaker, quote=later[0], type="contradiction", label="self",
                                 reason=item["reason"], confidence=item["confidence"],
                                 related={"t": earlier[1], "quote": earlier[0]}))
    for item in answer.get("positions", []):
        found = _locate(item["quote"], words)
        if not found:
            continue
        quote, t, voices, end = found
        speaker = _speaker(voices, names, item["speaker"])
        if speaker is not None:
            result.positions.append(Position(t=t, speaker=speaker, summary=item["summary"], quote=quote,
                                             segments=[s for s in chunk.segments if t <= s.t <= end]))
    for item in answer.get("context", []):
        found = _locate(item["name"], words)
        if not found:
            continue
        speaker = _speaker(found[2], names, item["speaker"])
        if speaker is not None:
            result.flags.append(Flag(t=found[1], speaker=speaker, quote=found[0].strip(".,;:"), type="context",
                                     label=item["kind"],
                                     reason=item["sentence"], confidence=item["confidence"]))
    return result


def screen(chunk: Chunk, llm, names: dict[str, str] | None = None, spoken: str = "es",
           reader: str | None = None) -> dict:
    """The cheap screen of a part: `read` false when the part holds nothing worth the full reading, and its `reason`."""
    rules = SCREEN.format(spoken=NAMES[spoken], reader=NAMES[reader or spoken])
    return llm.complete(Prompt(rules, f"PART:\n{labeled(chunk.segments, names or {})}\n", None, spoken), SCREEN_SCHEMA)
