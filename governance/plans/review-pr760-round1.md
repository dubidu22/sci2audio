# Review PR #760, round 1

- PR: https://github.com/dubidu22/sci2audio/pull/760 (closes #756, #757, #758, #759; impl-infra-b005; plan `plans/impl-infra-b005-plan.md`, approved as D-899)
- Head: `a25a67ec06b769715b2f6baaec696d5d68e81986`, base `8965914` (= main, not behind)
- Thread: review-b005 (Opus 5.5 high), 2026-11-23
- **Critical: yes** (CRIT-03): `governance/tools/**`, `.github/governance/**`, the ruleset, its config and all seven extracts (critical_paths). Labels `risk:high, lane:infra, lane:docs`.
- **Verdict: approved.** 0 must-fix, 0 should-fix, 0 deferred, 2 notes.

## Verified checks

- `ci:full` run 45160343600 on a25a67e: `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, `lint and layers`, `security`, `CI passed` success; `ci:full` removed.
- `governance pr checks` (job 137655228199): red only on `no review round is recorded` (the D-882 `approved` step); `comments: ok`; one WARN `unowned` for the three test files, as for earlier infra PRs.
- Locally: `test_ledger_tool.py`, `test_narrating_comments.py`, `test_ruleset.py` 80 passed. Every node ID of plan section 5 exists.
- `.github/governance/pr_checks.py` and `governance/github-setup/pr_checks.py` are byte-equal (`cmp`).

### Ruleset: the net change (coordinator's points a and b)

- `git diff 8965914 a25a67e` over `governance/claude-project-rules.yaml` and `governance/rules/*.yaml` (8 files): each file changes exactly two lines, `version: 1.14.0 -> 1.15.0` and the PREF-01 rule, which loses the advisor sentence and keeps the time-zone and terminal-command sentences. MRG-01, PLAN-01, ROLE-11, ROLE-17 and THR-04 are byte-identical to main, so the "restored to main's wording" step is a no-op against main and every exact-replace text in them (D-849, D-882) survives unchanged.
- `governance/governance-config.json`: only `ruleset_version` and `owner_prefs` (the advisor sentence) change. There is no `claude_code_host` key on main or on the head (`git grep` finds none in `governance/`), so the generator's `local` value never reached the committed tree; nothing contradicts #751/D-889.
- #759 AC2: `git grep` for "advisor thread" and "Fable 5.1" outside the decision log finds only the KB's historic `[advisor]` status tags and D-73's model note in the toolkit playbook, none an advisor-thread rule; `test_no_instruction_file_asks_for_an_advisor_thread` pins the instruction files.

### F1 and F2 (#756, #757)

- `check` with the PR's tool on the current governance ledger (after `git fetch origin main 'release/*'`): `36 PR entries and 55 round entries, no problems.`, exit 0. The coordinator's fix of `prs/pr-753.yaml` (`merged: "8965914 2026-11-23"`) is in; round 1 of #753 also records the merge.
- CI calls only `ledger_tool.py approved`, never `check`, so `check`'s new exit 2 (no origin/main refs) cannot break a PR's checks; it falls on the thread that runs it, as intended.
- Last `(#N)` of a subject, release branches, unreadable subjects (exit 2), sum of `deferred` over rounds, required from PR 760 on, non-number refused, triage listing: each has its unit test, and each test fails without its code per the PR's first commit (tests first, 1ad7a62).

### Narrating comments (#758)

- VER-02, checked by this review: a comment `# previously this used a cache` appended to `src/sci2audio/core/__init__.py` fails `test_no_comment_or_docstring_narrates_the_change` naming `path:line`; a docstring "it used to call write_audiobook" in `output/chapters.py` fails it too. Both reverted.
- The PR body states the limit (a comment that says what instead of why stays the reviewer's), as #758 asks.

## Findings

- **N1** (note). `owed_deferrals` and triage's should-fix rule both count the same `deferred/pr<N>-*.yaml` files. A round that records a finding both as `should_fix` left open at merge and as `deferred` is satisfied by one file, which is right for one finding; a round that leaves one should-fix open *and* defers a different finding needs two files, but each rule alone sees one and passes. README's wording (`deferred` = set aside instead of fixing) makes the two disjoint only by convention. No change asked; if it recurs, `check` could compare the files against `max` or the sum of both.
- **N2** (note). From this merge on, every round entry of PR 760 and later needs `deferred:` (this round's entry already carries it). Review threads write it; the README example shows it.

## Handoff (THR-07)

- Goal: critical review round 1 of #760 at a25a67e.
- Done: ruleset net change confirmed (PREF-01 and version only), ledger check clean on the real ledger, narration check shown to fail on a planted comment and docstring, three-system run green.
- Next: the coordinator's go `ledger/gos/pr-760.yaml` for a25a67e; then `ledger_tool.py gate 760`, rerun `governance pr checks` if still red, squash-merge pinned to a25a67e, and record the merge and main's three-system run here.

## Merge

- Squash-merged by this thread on the coordinator's go (D-900), pinned to a25a67e, after `ledger_tool.py gate 760` said it may be merged and `tests (ubuntu|macos|windows-latest)`, `CI passed` and `governance pr checks` were green on that head: `e3a328e65f78a86341d5d03dc77680f4cab6c441`.
- main merged into governance with a plain merge afterwards (THR-14), so governance carries ruleset 1.15.0 and the new extracts.
