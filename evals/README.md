# Measurements

Runs on a real interview, a paid model or the person's own machine. CI never runs them. Each one prints `PASS` or `FAIL` against the bar that its slice set.

- Run each one from the repo root: `bash evals/<script> …`.
- A run spends the subscription or API key of the person who runs it. Set the keys (`FACT_CHECK_API_KEY`, `HF_TOKEN`, …) in your own terminal.
- The real video ids and marks stay in the helper home (`FACT_CHECKER_HOME` or `~/.fact-checker`), never in the repo.
- `--no-run`, where a script takes it, scores a run that is already there and spends nothing.

| Script | Measures | Run |
|---|---|---|
| `s1-a1-helper-serves-flags.sh` | The helper analyses a 15-minute video and serves its fallacy flags; a second ask calls Claude zero times | `<youtube-url>` · Claude Code |
| `s2-a1-real-inaccuracy-flags.sh` | A 112-minute interview gets inaccuracy flags with dated sources | `<youtube-url>` · Claude Code, Google key |
| `s3-a1-eval-on-golden.sh` | Precision and recall per flag type on `tests/golden/`, and the bar it picks | no argument · Claude Code, Google key |
| `s5-a1-voices-named.sh` | The voices of a real video are separated and named | `<youtube-url>` · Claude Code, pyannote (`HF_TOKEN`) |
| `s5-a4-marks-regression.sh` | The cards marked unfair stay gone on a new analysis; the correct ones come back | `[flag-file]` · Claude Code, pyannote, Google key |
| `s6-a3-a4-real-window.sh` | A swapped metric and a plan told as a fact are flagged in a window of the 112-minute interview | `<definition_swap\|plan_as_fact> [flag-file]` · Claude Code, Google key |
| `s7-a4-real-dodged-question.sh` | A dodged question shows in a window of the 112-minute interview | `[flag-file]` · Claude Code |
| `s9-a4-real-promise.sh` | A promise shows its status in a window of the 112-minute interview | `[flag-file]` · Claude Code, Google key |
| `s10-a3-real-context.sh` | A named minister gets a context card in a window of the 112-minute interview | `[flag-file]` · Claude Code |
| `s12-a2-whisper-real.sh` | Whisper turns the audio of a 14-minute interview into at least 2,000 timed words | `<youtube-url>` · Apple silicon |
| `s15-a4-judge-real-marks.sh` | The judge agrees with the person's marks on the 1.5-hour interview | `REAL_VIDEO=<id>` `[--no-run]` · Claude Code |
| `s16-a4-real-recall.sh` | High-importance misses caught on the 1.5-hour interview, S16 bars | `REAL_VIDEO=<id> RECALL_HOME=<dir>` `[--no-run]` · Claude Code |
| `s17-a4-real-cost.sh` | Cost of the 1.5-hour interview, at most 7 dollars, with no less recall | `REAL_VIDEO=<id> RECALL_HOME=<dir>` `[--no-run]` · Claude Code |
| `s18-a4-context-ab.sh` | Cost and recall per context mode (window, conversation) | `REAL_VIDEO=<id> RECALL_HOME=<dir>` `[--no-run]` · Claude Code |
| `s19-a2-judge-keeps-contradictions.sh` | The judge keeps the self-contradictions of the S18 runs | `RECALL_HOME=<dir>` `[--no-run]` · Claude Code |
| `s19-a3-real-recall.sh` | Misses caught, judge drop share and cost of the default analysis, S19 bars | `REAL_VIDEO=<id> RUN_HOME=<dir>` `[--no-run]` · Claude Code |
| `s20-a3-codex-real.sh` | Precision on the person's marks and recall with Codex, beside Claude | `REAL_VIDEO=<id> CODEX_HOME_RUN=<dir>` `[--no-run]` · Codex |
| `s21-a3-no-diarization.sh` | What speakers from the text lose against speakers from the voices | `<scratch helper home>` · none (reads a finished run) |
| `s34-a4-real-severity.sh` | The judge spreads the kept flags of the 1.5-hour interview over the three severity levels | `REAL_VIDEO=<id>` `[JUDGE_HOME=<dir>]` `[--no-run]` · Claude Code |
| `s35-a3-card-render.sh` | The profile card follows the CALVET board, every text at 30 px or more | no argument · headless Chrome (macOS) |
| `s36-a3-compare-render.sh` | The comparison card follows the CALVET board, every text at 30 px or more | no argument · headless Chrome (macOS) |
