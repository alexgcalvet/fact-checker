import re

from fact_checker.core.flags import Claim, Flag, PublishedCheck, Prompt
from fact_checker.core.languages import EARLIER, NAMES, SOURCES, TIERS
from fact_checker.core.pipeline import _norm

TOOLS = ("WebSearch", "WebFetch")
WRONG = ("false", "misleading")
BROKEN = ("partly met", "not met")  # a met or ongoing promise is not a flag
VERDICTS = ["true", "false", "misleading", "unverifiable", "definition_swap", "plan_as_fact"]
CREDIBLE_TIER = 4  # tier 5 (think tanks, media) is context only
ANCHOR_TIER = 3  # a "false" needs a contradicting measure of tier 1-3

SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "verdict": {"type": "string", "enum": VERDICTS},
                    "reason": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "publisher": {"type": "string"},
                                "url": {"type": "string"},
                                "date": {"type": ["string", "null"]},
                            },
                            "required": ["publisher", "url", "date"],
                            "additionalProperties": False,
                        },
                    },
                    "note": {"type": ["string", "null"]},
                    "measures": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "string"},
                                "source": {"type": "string"},
                                "tier": {"type": "integer", "minimum": 1, "maximum": 5},
                                "supports": {"type": "boolean"},
                            },
                            "required": ["name", "value", "source", "tier", "supports"],
                            "additionalProperties": False,
                        },
                    },
                    "controversy": {"type": ["string", "null"]},
                    "published": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"url": {"type": "string"}, "same_event": {"type": "boolean"}},
                            "required": ["url", "same_event"],
                            "additionalProperties": False,
                        },
                    },
                    "earlier": {
                        "type": ["object", "null"],
                        "properties": {
                            "quote": {"type": "string"},
                            "date": {"type": ["string", "null"]},
                            "publisher": {"type": "string"},
                            "url": {"type": "string"},
                        },
                        "required": ["quote", "date", "publisher", "url"],
                        "additionalProperties": False,
                    },
                    "promise": {
                        "type": ["object", "null"],
                        "properties": {
                            "made": {"type": "string"},
                            "figure": {"type": "string"},
                            "deadline": {"type": "string"},
                            "status": {"type": "string", "enum": ["met", "partly met", "not met", "in progress"]},
                        },
                        "required": ["made", "figure", "deadline", "status"],
                        "additionalProperties": False,
                    },
                },
                "required": ["quote", "verdict", "reason", "confidence", "sources", "note", "measures", "controversy",
                             "published", "earlier", "promise"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}

INTRO = """You check claims made in a {spoken} video. Judge each claim against the data that was valid on the
publish date given with the claims. If the data changed later, judge it on the publish date and put the newer value
in `note`.
"""

SEARCH = """Use the published fact-checks listed under a claim first, but only one about the same event as the claim:
the same place, dates and facts. A check about another event (another crossing, another year, another
rumour on the same topic) says nothing about the claim; never cite it.
Otherwise use WebSearch. Search in {spoken}, in the context of the country the conversation is about, preferring
official and primary sources: {sources}. Make at most 2 searches per claim. Do not open pages: use the
title, snippet and date that the search results show.
For a claim with a figure, look for each credible measure of it, the ones that support the claim and the ones
that do not.
For an own_words claim, search the speaker's earlier public statements: {earlier}.
For a promise claim, find the original promise and its status on the publish date.
For a figure of the effect of a rule or a measure (a saving, a margin, a cost), search how the rule works: what
it takes away as well as what it gives.
"""

