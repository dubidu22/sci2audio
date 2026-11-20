# Review of PR #412 (v1.1.0 checklist-run fixes), round 2

Reviewed head **2a598c1** (one commit on 8f98a62), base `release/1.1` 08d5965. Critical, Opus high. 16 Nov 2026 ~03:00 UTC.

**Verdict: approvable.** P1 and K1 are done exactly as listed; CI is green on all three systems; the nightly is green except the accepted #410 job. Not merged (waits for the coordinator's go).

## Fix list, item by item

| Item | Done? | Checked how |
|---|---|---|
| P1 position test route | Yes | `exit_save = f"{live.url}/api/v1/documents/{document}/position"`; the route continues a request only if it is inside `second.url`, or is a `POST` whose URL equals `exit_save`; everything else goes to `live.outside` and is aborted. Comment kept. Firefox proof: nightly 43783502578 "browser (firefox, ubuntu-latest)" green on 2a598c1; Chromium and WebKit (Linux, macOS) green too. |
| K1 known-issues wording | Yes | The line is word for word the text given in round 1. |

Diff 8f98a62..2a598c1: `CHANGELOG.md` and `tests/browser/test_player_position.py` only.

## Runs on 2a598c1

| Run | Result |
|---|---|
| ci:full 43783504996 | Green: tests on ubuntu, macos, windows; browser; lint and layers; licences; security; `CI passed`. |
| PR run 43783508472 | Green, all three systems (same jobs). |
| ZAP 43783508468 | Green. |
| Nightly 43783502578 | All green except "property-based tests, many examples": the single failure is the #410 shape again (LITERATUR section, "Eine Tabelle wird übersprungen." on the second run, 1 failed / 5878 passed), accepted by D-678 and now listed under Known issues. |
| Mutation 43774246928 (5131ba1, same mutmut config) | **Still running** at 03:00 UTC, 3 h 40 min into the "Mutation run" step (no `timeout-minutes`, so GitHub's 6 h job cap ends it at about 05:20 UTC at the latest). Before the `.github/` fix it stopped after 2 minutes at collection; now it is past that, which proves the config change. Per D-531 a partial result does not hold the tag; its result goes into the R2 body, survivors that change what users hear get tests, the rest go to #260. |

## Merge note

Squash pinned to `sha=2a598c1`. Check the branch commit messages for closing keywords before merging (round 1 commits name #410 and D-678 only as references).
