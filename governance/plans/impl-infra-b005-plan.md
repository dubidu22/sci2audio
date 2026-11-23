# Plan impl-infra-b005: ledger and lint checks (batch 005, slot B, item 2)

Thread: impl-infra-b005 (implementation, Opus 5.5 high). Issues: #756 (F1), #757 (F2), #758 (narrating comments), #759 (PREF-01), all v1.5, lane:infra, risk:high. Sources: `plans/batch-005.md` slot B item 2, `plans/audit-batch-004.md` F1/F2, D-891, D-892, D-896.

**Critical: yes** (CRIT-01: `governance/tools/**`, `.github/**`, the ruleset and its extracts). One PR, labels `lane:infra, lane:docs, risk:high`, title `governance: the ledger check sees unrecorded merges and deferrals, comments that narrate fail (#756)`, body `Closes #756`, `Closes #757`, `Closes #758`, `Closes #759`. Base: main at 8965914 (#744 merged, so the lane:infra lock is free).

## 1. F1: unrecorded merges (#756)

- `governance/tools/ledger_tool.py`: new `squash_numbers(subjects) -> set[str]` takes the PR number from the **last** `(#N)` of each subject (`\(#(\d+)\)\s*$`), so `voices: ... (#744) (#753)` gives 753, not 744.
- `check` reads subjects from `--subjects FILE` if given; else runs `git -C <ledger> for-each-ref refs/remotes/origin/main refs/remotes/origin/release/` and `git log --format=%s <those refs>`. No ref, no git, or a git error: exit 2 with the reason and the hint `pass --subjects or git fetch origin main 'release/*'`. Never a silent pass.
- New problem line: `prs/pr-<N>.yaml: PR #N is merged (a squash subject on main or release/* ends with (#N)) but no round or PR entry records the merge`.
- Read-only stays true (git log only). Standard library only stays true.
- Today's ledger: a trial run finds exactly one entry, `prs/pr-753.yaml` (#744's PR, merged 8965914). That is a data fix for the writer of #753's merge record, not for this PR; the PR body names it.

## 2. F2: deferrals in a round (#757)

