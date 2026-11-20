# Review of KB PR #46, round 6 (D-379, D-378 wording)

Head reviewed: `7216653`. It adds two commits on top of `245a161`, which was approved in round 5: `ed53995` adds D-379 and rewords D-378, and `7216653` names the follow-up issue in D-379. Nothing else changed.

- **D-379 matches the coordinator's post** (project chat, 2026-11-13 15:51:31 UTC). The red ZAP run on PR #170 fails in the scan's own "Replace these files" step and not in the PR, so it does not block the merge. A follow-up issue is filed.
- **The facts match the Actions logs and the code.** ZAP run 43455394552 on #170's head 62747fd failed on attempt 1 (job 131988044952) and attempt 2 (job 131989987559) with "Actual value: The job failed: The audiobook files exist already.", raised at `scripts/zap_scan.py`, line 738, in `_walk_english`. #170's files are the 7 named. `pyproject.toml` is in the scan's path filter, and #170 only adds a `quarantined` marker line to it. The other files are not imported by the scan: `zap_scan.py` imports `conftest` from `tests/browser/` (`tests/unit/` has none), while #170 changes the root `tests/conftest.py`. So the claim that the PR cannot have caused the failure holds.
- **Issue #177** is open, milestone v1.1, titled "ci: ZAP scan walk sometimes fails at "Replace these files" (files exist already)". Its body explains why it is v1.1, and refers back to D-379.
- **Status:** "Decided (Claude)" is correct, because this is the coordinator's own decision, and the time matches the post. The record links PR #170, Issue #177, D-364, D-368 and D-374. The row says that D-368 stays in force. The row has 6 cells, sits above D-378, and D-379 was the next free number.
- **D-378 wording:** "eight such cases, among them (…)" now marks the short list as incomplete, so round 5's note is answered.
- **PR title and body** cover D-379, and there is still no closing keyword before a link.

**Noted only (no change needed):** "passed on 2 of 4 recent runs" uses #177's count (heads 2347060 and cdf74c3 against #170's two attempts). The two earlier #12 runs (14ae267, 6ded8e8) also passed the walk, so the step has passed more often than this says. The conclusion, flaky and not broken, stands.

**Approved at 7216653.** It merges after KB PR #45 has merged, main has been merged into this branch, and a final check passes.
