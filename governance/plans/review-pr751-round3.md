# Review PR #751, round 3

- PR: https://github.com/dubidu22/sci2audio/pull/751 (#750, D-888; ruleset 1.13.0 → 1.14.0, claude.ai Project setup)
- Head: `bf417b9159985eedee42bd325c3e65a186de31ee` (fix commit 62f39de plus a merge of main at 0994f97, #752); up to date with main
- Thread: review-pr751-1 (Opus 5.5 high), 2026-11-23
- **Critical: yes** (unchanged).
- **Verdict: approved.** Must-fix 0, should-fix 0, notes 3.

## Round 2 findings

- **M1 fixed.** `project_chat_instructions.md` "Starting other threads" now reads: the coordinator and the dispatcher ask the Project's channel session for each worker thread and pass the starter block as its brief (D-889); only where that is not possible do they ask Colin. The THR-10 bullets of `project_instructions.md` and `dispatcher_instructions.md` say the same between the tool clause and the owner fallback, which matches the ruleset's generic THR-10. Pinned by `test_the_project_chat_instructions_start_threads_through_the_channel_session` and `test_an_instruction_file_starts_threads_through_the_channel_session[project_instructions.md|dispatcher_instructions.md]`. Proof: putting back b54bf45's copy of each of the three files fails exactly 1 test each.
- **S1 fixed.** The two change-history comment lines above `D882` are gone.

## Verified checks

- Delta b54bf45..bf417b9: 5 files. Beyond the fix, it brings in #752's decision log, and `governance/kb/decision-log.md` on the head is byte-equal to main's. The diff against main now holds only the PR's own changes.
- ci:full run 45150607713 (workflow_dispatch) on bf417b9: `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, `lint and layers`, `licences`, `security`, both Chromium shards, `web paths` and `CI passed` all success (D-580).
- Locally: `test_ruleset.py` and `test_lanes.py` give 67 passed (`pytest --noconftest`).
- The checks of round 2 still hold. The fix touches neither the ruleset, the extracts, the config nor any path list.

## Findings

- **N1** (note). The new test comment says a "no chat can open another" line "would send Colin click steps PREF-01 avoids". "As few clicks as possible" is in the "For Colin" paragraph of `project_chat_instructions.md`, not in PREF-01. The comment's reason is right and the cited rule is wrong. The next ruleset PR (D-892, which edits PREF-01) can correct it in passing. Not a finding against merge.
- **N2** (note, ROLE-14 hand step). After the merge, Colin re-pastes the text below the line of `governance/project_chat_instructions.md` into the Project's instructions. The pasted copy still has the old "No chat here can open another chat" paragraph. The coordinator names this step.
- **N3** (note, MRG-01). `governance pr checks` must be re-run on bf417b9 after this entry is on governance, and must be green before the merge.

## Handoff (THR-07)

- Goal: critical review of #751 to approval.
- Done: round 3 approved at bf417b9 with 0 must-fix.
- Next: the coordinator's `ledger/gos/pr-751.yaml` for bf417b9, the re-run of `governance pr checks`, `ledger_tool.py gate 751`, then a pinned squash merge, if main has not moved again.