JUDGE = """An official figure is not the truth by itself: a metric can be defined or framed to fit a side. For a
claim with a figure, list each credible measure of it, the ones that support the claim and the ones
that do not. Give each measure the tier of its producer:
{tiers}

Two more ways a claim can mislead:
- definition_swap: the speaker answers a question about one metric with a wider or different one (asked
  for homes delivered, answers with homes "delivered or in process"). Only when the question is listed
  under the claim.
- plan_as_fact: the speaker talks about a plan, a programme or homes as if they already existed or were
  done, while a dated source shows they are still announced, planned or in progress.
A figure of the effect of a rule or a measure (a saving, a margin, a cost) must follow from how the rule works.
If it leaves out a part of the rule that changes the figure, the verdict is misleading.

Read the claim the way a fair listener would. If it is true on a reasonable reading, it is not false. When the
facts are mixed (a detention without charges, a crowd figure that sources count differently), the verdict is
misleading at most, and the reason names the fact that speaks for the speaker too.

Some claims are marked with a kind:
- own_words: the speaker says what they said or did not say before. If a dated earlier statement says
  otherwise, the verdict is false.
- promise: the speaker talks about a promise of theirs or their side, or about what was delivered toward
  it. The verdict is false or misleading when the speaker presents it as kept or further along than a dated
  source shows.

For each claim give:
- quote: the claim, copied exactly.
- verdict: true, false, misleading, unverifiable, definition_swap or plan_as_fact. Say false, misleading,
  definition_swap or plan_as_fact only when a source shows it.
- reason: one short sentence in {reader}, with the correct figure. For definition_swap, name the metric
  asked and the metric given. For plan_as_fact, say the real status of the plan and its date.
- confidence: 0 to 1.
- sources: publisher, url and publication date (YYYY-MM-DD), or null when the date cannot be found.
- note: the newer value if the data changed after the publish date, in {reader}, else null.
- measures: each credible measure of the figure: name, value, source (publisher and period), tier (1-5),
  and supports (true when the measure supports the claim). Empty when the claim has no figure.
- controversy: one short sentence in {reader} on a documented controversy about the metric, with its
  source, else null.
- published: for each published fact-check listed under the claim, its url and whether it is about
  the same event (same_event).
- earlier: for own_words, the earlier statement that contradicts the claim: its exact words, its date
  (YYYY-MM-DD, or null when no source confirms it), publisher and url. Else null.
- promise: for promise, when it was made (YYYY-MM), its figure, its deadline and its status on the publish
  date: met, partly met, not met or in progress. Else null.
"""

# One reading searches and judges.
CHECK = INTRO + SEARCH + JUDGE
GATHER = """
Do not judge the claims. For each claim give:
- quote: the claim, copied exactly.
- findings: each source you found that bears on it: publisher, url, publication date (YYYY-MM-DD, or null
  when it cannot be found), and says: what the source states about the claim in one or two sentences, with
  its figures and period, or the earlier statement in its exact words, or the promise and its status.
"""
# The search reading: a cheaper model with web tools gathers the evidence and judges nothing.
FIND = INTRO + SEARCH + GATHER
# The search reading of a model with no web search: it reads the results of a search service instead.
READ = INTRO + """Use the published fact-checks listed under a claim first, but only one about the same event as the
claim: the same place, dates and facts. A check about another event says nothing about the claim; never cite it.
Otherwise use only the SEARCH RESULTS listed under each claim: their title, date, url and snippet. Do not search.
For a claim with a figure, look in them for each credible measure of it, the ones that support the claim and the
ones that do not.
""" + GATHER
# The verdict reading: no tools, only the evidence of the search reading.
VERDICT = INTRO + """Use only the EVIDENCE listed under each claim and the published fact-checks listed under it.
Do not use any tool. Cite only the urls of the evidence and of the published fact-checks.
A published fact-check counts only when it is about the same event as the claim: the same place, dates and facts.
""" + JUDGE

DATA = """Video published on {published_at}.

CLAIMS:
{claims}
"""

SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "quote": {"type": "string"},
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "publisher": {"type": "string"},
                                "url": {"type": "string"},
                                "date": {"type": ["string", "null"]},
                                "says": {"type": "string"},
                            },
                            "required": ["publisher", "url", "date", "says"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["quote", "findings"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["evidence"],
    "additionalProperties": False,
}

DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _claims_text(claims: list[Claim], published: dict[str, list[PublishedCheck]],
                evidence: dict[str, list[dict]] | None = None, results: dict[str, list[dict]] | None = None) -> str:
    out = []
    for i, c in enumerate(claims, 1):
        kind = f"{c.kind}: " if c.kind != "fact" else ""
        out.append(f'{i}. [{c.speaker}] {kind}"{c.quote}"')
        if c.question:
            out.append(f'   asked just before: "{c.question}"')
        for p in published.get(c.quote, []):
            out.append(f'   published fact-check: {p.publisher}, rated "{p.rating}" on {p.review_date}: '
                       f'"{p.claim}" {p.url}')
        for e in (evidence or {}).get(_norm_text(c.quote), []):
            out.append(f'   EVIDENCE: {e["publisher"]}, {e["date"] or "undated"}, {e["url"]}: {e["says"]}')
        for r in (results or {}).get(c.quote, []):
            out.append(f'   SEARCH RESULT: {r["title"]}, {r["published_date"] or "undated"}, {r["url"]}: {r["content"]}')
    return "\n".join(out)


def _results(web, queries: list[str]) -> list[dict]:
    """The results of the claim's first 2 queries, each URL once. A failed search gives none."""
    found = {}
    for query in queries[:2]:
        try:
            found |= {r["url"]: r for r in web.search(query) if r["url"] not in found}
        except OSError:
            pass
    return list(found.values())


def _prompt(rules: str, data: str, spoken: str, reader: str) -> Prompt:
    """The rules for the language of the video and of the reasons."""
    return Prompt(rules.format(spoken=NAMES[spoken], reader=NAMES[reader], sources=SOURCES[spoken],
                               earlier=EARLIER[spoken], tiers=TIERS[spoken]), data, language=spoken)


def _evidence(claims: list[Claim], published_at: str, published: dict[str, list[PublishedCheck]],
              searcher, web, spoken: str, reader: str) -> dict[str, list[dict]]:
    """The findings of the search reading, by normalized claim quote. With `web`, a search service, the searcher reads
    its results instead of searching."""
    if web:
        results = {c.quote: _results(web, c.queries) for c in claims}
        data = DATA.format(published_at=published_at, claims=_claims_text(claims, published, results=results))
        answer = searcher.complete(_prompt(READ, data, spoken, reader), SEARCH_SCHEMA)
    else:
        data = DATA.format(published_at=published_at, claims=_claims_text(claims, published))
        answer = searcher.complete(_prompt(FIND, data, spoken, reader), SEARCH_SCHEMA, tools=TOOLS)
    return {_norm_text(e["quote"]): e["findings"] for e in answer.get("evidence", [])}


def check_claims(claims: list[Claim], published_at: str | None,
                 published: dict[str, list[PublishedCheck]], llm, searcher=None,
                 web=None, spoken: str = "es", reader: str | None = None) -> tuple[list[Flag], list[str]]:
    """Flags the claims that a dated source contradicts, and the outcome of each claim: `flagged`, `ok` (a verdict
    and no flag) or `unchecked` (no verdict).

    With a `searcher`, it gathers the evidence with web tools and `llm` judges it with none, citing only the evidence;
    without one, `llm` searches and judges in one reading. With `web`, a search service, the searcher reads its
    results instead of searching. `spoken` is the language of the video, `reader` the language of the reasons (by
    default the spoken one)."""
    reader = reader or spoken
    published_at = published_at or "unknown"
    review_dates = {p.url: p.review_date for checks in published.values() for p in checks}
    if searcher:
        evidence = _evidence(claims, published_at, published, searcher, web, spoken, reader)
        found = {e["url"]: e["date"] for findings in evidence.values() for e in findings}
        cited = found.keys() | review_dates.keys()
        data = DATA.format(published_at=published_at, claims=_claims_text(claims, published, evidence))
        answer = llm.complete(_prompt(VERDICT, data, spoken, reader), SCHEMA)
    else:
        found, cited = {}, None
        data = DATA.format(published_at=published_at, claims=_claims_text(claims, published))
        answer = llm.complete(_prompt(CHECK, data, spoken, reader), SCHEMA, tools=TOOLS)
    by_quote = {_norm_text(c.quote): i for i, c in enumerate(claims)}
    outcomes = ["unchecked"] * len(claims)
    flags = []
    for v in answer.get("verdicts", []):
        i = by_quote.get(_norm_text(v["quote"]))
        if i is None:
            continue
        claim, before = claims[i], len(flags)
        other_event = {p["url"] for p in v.get("published", []) if not p["same_event"]}
        sources = []
        for s in v["sources"]:
            if s["url"] in other_event or (cited is not None and s["url"] not in cited):
                continue
            date = (s.get("date") or found.get(s["url"]) or review_dates.get(s["url"]) or "")[:10]
            if DATE.fullmatch(date):
                sources.append({"publisher": s["publisher"], "url": s["url"], "date": date})
        record = _record_flag(claim, v, sources)
        if record:
            flags.append(record)
        label = _label(v["verdict"], v.get("measures", []))
        # A record or promise flag already says the claim is wrong; a plain false or misleading would repeat it.
        if sources and label and not (record and label in WRONG):
            flags.append(Flag(t=claim.t, speaker=claim.speaker, quote=claim.quote, type="inaccuracy",
                              label=label, reason=v["reason"], confidence=v["confidence"],
                              sources=sources, note=v.get("note"), measures=v.get("measures", []),
                              controversy=v.get("controversy")))
        if outcomes[i] != "flagged":
            outcomes[i] = "flagged" if len(flags) > before else "ok"
    return flags, outcomes


def _record_flag(claim: Claim, v: dict, sources: list[dict]) -> Flag | None:
    """A contradiction with the speaker's dated record or a broken promise, else None."""
    earlier, promise = v.get("earlier"), v.get("promise")
    if earlier and v["verdict"] in WRONG and DATE.fullmatch((earlier["date"] or "")[:10]):
        source = {"publisher": earlier["publisher"], "url": earlier["url"]}
        date = earlier["date"][:10]
        return Flag(t=claim.t, speaker=claim.speaker, quote=claim.quote, type="contradiction", label="record",
                    reason=v["reason"], confidence=v["confidence"],
                    related={"t": None, "quote": earlier["quote"], "date": date, "source": source},
                    sources=[source | {"date": date}] + [s for s in sources if s["url"] != earlier["url"]])
    if promise and v["verdict"] != "true" and promise["status"] in BROKEN and sources:
        return Flag(t=claim.t, speaker=claim.speaker, quote=claim.quote, type="contradiction", label="promise",
                    reason=v["reason"], confidence=v["confidence"], sources=sources, promise=promise)
    return None


def _label(verdict: str, measures: list[dict]) -> str | None:
    """The flag label from the model's verdict and the measures, or None for no flag.

    One credible measure for the figure and one against make it disputed, whatever the verdict.
    "false" needs every credible measure against the claim, one of them from tier 1-3.
    """
    if verdict in ("definition_swap", "plan_as_fact"):
        return verdict
    wrong = verdict in ("false", "misleading")
    if not measures:
        return verdict if wrong else None
    credible = [m for m in measures if m["tier"] <= CREDIBLE_TIER]
    against = [m for m in credible if not m["supports"]]
    if against and len(against) < len(credible):
        return "disputed"
    if wrong and against and any(m["tier"] <= ANCHOR_TIER for m in against):
        return verdict
    return None


def _norm_text(text: str) -> str:
    return " ".join(w for w in (_norm(x) for x in text.split()) if w)
