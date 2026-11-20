# Review PR #583, round 2 (final round, critical)

Reviewed: fix commit **bd2043a** plus merges of main d8c32ab (CHANGELOG, after #572) and 76129b7 (test_app_job imports, after #577). Head **76129b7**.
Verdict: **approved, merged** as **9333ce0** (squash, pinned to 76129b7). #493 and #544 are closed.

## Round-1 items

| Item | Result |
|---|---|
| R1 merge main | Merged twice, never rebased. Both sides are kept in CHANGELOG.md and in the test_app_job.py imports. The head contains main ee02e56, and it merges cleanly. |
| R2 only EILSEQ retried | `test_another_error_while_placing_a_newer_name_is_tried_once`: ENOSPC gives one try, 507 `disk-full`, and nothing is left. It kills q17. |
| R3 issue link | The PR body links #584 (the project folder name on another volume). |

## Final-round checks

- **Mutation:** the clean baseline is 236 passed, 2 skipped on the 8 affected test files. Of 18 hand mutants, 17 are killed: q1 to q8, q10b, q11 to q17. q9 is near-equivalent (the base probed on the M4B suffix, with the same characters).
- **Nightly seeds:** `test_output_retried_names.py` is green under the nightly profile with seeds 1, 2 and 3.
- **Three-system run:** ci:full on 76129b7 is green on ubuntu, macOS and Windows, with Chromium shards, ZAP and CodeQL. Every reported-only Firefox and WebKit leg is green.
- **CRIT-02:** it holds as stated in round 1. The check before speech and the writer share `audiobook_targets`, the probe uses O_EXCL and removes only its own file, and a retried name over a person's file is refused with that name. I probed it for both audiobook and script files.
- **D-768:** the CHANGELOG line is present and accurate.

## Notes

- N1 to N3 of round 1 stand. #584 is open for the project folder name.
- The `ci:full` label was still on at merge, because the author removes it after the run. It has no effect after the merge.
