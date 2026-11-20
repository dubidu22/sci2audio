# Review of sci2audio PR #107, round 2

Head reviewed: `647f81f`. The author answered on the PR (issuecomment-6842564251). main (`d30e6e7`, #103) was merged in with GitHub's update-branch, giving head `31ae413`.

| Item | Status | How I checked it |
|---|---|---|
| M1 Windows offline fixture | fixed in 5beba63 | `tests (windows-latest)` green on 3d09866 and 647f81f |
| M2 cancellable race | fixed in 3d09866 | 5 parallel fast runs green |
| S1 python_multipart in D-205 | fixed | A planted `import python_multipart` in `sci2audio.app` breaks the contract |
| S2 duplicate cookie | fixed | Live server: `x` plus the real token gives 200; two wrong values give 401 |
| S3 StrictBool | fixed | consent `"yes"` and `1` give 422; overwrite `"yes"` gives 422 |
| S4 NUL in output_folder | fixed | PUT /settings gives 422; the Hypothesis property now generates NUL |
| N1 websocket hint | fixed | `ws="none"` plus a filter for exactly the two uvicorn messages; no warning on a live upgrade request |
| N2 token on the browser command line | deferred to issue #117 (open) | |
| N3 stale .part | fixed | On start, a 2-hour-old .part is removed and a fresh one is kept |

Fast suite: 1356 passed (twice, `-n auto`). Merged with main locally: 1629 passed, 3 contracts kept. Nightly web: 152 passed. ruff, format and deptry are clean.

Verdict: passes. CI green on all three systems on 31ae413; squash-merged 13 Nov 2026 ~06:38 UTC as 7767174. No decision from D-192 to D-209 changed in substance.
