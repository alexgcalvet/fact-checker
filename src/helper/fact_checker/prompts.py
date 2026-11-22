"""The helper's prompts as one JSON file: each reading with its fixed rules, and the rule behind each flag label.

The version names the exact texts: the package version, then the first 12 hex digits of the SHA-256 of the components
as compact JSON. The collector computes the same hash (JSON.stringify), so nobody can store other texts under it.
"""
import hashlib
import json

from fact_checker.core import factcheck, judge, pipeline, speakers
from fact_checker.core.flags import FALLACY_LABELS, SYSTEM
from fact_checker.feedback import helper_version


def _block(text: str, start: str) -> str:
    """The first line of `text` that starts with `start`, with its own lines: a bullet ("- ") keeps its indented lines,
    a paragraph runs to the next blank line."""
    lines = text.splitlines()
    i = next(n for n, line in enumerate(lines) if line.startswith(start))
    end = i + 1
    while end < len(lines) and (lines[end].startswith("  ") if start.startswith("- ") else lines[end].strip()):
        end += 1
    return "\n".join(lines[i:end])


def _rules(text: str, starts: dict[str, str]) -> list[dict]:
    return [{"id": label, "text": _block(text, start)} for label, start in starts.items()]


def components() -> list[dict]:
    status = "- status:"
    context = "Also list at most 2 people"
    parts = {label: f"- {label}:" for label in FALLACY_LABELS} | {
        "partial": status, "dodged": status, "self": "Also list each statement in the PART that says the opposite",
        "person": context, "case": context, "event": context}
    verdict = {"false": "- verdict:", "misleading": "- verdict:", "disputed": "An official figure is not the truth",
               "definition_swap": "- definition_swap:", "plan_as_fact": "- plan_as_fact:", "record": "- own_words:",
               "promise": "- promise:"}
    reading = lambda key, role, text, rules=(): {"id": key, "role": role, "text": text, "rules": list(rules)}
    return [
        reading("system", "every", SYSTEM),
        reading("speakers", "parts", speakers.PROMPT),
        reading("screen", "screen", pipeline.SCREEN),
        reading("parts", "parts", pipeline.RULES, _rules(pipeline.RULES, parts)),
        reading("search", "search", factcheck.FIND),
        reading("search_results", "search", factcheck.READ),
        # The one reading that searches and judges shares the verdict's text; its rules live once, in `verdict`.
        reading("check", "verdict", factcheck.CHECK),
        reading("verdict", "verdict", factcheck.VERDICT, _rules(factcheck.VERDICT, verdict)),
        reading("judge", "judge", judge.PROMPT.replace("{rules}", judge.RULES)),
    ]


def version_of(items: list[dict], package: str | None = None) -> str:
    compact = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    return f"{package or helper_version()}+{hashlib.sha256(compact.encode()).hexdigest()[:12]}"


def export() -> dict:
    items = components()
    return {"version": version_of(items), "components": items}
