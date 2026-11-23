# Review PR #751, round 2

- PR: https://github.com/dubidu22/sci2audio/pull/751 (#750, D-888; ruleset 1.13.0 → 1.14.0, claude.ai Project setup)
- Head: `b54bf4560c310ea5bc67d8ba850e4e66986760ba` (f168cbf plus a merge of main at 1cbfbd2)
- Thread: review-pr751-1 (Opus 5.5 high), 2026-11-23
- **Critical: yes** (CRIT-03, unchanged from round 1). The plan is the preview Colin approved in the settings session ("Yes, apply", D-888, D-891); no plan file exists (PR body).
- **Verdict: changes_requested.** Must-fix 1 (M1), should-fix 1 (S1), notes 3. Round 1's B1 and B2 are fixed.

## Round 1 findings

- B1 fixed: ci:full run 45146007075 (workflow_dispatch) on b54bf45 is green: `tests (ubuntu-latest)`, `tests (macos-latest)`, `tests (windows-latest)`, `lint and layers` (includes #749's working-files check), `licences`, `security`, both Chromium shards, `CI passed`.
- B2 fixed: b54bf45 merges `1cbfbd2` (merge commit, no force-push). See N1 for #752, which landed afterwards.

## Verified checks

- Diff read in full against the merge base (`origin/main...b54bf45`, 19 files, +163 −85). The two-dot diff against today's main also shows 62 deleted decision-log lines; those are #752's D-834 to D-890, which landed after the head, not a deletion by this PR (N1).
- Extracts: a script compared all 7 extracts with `claude-project-rules.yaml`. Each one has exactly the rules whose `applies_to` names its role or `all`, the rule texts are byte-equal to the full file, and `project_profile` and `execution_profile` are equal. All carry 1.14.0 and 2026-11-23.
- D-882 texts kept: MRG-01 (go file, re-run of `governance pr checks`, `updated_head`), ROLE-11, ROLE-17 and THR-04 do not appear in the diff, so they are unchanged from 1.13.0. The `D882` pins still cover them, and the `COORDINATOR:` and outside-the-batch fragments of `dispatcher_instructions.md` are still pinned.
- D-849 text kept: PLAN-01 keeps the promised-tests sentence ("…under the heading '## Tests promised in the plan'; the governance check fails the PR when a listed test does not collect"). `governance_paths` and `promised_tests_check` are unchanged. `ledger_tool.py` and `ledger/README.md` are untouched.
- D-881 removal is complete. THR-10 loses the subagent clause and is now the generic text. THR-05 loses "never while one of its subagents is running". The dispatcher instructions lose both subagent sentences. THR-11 and the `/compact` paragraph are gone, and `coordinator_compact_every_batches` is 0 in the config, the ruleset and all extracts. A grep of the PR tree for `THR-11`, `/compact`, `subagent` and `claude --model` finds nothing left in rules, config or instructions. The only hits are the generic "a tool that starts a session or subagent" clause and three KB research notes about Claude Code's `/code-review`, which are not rules.
- New file path lists: `governance/project_chat_instructions.md` is added consistently to critical_paths, lane:infra and doc_paths in the ruleset, the config, both `pr-checks.json` copies, both `labeler.yml` copies, `CODEOWNERS` and `lanes.yml`.
- The Project's pasted instructions as Colin pasted them match the new file's text below the line word for word.
- Tests: `test_ruleset.py` and `test_lanes.py` pass locally, 64 passed (`pytest --noconftest`). `uv` could not fetch Python 3.12.16 here, so the full fast suite is taken from CI. Hand mutations were each caught (VER-02): main's `dispatcher_instructions.md` (1 fail), main's `claude-project-rules.yaml` (11 fail), the worktree line removed from the new file (1 fail), MRG-01's go-file text changed (2 fail).
- Removed pins (THR-10/THR-05 D-881 fragments): their text was retired by D-888, and the new D888 tests fail when it comes back. Nothing was weakened.
- PR-06: no new dependency, tool or feature beyond the plan.

## Findings

- **M1** (must-fix, kind `stale-instruction`). `governance/project_chat_instructions.md`, "Starting other threads", says: "No chat here can open another chat. The coordinator and the dispatcher write a starter block … and ask Colin to open a new chat in this Project on that model and paste it." That contradicts D-889 (main, via #752): "it asks the project's channel session for each worker thread … and passes the brief". It also contradicts D-893 ("the coordinator asks the project for each thread (D-889)") and what is happening today: this review thread and #751's own update thread were opened without Colin. The text is unconditional and is pasted into every chat, so it overrides THR-10's first clause ("if you have a tool that opens a thread or session, use it"). That sends Colin click steps PREF-01 asks to avoid. The paragraph came from the preview approved at about 07:49Z, before D-889 at 08:27Z. Fix: reword the paragraph to D-889. For example: "Starting other threads. The coordinator asks the Project for each worker thread and passes the starter block (role, model, extract, first task) as its brief (D-889). Only where that is not possible does it ask Colin to open a new chat in this Project on that model and paste the block." Pin it in `test_the_project_chat_instructions_set_up_the_clone_and_the_governance_worktree`, or in a new test, so "No chat here can open another chat" cannot come back. Colin then re-pastes the Project's instructions (ROLE-14 hand step; the coordinator names it).
- **S1** (should-fix, kind `narrating-comment`, PR-05). `tests/unit/test_ruleset.py`, the two lines added above `D882`: "Its THR-10 and THR-05 texts (subagent hosting, D-881) ended with the move to the claude.ai Project (D-888, ruleset 1.14.0); the D888 pins below replace them." This is change history, not a why. Remove it. The D-888 comment block below already says why those pins exist. This kind regressed per D-891, and its lint check is planned for batch 005 slot B, so no new check is asked here.
- **N1** (note, MRG-01). Main moved again after b54bf45: #752 (`0994f97`, decision log only). A trial merge is clean. At merge time, update by merge commit, re-run CI including a three-system run on the new head (critical, D-580), and record it as `updated_head`. With M1's fix commit this can be one step: merge main into the branch before or with the fix commit.
- **N2** (note, CRIT-03). There is no plan file and no coordinator plan approval. The plan is the owner-approved preview (D-888; D-891 names the PR as Colin's). Owner approval exceeds coordinator approval, so the PR does not stop on this. The coordinator's go file should name that basis.
- **N3** (note). D-892 drops PREF-01's advisor, and that text stays in this PR by design (removed by the next ruleset PR, D-892). No action here.

## Handoff (THR-07)

- Goal: critical review of #751 to approval.
- Done: round 2 at b54bf45. B1 and B2 are fixed. M1 and S1 are open.
- Next: the author pushes one fix commit for M1 and S1, with main merged, plus a green three-system run. Round 3 then checks only M1, S1, the merge of #752 and CI on the new head. Ruled out: extract drift, loss of D-882/D-849 texts, leftover D-881/THR-11 text, path-list gaps (all checked above).
