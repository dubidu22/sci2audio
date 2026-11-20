# Review of sci2audio PR #139, round 2

Reviewed fix commit `50ba8ad` and final head `1def7df` (main 1fc7fb6 merged in from GitHub's update-branch, no force push), 13 Nov 2026.

| Round 1 item | State | Checked how |
|---|---|---|
| 1 `--json` into a missing folder lost the run | fixed: `json_target()` makes the folder before any work, refuses a folder path or an unwritable folder (exit 1); summary printed before the write; a failed write says so (exit 1) | my round 1 probe now writes `nope/x.json` and exits 0; two new tests |
| 2 job error ended in a traceback | fixed: a given file goes through the job's own `check_readable` (no hard-coded `.pdf`), `main` catches `JobError` and `EngineError` as `speed: …` exit 1 | probe `--paper notes.md` exits 1 before any work; three new tests |
| 3 `--quick` dropped `--voice` | fixed: `--quick` only picks the short paper; `--voice` honoured and validated | probe: `--quick --voice bf_lily` measures bf_lily; `--quick --voice xx_nobody` exits 1 with the voice list |
| 4 speech budget judged on other devices | fixed: `met = None` (not judged) off the app's device, text names the app's device | new test |

On `1def7df`: ruff, format, lint-imports (3 contracts kept) clean; fast suite 2166 passed; nightly Hypothesis profile 2166 passed (5 min 48 s); CI all green on Linux, macOS, Windows, browser, lint and layers, licences, security, CodeQL. Nothing deferred, no open findings. **Approved; merged.**
