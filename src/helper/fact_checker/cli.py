import argparse
import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path

from fact_checker import analyses, feedback, install, server
from fact_checker.adapters.diarization import Diarizer
from fact_checker.adapters.factcheck_google import GoogleFactCheck
from fact_checker.adapters.whisper import Whisper
from fact_checker.adapters.youtube import YouTube
from fact_checker.core import judge, scheduler, score, speakers
from fact_checker.core.flags import Segment, Transcript
from fact_checker.store import default_home

GOLDEN = Path(__file__).resolve().parents[3] / "tests" / "golden"
TYPES = ("fallacy", "inaccuracy", "contradiction")
WORD_SECONDS = 0.4


class CountingLLM:
    def __init__(self, llm):
        self.llm = llm
        self.calls = 0

    def complete(self, prompt, schema, tools=()):
        self.calls += 1
        return self.llm.complete(prompt, schema, tools=tools) if tools else self.llm.complete(prompt, schema)


class GoldenTranscript:
    def __init__(self, dialogue: dict):
        self.dialogue = dialogue

    def fetch(self, video_id):
        segments = [Segment(t=line["t"] + i * WORD_SECONDS, text=w)
                    for line in self.dialogue["lines"] for i, w in enumerate(line["text"].split())]
        return Transcript(segments=segments, published_at=self.dialogue["published_at"])


def _pct(x: float | None) -> str:
    return "  -" if x is None else f"{x:.0%}"


def run_eval(golden: Path, *, llm, factcheck, save_to: Path | None = None) -> dict:
    """Runs the analysis on every golden dialogue, prints precision and recall per type, and picks the bars."""
    counting = CountingLLM(llm)
    scored = {t: [] for t in TYPES}
    found = {t: 0 for t in TYPES}
    total = {t: 0 for t in TYPES}
    with tempfile.TemporaryDirectory() as home:
        for path in sorted(Path(golden).glob("*.json")):
            dialogue = json.loads(path.read_text())
            server.run_analysis(path.stem, 0, transcript=GoldenTranscript(dialogue), llm=counting,
                                factcheck=factcheck, home=Path(home))
            flags = json.loads((Path(home) / "videos" / f"{path.stem}.json").read_text())["flags"]
            for t in TYPES:
                s, f, n = score.score(flags, dialogue["expected"], t)
                scored[t] += s
                found[t] += f
                total[t] += n

    report = {}
    print("type          precision recall | " + "  ".join(f"{b}" for b in score.BARS) + " | bar")
    for t in TYPES:
        precision, recall = score.precision_recall(scored[t], total[t])
        bars = {b: score.precision_recall(scored[t], total[t], b) for b in score.BARS}
        bar = score.pick_bar(scored[t])
        report[t] = {"precision": precision, "recall": recall, "matched": found[t], "flags": len(scored[t]),
                     "expected": total[t], "bars": bars, "bar": bar}
        cells = "  ".join(f"{_pct(p)}/{_pct(r)}" for p, r in bars.values())
        print(f"{t:<13} {_pct(precision):>9} {_pct(recall):>6} | {cells} | {bar if bar is not None else 'never'}")
    print(f"Claude tool calls: {counting.calls}")
    if save_to:
        # A type with no flag and no expected one gives no evidence for a bar; it keeps the default bar.
        seen = [t for t in TYPES if report[t]["flags"] or report[t]["expected"]]
        Path(save_to).write_text(json.dumps({t: report[t]["bar"] for t in seen}) + "\n")
    return report


def report_marks(home: Path) -> dict:
    """Prints the precision per type and name on the person's marks; the latest mark of a flag counts."""
    path = Path(home) / "marks.jsonl"
    latest = {}
    for line in (path.read_text().splitlines() if path.exists() else []):
        m = json.loads(line)
        latest[(m["video_id"], m["flag_id"])] = m
    report = {}
    print("real marks    precision        | bar")
    for t in TYPES:
        marks = [m for m in latest.values() if m["type"] == t]
        correct = sum(m["verdict"] == "correct" for m in marks)
        bar = score.pick_bar([(m["confidence"], m["verdict"] == "correct") for m in marks])
        report[t] = {"marked": len(marks), "correct": correct, "bar": bar}
        print(f"{t:<13} {_pct(correct / len(marks) if marks else None):>5} ({correct}/{len(marks)}) | "
              f"{bar if bar is not None else 'never'}")
        for label in sorted({m["label"] for m in marks}):
            ms = [m for m in marks if m["label"] == label]
            ok = sum(m["verdict"] == "correct" for m in ms)
            print(f"  {label:<22} {_pct(ok / len(ms)):>5} ({ok}/{len(ms)})")
    return report


