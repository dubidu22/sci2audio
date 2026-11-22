# Review PR #730, round 1 (ruleset 1.10.0, #729, D-877)

Thread: review-730 (Opus 5.5 high). Head reviewed: 4ec26e46c376608b0464c7767aa340710300ccd6. Base: `main` at 85aed7e (the PR is up to date with it). Date: 2026-11-22.
**Critical: yes** (META-01, CRIT-01: the ruleset, all 7 extracts, `governance-config.json` and `governance/tools/ledger_tool.py`, all in `project_profile.critical_paths`; `risk:high`, `lane:infra`). Plan `plans/ruleset-1-10-settings-plan.md`; the owner's yes is "Yes, with restore" (22 Nov 2026), and D-877 quotes his request.

**Verdict: approved** (0 must-fix, 2 should-fix, 3 notes). Neither should-fix finding needs a commit. Both are answered by filing Issues (GH-01, CRIT-02) and naming them in the PR body. The merge needs the coordinator's go (critical), pinned to 4ec26e4.

## Verified

- **The regeneration is reproducible.** I copied `governance/` at 85aed7e into a scratch git repo and ran the skill's `generate_project_rules.py --from-json <main config> --out-dir <scratch>/governance --set 'dispatcher_model=Opus 5.5 high' --set 'promised_tests_check=the governance check'`, then `scaffold_workspace.py --refresh`.
  - It changed exactly the PR's 12 governance files: the ruleset, the 7 extracts, the config, `dispatcher_instructions.md`, `ledger/README.md` and `tools/ledger_tool.py`.
  - 10 of them match the PR byte for byte.
  - The other two, `claude-project-rules.yaml` and `rules/implementation.yaml`, each differ from the PR in one line: PLAN-01. The PR's PLAN-01 is the D-849 text word for word, so its diff from 85aed7e is empty.
  - `project_instructions.md`, `claude-md-snippet.md`, `kb/README.md`, `plans/README.md` and `project-state.yaml` come out unchanged, as the PR body says.
  - The generator's own summary is "version 1.9.0 -> 1.10.0; promised_tests_check, dispatcher set; rules reworded: PLAN-01, THR-16". That matches the body: THR-16 comes from the generator and PLAN-01 is the one restore.
  - So there is no hand edit beyond the named restore.
- **The extracts.** Across all 7, the diff has 4 kinds of lines: version, date, `promised_tests_check`, and `dispatcher: "Opus 5.5 high"`. The coordinator extract also has the THR-16 line.
- **The config.** `dispatcher_model` and `promised_tests_check` are new. `advisor: false` and `advisor_model: ""` are new too. The other keys only move, with the same values. `pr-checks.json`, `lanes.yml`, `labeler.yml` and CODEOWNERS are untouched, and `test_ruleset.py` and `test_lanes.py` still find them in agreement with the config.
- **D-872 fixes have not regressed.**
  - INV-12 still says "one PR per milestone or batch (kb_pr_cadence)".
  - CRIT-01 still reads "(excluding the KB thread's decision-log PR)". No "daily" or "per day" is left in the ruleset, the extracts, either instructions file or CLAUDE.md.
  - CLAUDE.md is unchanged, so its merge-go lines (15 and 42) keep the dispatcher's go for PRs confirmed non-critical.
- **The dispatcher's model is stated nowhere else.** No repo doc says the dispatcher runs on Sonnet. `operations: "Sonnet 5.5 high"` stays only as the assist slot, and no rule maps the dispatcher to it.
  - The new text at `dispatcher_instructions.md:7-13` is true for the threads the dispatcher starts: implementation and critical work on Opus 5.5 high, review on Opus 5.5 medium.
  - Its fallback, a starter block for the owner plus one line to the coordinator, agrees with THR-10.
- **`ledger_tool.py` is the skill's file.** It is byte-identical to the skill's `scripts/ledger_tool.py`.
  - I tried it end to end on a scratch copy of the governance ledger, with `pr715-1.yaml` switched to `decision: fixed` and `commit: "266f10f"`.
  - `triage` lists the entry as settled ("fixed in 266f10f") and exits 0. `check` reports no problems.
- **Tests.**
  - `uv run pytest -q tests/unit/test_ruleset.py tests/unit/test_lanes.py tests/unit/test_ledger_tool.py tests/unit/test_promised_tests.py` gives 88 passed.
  - VER-02: I ran the new `test_ledger_tool.py` against the 1.9.0 `ledger_tool.py` (85aed7e) in scratch. Both tests fail there, with "`decision` must be one of ... got 'fixed'".
  - The tests cover both the regex and the triage branch. Removing the commit check would fail both: the empty commit gives no problem in the first test and lands in `settled` in the second.
  - Neither test file has narrating comments (PR-05). The two docstrings say why.
