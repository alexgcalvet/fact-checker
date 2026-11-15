import uuid
from dataclasses import dataclass, field

from fact_checker.core.languages import NAMES

FALLACY_LABELS = (
    "ad_hominem",
    "tu_quoque",
    "false_dilemma",
    "straw_man",
    "false_cause",
    "hasty_generalization",
    "vague_authority",
    "insinuation",
    "double_standard",
    "cherry_picking",
    "appeal_to_fear",
)


SYSTEM = "You analyse {} conversations. Answer only with the JSON that the schema asks for."


class Prompt(str):
    """A prompt as one text, whose fixed `rules` a model can read from cache apart from its `data`. With a `session`,
    the model reads it as the next message of that conversation. `language` is the language of the conversation;
    a prompt with no rules is its data alone."""

    def __new__(cls, rules: str, data: str, session: "Session | None" = None, language: str = "es"):
        prompt = super().__new__(cls, f"{rules}\n{data}" if rules else data)
        prompt.rules, prompt.data, prompt.session, prompt.language = rules, data, session, language
        return prompt


def split(prompt: str) -> tuple[str, str]:
    """The system prompt of a reading, with the prompt's fixed rules, and the message to send."""
    head = SYSTEM.format(NAMES[getattr(prompt, "language", "es")])
    rules = getattr(prompt, "rules", None)
    return (f"{head}\n\n{rules}", prompt.data) if rules else (head, prompt)


@dataclass
class Session:
    """One model conversation that readings resume in turn; `tokens` is the size of its context at the last reading,
    `cost_usd` the cost of the whole conversation so far."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    turns: int = 0
    tokens: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class Segment:
    """Caption text that starts at second `t`; usually one word. `speaker` is the voice from the audio."""
    t: float
    text: str
    speaker: str | None = None


@dataclass(frozen=True)
class Transcript:
    segments: list[Segment]
    published_at: str | None
    speakers: dict[str, str] = field(default_factory=dict)  # voice → name or role
    title: str | None = None
    channel: str | None = None
    duration: float | None = None
    language: str = "es"  # the spoken language, from the captions or the speech engine


@dataclass(frozen=True)
class Chunk:
    start: float
    end: float
    segments: list[Segment]

    @property
    def text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments)


@dataclass
class Flag:
    t: float
    speaker: str
    quote: str
    type: str
    label: str
    reason: str
    confidence: float
    related: dict | None = None
    sources: list = field(default_factory=list)
    note: str | None = None
    measures: list = field(default_factory=list)
    controversy: str | None = None
    answer: str | None = None
    promise: dict | None = None
    on_player: bool = False

    @property
    def id(self) -> str:
        return f"{self.label}-{self.t:.1f}"


@dataclass
class Candidate:
    t: float
    label: str
    quote: str
    reason: str


@dataclass(frozen=True)
class Claim:
    """A checkable statement, located in the captions.

    `kind`: `fact`, `own_words` (about the speaker's own earlier words) or `promise` (about a promise of the
    speaker or their side). `central`: the figure carries the speaker's argument; only central claims are checked.
    `repeats`: the second of an earlier claim that states the same figure, else None."""
    t: float
    quote: str
    speaker: str
    queries: list[str]
    question: str | None = None
    kind: str = "fact"
    central: bool = True
    repeats: float | None = None


@dataclass(frozen=True)
class PublishedCheck:
    claim: str
    claimant: str
    publisher: str
    site: str
    url: str
    rating: str
    review_date: str