def run_judge(video_id: str, home: Path, against_marks: bool) -> bool:
    """Judges an analysed video again and writes the verdicts into its flag file.

    The transcript comes from the cached captions and voice turns, with the speaker names of the flag file.
    With `against_marks`, prints how the verdicts meet the person's latest marks; False when they do not.
    """
    path = home / "videos" / f"{video_id}.json"
    data = json.loads(path.read_text())
    audio = YouTube(home / "audio")
    engine = server.speech_cli()
    tr = YouTube(home / "captions", engine and Whisper(home / "speech", audio, engine)).fetch(video_id)
    if (home / "voices" / f"{video_id}.turns.json").exists():
        tr = speakers.assign(tr, Diarizer(home / "voices", audio).turns(video_id))
    tr = replace(tr, speakers=data["speakers"])
    llm = scheduler.BudgetedLLM(server.provider_llm(home, "judge", timeout=judge.TIMEOUT), judge.calls(tr))
    verdicts = judge.judge(data["flags"], tr, llm, data.get("lang"))
    flags = [{k: v for k, v in f.items() if k != "judge"} for f in data["flags"]]
    data["flags"] = [f | {"judge": verdicts[f["id"]]} if f["id"] in verdicts else f for f in flags]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"{len(verdicts)} flags judged: " + ", ".join(
        f"{n} {v}" for v in ("keep", "nitpick", "drop") if (n := sum(r["verdict"] == v for r in verdicts.values()))))
    if not against_marks:
        return True
    marks = server.Store(home).marks(video_id)
    by_id = {f["id"]: f for f in data["flags"]}
    unfair = [by_id[i] for i, v in marks.items() if v == "unfair" and i in by_id]
    correct = [by_id[i] for i, v in marks.items() if v == "correct" and i in by_id]
    ruled_out = [f for f in unfair if f.get("judge", {}).get("verdict") in ("drop", "nitpick")
                 or f.get("judge", {}).get("speaker")]
    touched = [f for f in correct if f.get("judge", {}).get("verdict") in ("drop", "nitpick")
               or f.get("judge", {}).get("speaker")]
    print(f"marked unfair, nitpicked or given to another speaker: {len(ruled_out)} of {len(unfair)}")
    print(f"marked correct, touched: {len(touched)} of {len(correct)}")
    return len(ruled_out) >= 6 and len(touched) <= 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="fact-checker")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8765)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("url")
    evaluate = sub.add_parser("eval")
    evaluate.add_argument("--save", action="store_true", help="write the bars of the provider in use")
    evaluate.add_argument("--marks", action="store_true", help="only the real precision from the person's marks")
    judging = sub.add_parser("judge")
    judging.add_argument("video_id")
    judging.add_argument("--against-marks", action="store_true", help="compare the verdicts with the person's marks")
    for name, text in (("setup", "check the tools and start the helper at every login"),
                       ("doctor", "say what is missing, one line each, with the fix")):
        command = sub.add_parser(name, help=text)
        command.add_argument("--port", type=int, default=8765)
        if name == "doctor":
            command.add_argument("--json", action="store_true", help="the checks as JSON, for an agent")
    key = sub.add_parser("key", help="store a key in ~/.fact-checker/.env")
    key.add_subparsers(dest="action", required=True).add_parser(
        "set", help="type a key in a hidden prompt").add_argument("name", help="the variable, such as HF_TOKEN")
    shared = sub.add_parser("feedback", help="the testers' shared marks")
    shared.add_argument("action", choices=["pull", "send"],
                        help="pull: download the new rows from the collector; send: send your pending marks now, "
                             "or write them to a dated file to mail")
    review = sub.add_parser("shared", help="the author's review of the shared analyses that wait")
    review.add_argument("action", choices=["list", "approve", "reject"],
                        help="list: the pending uploads; approve: serve one to everyone; reject: delete it")
    review.add_argument("video_id", nargs="?")
    review.add_argument("lang", nargs="?", choices=["es", "en"])
    args = parser.parse_args()

    if args.command == "key":
        raise SystemExit(install.set_key(default_home(), args.name))
    if args.command in ("setup", "doctor"):
        raise SystemExit(install.setup(args.port) if args.command == "setup" else install.doctor(args.port, args.json))

    if args.command == "shared":
        if args.action != "list" and not args.lang:
            parser.error(f"shared {args.action} needs a video id and a language (es or en)")
        home = default_home()
        raise SystemExit(analyses.review(home, server.config(home).get("feedback_url"), args.action, args.video_id,
                                         args.lang))
    if args.command == "feedback":
        home = default_home()
        if args.action == "send":
            result = feedback.send(home, server.config(home).get("feedback_url"))
            print(f"Saved in {result['saved']}: send it to the author." if "saved" in result
                  else f"Sent {result['sent']} marks.")
            raise SystemExit(0)
        raise SystemExit(feedback.pull(home, server.config(home).get("feedback_url"),
                                       server.secret(home, "FEEDBACK_ADMIN_TOKEN")))
    key = os.environ.get("FACT_CHECK_API_KEY")
    factcheck = GoogleFactCheck(key) if key else None
    if args.command == "judge":
        raise SystemExit(0 if run_judge(args.video_id, default_home(), args.against_marks) else 1)
    if args.command == "serve":
        server.serve(args.port)
    elif args.command == "analyze":
        home = default_home()
        video_id = args.url.split("v=")[-1].split("&")[0]
        server.run_analysis(video_id, 0, transcript=YouTube(home / "captions"),
                            llm=server.provider_llm(home, "search"),
                            factcheck=factcheck, home=home)
        print(home / "videos" / f"{video_id}.json")
    else:
        if not args.marks:
            run_eval(GOLDEN, llm=server.provider_llm(default_home(), "search"), factcheck=factcheck,
                     save_to=server.bars_file(default_home()) if args.save else None)
            print()
        report_marks(default_home())


if __name__ == "__main__":
    main()