- **The skill's `audit_rules.py`** on the PR ruleset and extracts (`--no-git`) gives 0 errors and 1 warning. The warning is A08: 41 rules bind the implementation thread. It is not new to this PR.
- **CI on 4ec26e4.**
  - These are green: `CI passed`, `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)` (run 45045862504, the author's ci:full run), both Chromium shards, lint and layers, licences, security, web paths and CodeQL.
  - `governance pr checks` (run 45047523039) is green, its promised-tests step included.
  - `ci:full` was added at 16:48:18Z and removed at 17:06:07Z. Only `risk:high` and `lane:infra` remain.
- **Form.**
  - The title follows `<area>: <outcome> (#N)`.
  - The body has `Closes #729`, the promised tests, a test summary, licence, risk and out-of-scope sections.
  - The commit message carries no closing keyword.
  - All four acceptance criteria of #729 are met by the diff.

## Findings

### Should-fix

- **S1 (kind: contradiction).** `governance/dispatcher_instructions.md:7-9` now states the constraint behind D-877: "a session can start sessions only on its own model or a cheaper one". PREF-01 (`governance/claude-project-rules.yaml:329-331`, `governance-config.json` `owner_prefs[1]`) has the coordinator on Opus 5.5 high ask "one advisor thread on Fable 5.1 medium". The skill ranks Fable above Opus (`model_tier`: 4 vs 3, in `generate_project_rules.py` and `audit_rules.py`), so by the rule this PR writes down, the coordinator cannot start its own advisor. That step falls back to a starter block for Colin, which is the THR-10 failure D-877 fixes for the dispatcher. This PR did not create the contradiction: PREF-01 came with 1.9.0 (D-871). The audit does not catch it because the advisor is prose in `owner_prefs`. The plan put the switch to the generator's `advisor` setting out of scope, and changing PREF-01 is the owner's call (META-01).
  - **Fix wanted:** no change in this PR. File an Issue (lane:infra, risk:high, milestone v1.4) that asks the owner how the advisor thread is started. Either PREF-01 says the coordinator posts a starter block for the advisor, or the advisor moves to the generator's `advisor`/`advisor_model` setting (ROLE-18) with that start path named. Name the Issue under "Out of scope" in the PR body.
- **S2 (kind: deferred-without-issue).** The PR body's "Out of scope" leaves two items open without an Issue (GH-01, CRIT-02 "issues for all deferred items", CLAUDE.md step 7, D-68):
  - **(a) The skill's newer `pr_checks.py` with `--self-test`** ("This could be a later lane:infra Issue"). It matters more than the body says: VER-02, unchanged since 1.9.0, names "`pr_checks.py --self-test`" as what proves the pull-request checks. The repo's `.github/governance/pr_checks.py` has no such option (`python3 .github/governance/pr_checks.py --self-test` prints the usage), so the rule points at a check this repo cannot run. #710 covers other stale scaffold copies, not this one.
  - **(b) "`fixed` only checks the commit's format, not that the commit is in the merged PR's pinned head."**
  - **Fix wanted:** file one Issue for (a) (lane:infra, risk:high, since it changes `.github/governance/`). For (b), file an Issue too, or decline it in the PR body with a reason, for example that it is the generator's design and a change belongs upstream (the owner's call, as in D-849). Link both in the PR body.

### Notes

- **N1.** D-877 expected that setting `promised_tests_check` would let a regenerated PLAN-01 keep the D-849 sentence "without a hand edit". It did not: the generator writes "by its test ID ... does not exist". So this is the third regeneration that restores PLAN-01 by hand (after D-855/D-871). `test_plan_01_carries_the_promised_tests_wording` guards the restore (META-03), and the owner approved it ("Yes, with restore"). The coordinator should still say in the merge's D-entry that D-877's "without a hand edit" did not hold, and that the upstream generator change stays the owner's call (D-849 follow-up).
- **N2.** `tests/unit/test_ledger_tool.py`'s docstring says no batch starts "on an unproved claim". The check only proves that a commit-shaped string is named, not that the commit exists. The PR body says this plainly (out of scope, point 2); the docstring overstates it slightly. No change needed.
- **N3.** `test_fixed_needs_a_commit` tests the lower bound (a 5-character SHA) but not the upper bound (41 characters). This does not block: the regex is the skill's and is anchored by `fullmatch`.

Verdict: approved. Merge on the coordinator's go, pinned to 4ec26e46c376608b0464c7767aa340710300ccd6, after `ledger_tool.py gate 730` passes and with all three systems green on that head (they are). S1 and S2 are answered by Issues, so no fix commit is needed. After the merge, the dispatcher merges main into governance (THR-14), and D-877's dispatcher replacement follows.
