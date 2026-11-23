# Audit: batch 005 (critical_only)

Audit thread audit-b005 (Opus 5.5 medium), 2026-11-23 (19:26 to 19:50Z). Read-only on product code;
this file and `ledger/audits/batch-005.md` are the only writes. Started from `ledger_tool.py flags`
(ROLE-15), then the merged diffs of the critical PRs.

- Scope: #754 (f1a9c1f), #760 (e3a328e), #761 (9f622af), #764 (eab9fb2), #762 (51dd21d),
  #765 (ebd6e40), and #751 (c63fc76, outside the batch). #753, #768 and #769 were read only where
  a flag or a critical PR touched them.
- **Verdict: pass. 0 blocking, 2 should-fix, 5 notes.**

## What was checked, and held

- **Pinned heads.** For every PR, `git merge-tree --write-tree <squash>^ <head>` equals the squash's
  tree, and the head is the approved round's head and the PR's last head: #751 bf417b9, #754 e07c3f1,
  #760 a25a67e, #761 a839955, #762 16b6e7a, #764 9d38cec, #765 adeba28.
- **Three systems on the final head (D-580).** Each run named in `gos/` was read: its head_sha is the
  approved head, and tests ubuntu, macos, windows and CI passed succeeded. #751 45150607713, #754
  45150916921, #760 45160343600, #761 45172191271, #762 45202299756, #764 45184320620 (attempt 2),
  #765 45216903017. #765's run shows conclusion `failure` only because of the reported-only WebKit
  shard (see S2); every required job is green. Main CI on 9f622af, eab9fb2, 51dd21d and ebd6e40 is
  success; main on 7e0e994 (#769) was still running at 19:26Z.
- **Hard rules.** No PR touched `src/sci2audio/core`, the import-linter contract, `pyproject.toml`,
  `uv.lock`, licences, `tests/corpus` or `tests/regression`. No network call added in `src/`. The
  only deletions in `src/` are the job's own files: the chapter record, `.partial` leftovers, and the
  read-along file after the overwrite check (`output/chapters.py`, BookWriter), which #761's
  vouch-window fix covers.
- **Golden files.** New: `test_app_audio_chapters.ambr`, `test_cli_convert.ambr` (#761),
  `test_output_book.ambr` (#762). Changed: three snapshots in #765, as 4.1 (D-903) predicts; its
  round reports name the golden diffs as checked.
- **Ruleset.** All eight files on main are 1.15.0; "advisor" is gone (D-892, #760). The
  `github-setup/` copies of `pr_checks.py`, `pr-checks.json` and `labeler.yml` are byte-equal to
  `.github/`. Governance carries #760, and its rules, tools, config and ledger README equal main
  (THR-14).
- **Cross-PR seams.** #761's web comment "until it can build one on request (#725)" is gone from
  main, so the later PRs closed what it pointed at. The web reads the chapter record only through
  `app` (`playable_chapters`); version 1 records still read after #765's version 2 (`READ_VERSIONS`).
- **Ledger.** `ledger_tool.py check` passes for all seven; its one complaint is #769 (merged 19:25Z,
  no merge record yet). That is #760's new F1 check failing on a real case (VER-02): the recorder
  fills `merged:`. #765's `deferred: 1` matches `deferred/pr765-1.yaml` (#767).

## Should-fix

- **S1. The two Issues #765 left have no milestone and no labels.** #767 (the round-2 deferral,
  `deferred/pr765-1.yaml`) and #766 (round 1 N2) carry no milestone, no `lane:*` and no `risk:*`
  label; GH-01 asks for all three the same day. #770, from #769's review, has them. Data fix (the
  coordinator, or whoever opens Issues for review-b005): #767 lane:app risk:low, #766 lane:cli
  risk:low, milestone as the coordinator plans them (`Later` while the project pauses).
  **Verdict: check.** `ledger_tool.py check` (or the governance PR check, which can call the API)
  could fail when the Issue a `deferred/` entry names has no milestone or no lane or risk label.
- **S2. WebKit failures that happen once each never reach D-374.** In this batch the reported-only
  WebKit shard failed three different tests, each once: on #764,
  `test_flow.py::test_the_removal_button_waits_for_the_script[webkit-library]` and
  `test_joined.py::test_the_mark_and_the_bar_stay_on_the_sentence_through_its_pieces[webkit]`
  (rerun passed); on #765, `test_markers.py::test_the_undo_ends_after_sixty_seconds_and_with_the_next_marker[webkit]`.
  #720 (another `test_markers.py` WebKit test, once) closed on #748 this morning. The reviews applied
  D-374 correctly ("twice" not met), but no Issue was opened for any of the three, so GH-01 ("every
  flaky test gets an issue the same day") is missed, and a second failure would be noticed only if a
  reviewer remembers the first. **Verdict: check.** A small step in the WebKit job (or the nightly)
  that appends each failed node ID to a tally, and fails the governance check when one node ID
  reaches two; until then, one Issue per WebKit failure (label testing, lane:web, risk:low).

## Notes

- **N1. The same vacuous test twice in the output lane** (`vacuous-test`, #754 M1 and #762 B1): a byte
  test on chunks whose joins trim nothing, so removing the trim passed. Different threads (impl-723,
  impl-725b). #762 turned it into a design step: `tests/unit/output_helpers.py` now has
  `quiet_edged_job` and `assert_joins_trim` ("no join trims anything"), used by both test files.
  **Verdict: leave**; the helper is the META-03 step.
- **N2. `missing-test` regressed after #765 (#768, #769), and `correctness` repeated (#765).** In each
  round the reviewer found it by a hand mutation (remove the guard, run the tests, all pass). The
  authors did not run that probe before review. **Verdict: check.** Proposal for the coordinator: a
  critical PR's pre-review `ci:full` also runs `mutmut` on the PR's changed `src/` files only, and the
  PR body lists the surviving mutants; reviewers then start from that list.
- **N3. #764 left a gap #770 found later.** A deleted chapter MP3 makes `current_audiobook` fail, so
  no chapter states show at all (from #724). #770 has milestone `Later`, lane:web, risk:low.
  **Verdict: leave**; it is outside the pause.
- **N4. Two merge-go files are timed after their squash.** `gos/pr-751.yaml` 10:21Z vs squash
  10:20:35Z; `gos/pr-765.yaml` 16:51Z vs 16:50:46Z. The other five are in the same minute. Most likely
  the go was given in chat and written after. **Verdict: leave** (minute resolution); if it matters,
  the go file could carry seconds.
- **N5. Batch file settings are stale again.** `plans/batch-005.md` says ruleset 1.13.0 "until #751
  merges"; main is 1.15.0 since #760. **Verdict: leave**: the batch is ending.

## Process numbers

- Critical PRs 7 (6 in the batch, #751 outside). Review rounds 13: #751 3, #754 2, #760 1, #761 2,
  #762 2, #764 1, #765 2. Overrides 0. Reverts 0. Deferred 1 (#767).
- Finding kinds: vacuous-test 2 (#754, #762), missing-case, vouch-window, incomplete-fix,
  correctness, missing-test (#765), ci-full-missing, behind-main, stale-instruction,
  narrating-comment (#751). `narrating-comment` did not recur after #760's check landed
  (#761 to #765 all passed it).