- Round entries gain `deferred: <n>` (whole number, in `INT_KEYS`): findings of this or earlier rounds that this round sets aside instead of fixing.
- `check` fails per PR when `len(deferred/pr<N>-*.yaml) < sum(deferred over that PR's rounds)`. Sum, not last round, so two rounds that each defer one need two files.
- `deferred` is **required** on round entries of PRs numbered from `DEFERRED_FROM_PR` (this PR's number) on, so the approving round cannot forget it; older entries are not asked. This is the design step of META-03: the field cannot be left out, rather than a field that may be.
- `triage` adds a round whose `deferred` outnumbers the PR's `deferred/` files to "Needs a decision", like the should_fix case.
- `governance/ledger/README.md` (lane:docs): the field, its meaning, an example. The review extract already sends round writers to that README (its round-report rule: "each round also gets a ledger entry (./governance/ledger/README.md)"), so no ruleset text changes for F2.

## 3. Narrating comments, one step up (#758)

What regressed: #739 N2 (a docstring that says what) and #751 round 2 S1 ("... ended with the move to the claude.ai Project (D-888, ruleset 1.14.0); the D888 pins below replace them", change history in a test comment). Today `pr_checks.py` only warns, sees only lines that start with a comment marker, and its broad list hits 56 legitimate comments and docstrings in the tree (mostly "no longer", "moved to"), too many to fail on.

- `.github/governance/pr_checks.py`: a new `HISTORY_RE`, a strict list of change-history and conversation phrases: previously; as requested/discussed/agreed; per the review/feedback/request; was changed; changed from/to; now use(s); we now / now we; the old/new implementation, old/new code, old approach/behaviour; in this PR/commit/change; before/after this PR/change/commit; this PR/commit adds/removes/...; reviewer asked/wanted/said/found; ended with / went away with / was dropped with (the move, ...); was added/removed/renamed/moved/replaced/rewritten in/by/for/when; used to be/call/use/read/... A trial scan of the tree with that list finds 0 real hits once `\b` closes "PR" (it matched "process") and "old version" is left out (`app/audio.py` "the old versions are gone" is a why).
- `comment_notes` reports a `HISTORY_RE` match as FAIL ("comments" check, PR-05) and keeps the broad list as WARN. "comments" joins `EXEMPTABLE`, so a sanctioned case goes in `pr-check-exemptions.json` (PR-04), never in a private list. `governance/github-setup/pr_checks.py` is updated byte-equal (the #706 test holds it).
- New fast test `tests/unit/test_narrating_comments.py` imports `HISTORY_RE` from `pr_checks.py` (one list, no drift) and scans every comment (`tokenize`) and docstring (`ast`) of the Python files in `src/`, `tests/`, `scripts/`, `.github/`, `governance/tools/`. It runs locally in the fast checks, so the author sees it before review, and on every PR in CI. Skipped: the two `pr_checks.py` copies and the test file itself, which quote the phrases.
- Honest limit, in the PR body and the test's docstring: a comment that says what instead of why (#739 N2) has no word to match; it stays the reviewer's finding.

## 4. PREF-01 and the test comment (#759)

- Through the governance skill (`project-governance-init`, change-a-setting mode): drop the advisor sentence from `owner_prefs` in `governance/governance-config.json`, regenerate `governance/claude-project-rules.yaml` and all of `governance/rules/*.yaml`, version 1.14.0 to 1.15.0 (a rule's meaning changes). META-01 is met by Colin's word quoted in D-892 (2026-11-23T08:48Z). PREF-01 keeps the time-zone and terminal-command sentences. `advisor: false` and `advisor_model: ""` already say the same and stay.
- `tests/unit/test_ruleset.py`: the comment above `PROJECT_CHANNEL_START` cites the Project instructions ("Ask for as few clicks as possible") instead of PREF-01 (D-896).

## 5. Tests promised in the plan (written first, each fails before its code)

- `tests/unit/test_ledger_tool.py::test_check_fails_on_a_merged_pr_whose_entry_records_no_merge`
- `tests/unit/test_ledger_tool.py::test_check_passes_when_the_merge_is_recorded`
- `tests/unit/test_ledger_tool.py::test_check_takes_the_last_number_of_a_squash_subject`
- `tests/unit/test_ledger_tool.py::test_check_counts_a_squash_subject_on_a_release_branch`
- `tests/unit/test_ledger_tool.py::test_check_exits_2_when_the_subjects_cannot_be_read`
- `tests/unit/test_ledger_tool.py::test_check_fails_when_fewer_deferred_files_than_the_rounds_defer`
- `tests/unit/test_ledger_tool.py::test_check_passes_when_every_deferral_has_a_file`
- `tests/unit/test_ledger_tool.py::test_a_new_round_entry_without_deferred_fails`
- `tests/unit/test_ledger_tool.py::test_an_old_round_entry_without_deferred_passes`
- `tests/unit/test_ledger_tool.py::test_deferred_must_be_a_whole_number`
- `tests/unit/test_ledger_tool.py::test_triage_lists_a_round_that_deferred_without_a_file`
- `tests/unit/test_narrating_comments.py::test_no_comment_or_docstring_narrates_the_change`
- `tests/unit/test_narrating_comments.py::test_the_history_list_catches_change_history` (parametrized; includes the #751 S1 text)
- `tests/unit/test_narrating_comments.py::test_the_history_list_leaves_why_comments_alone` (parametrized; "no longer fits", "in this process", "the old versions are gone", "moved to its mark")
- `tests/unit/test_narrating_comments.py::test_an_added_change_history_comment_fails_the_pr_check`
- `tests/unit/test_narrating_comments.py::test_a_broad_list_match_only_warns`
- `tests/unit/test_narrating_comments.py::test_a_sanctioned_exemption_lets_a_comment_through`
- `tests/unit/test_ruleset.py::test_pref_01_names_no_advisor_thread`
- `tests/unit/test_ruleset.py::test_no_instruction_file_asks_for_an_advisor_thread`

Then the full fast checks, `uv run zizmor --offline .github/workflows` (no workflow file changes expected), and a `ci:full` three-system run before review (D-698), label removed after.

## 6. Size and files

About 150 lines in `ledger_tool.py`, 40 in `pr_checks.py` (twice), 250 lines of tests, the README section, the regenerated ruleset (one sentence fewer in 8 files plus the version). Files: `governance/tools/ledger_tool.py`, `governance/ledger/README.md`, `.github/governance/pr_checks.py`, `governance/github-setup/pr_checks.py`, `governance/governance-config.json`, `governance/claude-project-rules.yaml`, `governance/rules/*.yaml`, `tests/unit/test_ledger_tool.py`, `tests/unit/test_narrating_comments.py` (new), `tests/unit/test_ruleset.py`. No product code, no workflow file.

## 7. Choices made (no open choice left)

- One PR for all four, as the batch file says; the parts share `ledger_tool.py` and the ruleset tests, so splitting would serialize them on the lane:infra lock anyway.
- `check` gets subjects from git by default, not only from a file, so a thread that runs `check` cannot forget them; a file option keeps the tests deterministic.
- `deferred` required from this PR on, sum over rounds.
- The failing narration check is a strict list plus the existing broad warning, not the broad list turned to FAIL (56 false hits).

## Handoff (THR-07)

- Goal: one critical lane:infra PR closing #756 to #759.
- Done: Issues opened, plan written; trial scans show 1 unrecorded merge (#753) and 0 strict-list hits in the tree.
- Next: coordinator approval, then tests first, then code, `ci:full`, PR, ledger entry.
