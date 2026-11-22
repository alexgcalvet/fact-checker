"""S7 A1 · The helper exports its prompts, with one rule for each label that a flag can carry

Story: The owner runs `fact-checker prompts` and gets JSON with a version such as `0.1.0+3f2a9c1b7d4e` and the
readings `system`, `speakers`, `screen`, `parts`, `search`, `search_results`, `check`, `verdict` and `judge`. The
`parts` reading has a rule `insinuation` whose text is the insinuation line of its prompt. Each label that a flag can
carry (the 11 fallacies, `partial`, `dodged`, `self`, `person`, `case`, `event`, `false`, `misleading`, `disputed`,
`definition_swap`, `plan_as_fact`, `record`, `promise`) finds exactly one rule.
Edge case: WHEN one character of a prompt changes THEN the part of the version after `+` changes.

Setup: the CLI's `main()` run with the argument `prompts`, its printed JSON read back. No helper home, no model.
"""
import json
import re
import sys

from fact_checker import cli
from fact_checker.core.flags import FALLACY_LABELS

READINGS = ["system", "speakers", "screen", "parts", "search", "search_results", "check", "verdict", "judge"]
PARTS_LABELS = [*FALLACY_LABELS, "partial", "dodged", "self", "person", "case", "event"]
VERDICT_LABELS = ["false", "misleading", "disputed", "definition_swap", "plan_as_fact", "record", "promise"]


def printed(monkeypatch, capsys) -> dict:
    monkeypatch.setattr(sys, "argv", ["fact-checker", "prompts"])
    try:
        cli.main()
    except SystemExit as e:
        assert not e.code, f"FAIL S7 A1 · fact-checker prompts exited {e.code}"
    return json.loads(capsys.readouterr().out)


def test_prompts_export(monkeypatch, capsys):
    # Case 1 · fact-checker prompts → a version <package>+<12 hex> and the nine readings, in order
    data = printed(monkeypatch, capsys)
    assert set(data) == {"version", "components"}, f"FAIL S7 A1 · fields {sorted(data)}"
    assert re.fullmatch(r"[0-9A-Za-z.]+\+[0-9a-f]{12}", data["version"]), f"FAIL S7 A1 · version {data['version']}"
    assert [c["id"] for c in data["components"]] == READINGS, \
        f"FAIL S7 A1 · readings {[c['id'] for c in data['components']]}"
    assert all(set(c) == {"id", "role", "text", "rules"} and c["text"] for c in data["components"]), \
        "FAIL S7 A1 · a reading lacks id, role, text or rules"
    by_id = {c["id"]: c for c in data["components"]}
    assert by_id["parts"]["role"] == "parts" and by_id["verdict"]["role"] == "verdict" \
        and by_id["judge"]["role"] == "judge", "FAIL S7 A1 · a reading has the wrong role"

    # Case 2 · rule insinuation of parts → the insinuation line of the parts prompt
    rules = {r["id"]: r["text"] for r in by_id["parts"]["rules"]}
    assert rules.get("insinuation", "").startswith("- insinuation: suggests a grave accusation without evidence"), \
        f"FAIL S7 A1 · insinuation rule {rules.get('insinuation')!r}"
    assert rules["insinuation"] in by_id["parts"]["text"], "FAIL S7 A1 · the rule is not a span of its prompt"

    # Case 3 · each label a flag can carry → exactly one rule in the file, in its reading, a span of that text
    every = [(c["id"], r) for c in data["components"] for r in c["rules"]]
    for reading, labels in (("parts", PARTS_LABELS), ("verdict", VERDICT_LABELS)):
        for label in labels:
            found = [(c, r) for c, r in every if r["id"] == label]
            assert len(found) == 1 and found[0][0] == reading, \
                f"FAIL S7 A1 · label {label}: rules in {[c for c, _ in found]}, expected one in {reading}"
            assert found[0][1]["text"].strip() and found[0][1]["text"] in by_id[reading]["text"], \
                f"FAIL S7 A1 · the rule {label} is not a span of {reading}"

    # Case 4 · the same code twice → the same file; one character changed → another hash after the +
    from fact_checker import prompts
    assert printed(monkeypatch, capsys) == data, "FAIL S7 A1 · two exports differ"
    changed = json.loads(json.dumps(data["components"]))
    changed[3]["text"] += "."
    assert prompts.version_of(data["components"]) == data["version"], "FAIL S7 A1 · version_of differs from the export"
    assert prompts.version_of(changed).split("+")[1] != data["version"].split("+")[1], \
        "FAIL S7 A1 · a changed prompt keeps its version"
    print("PASS S7 A1 · The helper exports its prompts, with one rule for each label that a flag can carry")
