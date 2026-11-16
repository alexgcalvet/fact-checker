#!/usr/bin/env bash
# S42 A3 · No line of code loses its test
# record: save the lines of fact_checker that the helper suite runs, per file, to coverage-before.json, with the commit
#   and the hash of each file's text. Record on a clean src/helper.
# compare: run the suite again and fail on any line covered before and not now. A line of code that changed since the
#   record is mapped by its text (difflib), so a change by someone else to the code does not count as a lost test.
set -euo pipefail

spec_dir="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$spec_dir/../../.." && pwd)"
before="$spec_dir/coverage-before.json"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

(cd "$repo/src/helper" && COVERAGE_FILE="$work/.coverage" uvx --quiet --with pytest-cov pytest -c pyproject.toml -q \
  -p no:cacheprovider --cov=fact_checker --cov-report="json:$work/report.json" >/dev/null)

case "${1:-}" in
  record)
    python3 - "$work/report.json" "$before" "$repo" <<'EOF'
import hashlib, json, subprocess, sys
from pathlib import Path
report, before, repo = json.load(open(sys.argv[1]))["files"], sys.argv[2], Path(sys.argv[3])
commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
files = {path: {"sha1": hashlib.sha1((repo / "src/helper" / path).read_bytes()).hexdigest(),
                "lines": data["executed_lines"]} for path, data in sorted(report.items())}
body = ",\n".join(f"  {json.dumps(k)}: {json.dumps(v)}" for k, v in files.items())
open(before, "w").write('{"commit": %s, "files": {\n%s\n}}\n' % (json.dumps(commit), body))
print(f"recorded {sum(len(f['lines']) for f in files.values())} lines in {len(files)} files at {commit[:7]}")
EOF
    ;;
  compare)
    python3 - "$work/report.json" "$before" "$repo" <<'EOF'
import difflib, hashlib, json, subprocess, sys
from pathlib import Path
now = {p: set(d["executed_lines"]) for p, d in json.load(open(sys.argv[1]))["files"].items()}
before, repo = json.load(open(sys.argv[2])), Path(sys.argv[3])
lost, changed = {}, 0
for path, rec in before["files"].items():
    current = repo / "src/helper" / path
    new_text = current.read_text() if current.exists() else ""
    if hashlib.sha1(new_text.encode()).hexdigest() == rec["sha1"]:
        mapping = {n: n for n in rec["lines"]}
    else:
        old_text = subprocess.run(["git", "show", f"{before['commit']}:src/helper/{path}"], cwd=repo,
                                  capture_output=True, text=True).stdout
        if hashlib.sha1(old_text.encode()).hexdigest() != rec["sha1"]:
            sys.exit(f"FAIL S42 A3 · {path}: the recorded text is not at {before['commit'][:7]}; record again")
        blocks = difflib.SequenceMatcher(None, old_text.splitlines(), new_text.splitlines(), autojunk=False)
        mapping = {}
        for a, b, size in blocks.get_matching_blocks():
            mapping.update({a + i + 1: b + i + 1 for i in range(size)})
    gone = [n for n in rec["lines"] if n in mapping and mapping[n] not in now.get(path, set())]
    changed += sum(n not in mapping for n in rec["lines"])
    if gone:
        lost[path] = gone
for path, lines in lost.items():
    print(f"FAIL S42 A3 · {path} lost lines {lines} (line numbers at the record)")
if changed:
    print(f"note: {changed} covered lines changed in the code since the record and were not compared")
if lost:
    sys.exit(1)
print("PASS S42 A3 · No line of code loses its test")
EOF
    ;;
  *) echo "usage: coverage.sh record|compare" >&2; exit 2 ;;
esac
