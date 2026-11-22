# S4 A1 · A shared analysis carries each guest's summary, and its flags add up to the card
#
# Story: The helper shares the invented debate (guests Ana and Luis). The upload holds, for each guest, the claims
# checked and questions asked, and for each flag of that guest the numbers it adds to. Adding up every flag gives
# exactly the numbers of the guest's profile card, such as Ana's false, misleading, nitpick and correct claims of her
# claims checked. The upload of the invented debate is the one written in the API examples.
#
# Setup: the invented debate of the public API tests: its 12 Spanish flags as docs/api-examples/debate-flags.json holds
# them, the guests Ana and Luis and the host Marta, 10 claims checked of Ana and 8 of Luis, 4 questions put to Ana and 3
# to Luis. A fake collector on a free local port takes the upload. The invented interview of tests/support/card_fakes.py
# (dodged questions and several devices, no marks) checks the adding up on a second file.
import json
from collections import Counter
from pathlib import Path

from card_fakes import GUEST, INTERVIEW
from fake_servers import FakeCollector
from fact_checker import analyses
from fact_checker.core import summary

EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "api-examples"
DEBATE = {
    "video_id": "debate01", "lang": "es", "spoken": "es", "status": "done", "published_at": "2026-11-10",
    "title": "Debate inventado", "channel": "Invented Channel", "duration": 3600, "analysed_until": 3600,
    "speakers": {"SPEAKER_00": "Ana", "SPEAKER_01": "Luis", "SPEAKER_02": "Marta"},
    "people": {"Ana": {"role": "guest"}, "Luis": {"role": "guest"}, "Marta": {"role": "host"}},
    "claims": {"Ana": 10, "Luis": 8}, "questions": {"Ana": 4, "Luis": 3},
    "readers": {r: {"provider": "claude", "model": "opus"} for r in ("parts", "verdict", "judge", "search")},
}


def debate() -> dict:
    return DEBATE | {"flags": json.loads((EXAMPLES / "debate-flags.json").read_text())["flags"]}


def add_up(tally: dict) -> dict:
    """The numbers of a guest from the tally of each flag: what the collector serves."""
    flags = list(tally["flags"].values())
    count = lambda key, value: sum(f[key] == value for f in flags)
    verdicts = {v: count("verdict", v) for v in ("false", "misleading", "nitpick")}
    devices, serious = Counter(), Counter()
    for f in flags:
        if f["device"]:
            devices[f["device"]] += 1
            serious[f["device"]] += f["severity"] == "serious"
    return {"checked": tally["checked"],
            "verdicts": verdicts | {"correct": tally["checked"] - sum(verdicts.values())},
            "severity": {s: count("severity", s) for s in ("serious", "moderate", "minor")},
            "devices": sorted(devices.items(), key=lambda x: (-x[1], -serious[x[0]])),
            "dodged": count("question", "dodged"), "partial": count("question", "partial"), "asked": tally["asked"],
            "gravest": tally["gravest"][:2]}


def card_numbers(data: dict, name: str) -> dict:
    """The same numbers from the profile card, with each device by its label id."""
    c = summary.card(data, name)
    ids = {text: label for label, text in summary.TEXTS[c["lang"]]["labels"].items()}
    by_second = {f["t"]: f["id"] for f in data["flags"] if summary.speaker(f) == name}
    return {k: c[k] for k in ("checked", "verdicts", "severity", "dodged", "partial", "asked")} | {
        "devices": [(ids.get(text, text), n) for text, n in c["devices"]],
        "gravest": [by_second[g["t"]] for g in c["gravest"]]}


def test_summary_upload(tmp_path):
    collector = FakeCollector()
    try:
        # Case 1 · the helper shares the invented debate → the upload's summary has Ana and Luis, equal to the example
        analyses.upload(tmp_path, collector.url, debate())
        sent = collector.requests[-1]["body"]["analysis"]
        assert list(sent["summary"]) == ["Ana", "Luis"]
        assert sent["summary"] == json.loads((EXAMPLES / "summary-upload.json").read_text())
        assert sent["flags"] == debate()["flags"]
        print("PASS S4 A1 · the upload carries the summary of the API examples")

        # Case 2 · Ana's flags added up → her card: 2 false, 1 misleading, 1 nitpick and 6 correct of 10 checked
        ana = add_up(sent["summary"]["Ana"])
        assert ana["verdicts"] == {"false": 2, "misleading": 1, "nitpick": 1, "correct": 6}
        assert ana["checked"] == 10 and ana["asked"] == 4
        for name in ("Ana", "Luis"):
            assert add_up(sent["summary"][name]) == card_numbers(debate(), name), name

        # Case 3 · the interview's guest (dodged questions, several devices) → the adding up equals the card too
        tally = analyses.strip(INTERVIEW)["summary"][GUEST]
        assert add_up(tally) == card_numbers(INTERVIEW, GUEST)
        assert add_up(tally)["dodged"] > 0 and len(add_up(tally)["devices"]) > 1
        print("PASS S4 A1 · A shared analysis carries each guest's summary, and its flags add up to the card")
    finally:
        collector.stop()
