# Review of PR #403 (v1.1.0 R1), round 2

Reviewed head **016b990** (one commit on 6fb9b6e), base `release/1.1` (a9e0e2d). Critical, Opus high. 15 Nov 2026 ~23:20 UTC.

**Verdict: approvable.** Every item of the round 1 fix list is done as written; three-system CI is green on this head. Not merged (waits for the coordinator's go).

## Fix list, item by item

| Item | Done? | Checked how |
|---|---|---|
| B1.1 racy-file guard in `file_id` | Yes | `app/config.py`: `RACY_NS = 2_000_000_000`; a file whose mtime is under 2 s old is hashed directly (`_hash`), older files keep the `(st_ino, st_mtime_ns, st_size)` cache. |
| B1.2 test that fails on 6fb9b6e | Yes | `test_a_file_rewritten_in_place_within_its_clock_tick_gets_a_new_id` (test_cli_listen.py): run against 6fb9b6e's `config.py` it fails (`'7692c3ad3540bb80' == '3fc4ccfe745870e2'`, the stale id). |
| B1.3 older file read once | Yes | `test_a_file_older_than_two_seconds_is_read_once` counts `_hash` calls (1 over two `file_id` calls) and pins `RACY_NS` as a literal. |
| B1.4 existing test unchanged, three runs with Windows | Yes | `test_app_chunks.py` untouched; dispatch runs 43770203315, 43770205947, 43770208262 all green on Linux, macOS, Windows and browser. |
| C1 #254 condition | Yes | Line now says keys count as citations when the reference list prints them as entry labels; without such a list the bracket stays as printed. Matches round 1's run on 6fb9b6e. |
| C2 #291 | Yes | Added to "Citations read the same on a second pass". |
| C3 #298 | Yes | "Text-step and extraction timing tests compare against a baseline run, the text-step ones on CPU time (#274, #276, #294, #298)". |

## Mutants on the guard (local)

| Mutant | Result |
|---|---|
| `RACY_NS = 0` (guard off) | killed by both new tests |
| guard always true (never cache) | killed by the read-once test |
| 6fb9b6e's `config.py` (no guard) | killed by the rewrite test |

## Other checks

- Diff 6fb9b6e..016b990: `CHANGELOG.md`, `src/sci2audio/app/config.py`, `tests/unit/test_cli_listen.py` only. No other behaviour change.
- Local: ruff check and format clean; fast suite 5879 passed, 1 skipped (Linux).
- CI on 016b990: PR run 43770200514 (Linux tests, browser, `CI passed`) green; the three dispatch runs green on all three systems, browser job included. Note: a `pull_request` run is Linux only by design (D-580), so the three-system proof is the dispatch runs.
- Round 1's #365 proof stands (test files unchanged since 6fb9b6e).

## Merge note

Squash-merge pinned to `sha=016b990`. Branch commit messages contain no closing keywords; the PR body's "Fixes #365" does not act on a non-default base, so close #365 by hand after the merge (as the body says). Then R1 → `release/1.1` push runs CI on three systems; the checklist runs (nightly, ZAP, mutation) follow per the plan.
